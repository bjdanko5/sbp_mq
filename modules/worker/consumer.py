# modules/worker/consumer.py
"""
Потребление сообщений из очереди RabbitMQ.

Пишет в:
- Свой лог (logs/{LOG_NAME}.log) — детали
- Общий лог (logs/all.log) — ключевые события

✅ Graceful shutdown (controlled abort):
- SIGTERM → worker.request_shutdown() → отмена _current_message_task и _task
- В process_message ловится CancelledError → _handle_abort()
- Abort: move_to_error → save_result → delete_progress → soap_notify → nack(requeue=False)
"""

import asyncio
import json
import time
from datetime import datetime

from aio_pika.abc import AbstractIncomingMessage

from modules.logger_config import logger, aggregated_logger
from modules.job_manager import job_manager
from modules.mq_client import mq_client


# ✅ Таймауты при abort
ABORT_SOAP_TIMEOUT = 3.0       # сек — soap_notify
ABORT_REDIS_TIMEOUT = 2.0      # сек — save_result / delete_progress
ABORT_REASON = "Worker shutdown (SIGTERM)"


class MessageConsumer:
    """Потребитель сообщений из очереди."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def consume_loop(self, queue):
        """
        Цикл потребления сообщений с поддержкой остановки.
        
        ✅ Каждое сообщение обрабатывается в отдельной asyncio-задаче,
        чтобы её можно было отменить из signal handler (request_shutdown).
        
        ⚠️ _current_message_task НЕ обнуляется в finally — это нужно
        для _wait_for_abort() в Worker.start(), чтобы дождаться завершения
        _handle_abort перед cleanup().
        """
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self.parent.is_running:
                    logger.debug(
                        f"[Worker {self.parent.worker_id}] "
                        f"shutdown requested, выход из consume_loop"
                    )
                    break
                
                # ✅ Запускаем обработку как отдельную задачу
                self.parent._current_message_task = asyncio.create_task(
                    self.process_message(message)
                )
                try:
                    await self.parent._current_message_task
                except asyncio.CancelledError:
                    # Abort уже сделан внутри process_message.
                    # Выходим из цикла — shutdown запрошен.
                    logger.warning(
                        f"[Worker {self.parent.worker_id}] "
                        f"обработка отменена, выход из consume_loop"
                    )
                    break
    
    async def process_message(self, message: AbstractIncomingMessage):
        """
        Обработка сообщения из очереди.
        
        ✅ requeue=False — при необработанном исключении nack(requeue=False)
        ✅ ignore_processed=True — если мы уже сделали ack/nack,
           process() не вмешивается (не дублирует)
        """
        async with message.process(requeue=False, ignore_processed=True):
            worker_id = self.parent.worker_id
            log_name = self.parent._log_name
            start_time = time.time()
            
            # ✅ Локальные переменные для abort-ветки
            bank = base = job_id = task_id = job_name = None
            job_data = None
            
            try:
                data = json.loads(message.body.decode())
                task_id = data.get('task_id')
                bank = data.get('bank')
                base = data.get('base')
                job_id = data.get('job_id')
                job_name = data.get('job_name', '')
                files = data.get('files', [])
                total_requests = data.get('total_requests', 0)
                
                # ✅ ДЕТАЛЬНЫЙ ЛОГ — только в свой файл
                logger.info(
                    f"📥 [Worker {worker_id}] ВЗЯЛ Job "
                    f"{bank}@{base}@{job_id} "
                    f"({job_name or 'без имени'}) | "
                    f"файлов: {len(files)}, запросов: {total_requests} | "
                    f"task_id: {task_id}"
                )
                
                # ✅ АГРЕГИРОВАННЫЙ ЛОГ — общий + ссылка на детали
                aggregated_logger.info(
                    f"📥 [Worker {worker_id}] ВЗЯЛ Job "
                    f"{bank}@{base}@{job_id} | "
                    f"файлов: {len(files)}, запросов: {total_requests} | "
                    f"детали: logs/{log_name}.log"
                )
                
                # ✅ Список файлов (только в свой лог)
                if files:
                    for f in files:
                        logger.debug(
                            f"📄 [Worker {worker_id}] Файл: {f.get('filename')} "
                            f"({f.get('count', 0)} запросов)"
                        )
                
                # Обрабатываем Job
                job_data = {
                    'bank': bank,
                    'base': base,
                    'job_id': job_id,
                    'job_name': job_name,
                    'created_at': data.get('created_at', ''),
                    'files': files,
                    'total_requests': total_requests,
                }
                
                # ✅ Запоминаем текущую Job (для abort из signal handler)
                self.parent._current_job = {
                    'bank': bank,
                    'base': base,
                    'job_id': job_id,
                    'task_id': task_id,
                    'job_data': job_data,
                }
                
                result = await self.parent.job_processor.process_job(
                    bank, base, job_id, files, job_data,
                    task_id=task_id
                )
                
                # Сохраняем результат
                await mq_client.save_result(task_id, result)
                
                # ✅ УДАЛЯЕМ прогресс (задача завершена)
                await mq_client.delete_progress(task_id)
                
                # ✅ SOAP-уведомление 1С — ТОЛЬКО при ошибке
                if result.get("status") != "completed":
                    from modules.soap_notify import notify_job_error
                    await notify_job_error(bank, base, job_id, result)
                
                elapsed = time.time() - start_time
                summary = result.get('summary', {})
                
                # ✅ Перемещаем Job-файл
                if result.get('status') == 'completed':
                    job_manager.move_to_success(bank, base, job_id)
                    
                    # ✅ ДЕТАЛЬНЫЙ ЛОГ
                    logger.info(
                        f"✅ [Worker {worker_id}] ЗАВЕРШИЛ Job "
                        f"{bank}@{base}@{job_id} за {elapsed:.2f} сек | "
                        f"файлов: {summary.get('success_files', 0)}/{summary.get('total_files', 0)}, "
                        f"запросов: {summary.get('success_requests', 0)}/{summary.get('total_requests', 0)} | "
                        f"task_id: {task_id}"
                    )
                    
                    # ✅ АГРЕГИРОВАННЫЙ ЛОГ
                    aggregated_logger.info(
                        f"✅ [Worker {worker_id}] ГОТОВ Job "
                        f"{bank}@{base}@{job_id} за {elapsed:.2f} сек | "
                        f"{summary.get('success_files', 0)}/{summary.get('total_files', 0)} файлов, "
                        f"{summary.get('success_requests', 0)}/{summary.get('total_requests', 0)} запросов"
                    )
                else:
                    job_manager.move_to_error(bank, base, job_id)
                    error_files = summary.get('error_files', 0)
                    error_requests = summary.get('error_requests', 0)
                    
                    # ✅ ДЕТАЛЬНЫЙ ЛОГ
                    logger.warning(
                        f"⚠️ [Worker {worker_id}] Job {bank}@{base}@{job_id} "
                        f"ЗАВЕРШЁН С ОШИБКАМИ за {elapsed:.2f} сек | "
                        f"файлов с ошибкой: {error_files}, "
                        f"запросов с ошибкой: {error_requests}, "
                        f"обработано файлов: {summary.get('processed_files', 0)}/{summary.get('total_files', 0)} | "
                        f"task_id: {task_id}"
                    )
                    
                    # ✅ АГРЕГИРОВАННЫЙ ЛОГ
                    aggregated_logger.warning(
                        f"⚠️ [Worker {worker_id}] ОШИБКА Job "
                        f"{bank}@{base}@{job_id} за {elapsed:.2f} сек | "
                        f"{error_files} файлов, {error_requests} запросов с ошибкой | "
                        f"детали: logs/{log_name}_errors.log"
                    )
                
                # ✅ Явный ack (process() с ignore_processed=True не дублирует)
                await message.ack()
            
            except asyncio.CancelledError:
                # ✅ CONTROLLED ABORT (SIGTERM)
                
                # Если abort до парсинга — нечего абортить, просто nack
                if bank is None or base is None or job_id is None:
                    logger.warning(
                        f"⚠️ [Worker {worker_id}] ABORT до парсинга "
                        f"сообщения — nack(requeue=False)"
                    )
                    try:
                        await message.nack(requeue=False)
                    except Exception as e:
                        logger.error(
                            f"❌ [Worker {worker_id}] Ошибка nack: {e}"
                        )
                    # ✅ Пробрасываем дальше — consume_loop должен выйти
                    raise
                
                # ✅ После этой проверки bank/base/job_id — точно не None
                await self._handle_abort(
                    message=message,
                    bank=bank, base=base, job_id=job_id,
                    task_id=task_id if task_id is not None else '',
                    job_name=job_name if job_name is not None else '',
                )
                # ✅ Пробрасываем дальше — consume_loop должен выйти
                raise
            
            except json.JSONDecodeError as e:
                logger.error(
                    f"❌ [Worker {worker_id}] Ошибка парсинга JSON: {e}",
                    exc_info=True
                )
                aggregated_logger.error(
                    f"❌ [Worker {worker_id}] Ошибка парсинга JSON | "
                    f"детали: logs/{log_name}_errors.log"
                )
                await message.nack(requeue=False)
            
            except Exception as e:
                logger.error(
                    f"❌ [Worker {worker_id}] Ошибка обработки задачи: {e}",
                    exc_info=True
                )
                aggregated_logger.error(
                    f"❌ [Worker {worker_id}] Ошибка обработки | "
                    f"детали: logs/{log_name}_errors.log"
                )
                try:
                    data = json.loads(message.body.decode())
                    job_manager.move_to_error(
                        data.get('bank'),
                        data.get('base'),
                        data.get('job_id')
                    )
                except Exception as inner_e:
                    logger.warning(
                        f"[Worker {worker_id}] Не удалось переместить Job в error: {inner_e}"
                    )
                await message.nack(requeue=False)
            
            finally:
                self.parent._current_job = None
    
    # ============================================================
    #                   CONTROLLED ABORT
    # ============================================================
    
    async def _handle_abort(
        self,
        message: AbstractIncomingMessage,
        bank: str,
        base: str,
        job_id: int,
        task_id: str,
        job_name: str,
    ) -> None:
        """
        Обработка controlled abort при SIGTERM.
        
        1С очищает задание и не переотправляет Job,
        поэтому requeue не используется — сообщение не возвращаем в очередь.
        
        Порядок операций:
        1. move_to_error — локально, быстро
        2. save_result + delete_progress — Redis локальный, timeout 2s
        3. soap_notify — внешний SOAP, timeout 3s
        4. nack(requeue=False) — сообщение не возвращаем
        """
        worker_id = self.parent.worker_id
        log_name = self.parent._log_name
        
        logger.warning(
            f"⚠️ [Worker {worker_id}] ABORT Job {bank}@{base}@{job_id} — "
            f"помечаю как error и уведомляю 1С"
        )
        aggregated_logger.warning(
            f"⚠️ [Worker {worker_id}] ABORT Job {bank}@{base}@{job_id} — "
            f"{ABORT_REASON} | детали: logs/{log_name}_errors.log"
        )
        
        abort_result = {
            "bank": bank,
            "base": base,
            "job_id": job_id,
            "job_name": job_name or '',
            "status": "error",
            "error": ABORT_REASON,
            "finished_at": datetime.now().isoformat(),
            "files": [],
            "summary": {
                "total_files": 0, "processed_files": 0,
                "success_files": 0, "error_files": 0,
                "total_requests": 0, "success_requests": 0, "error_requests": 0,
            },
        }
        
        # 1. Переместить Job-файл в error/ (локально, быстро)
        try:
            moved = job_manager.move_to_error(bank, base, job_id)
            if moved:
                logger.info(
                    f"📦 [Worker {worker_id}] Job {bank}@{base}@{job_id} "
                    f"перемещён в error/"
                )
            else:
                logger.warning(
                    f"⚠️ [Worker {worker_id}] Не удалось переместить "
                    f"Job {bank}@{base}@{job_id} в error/ "
                    f"(возможно, уже там или файл не найден)"
                )
        except Exception as e:
            logger.error(
                f"❌ [Worker {worker_id}] Ошибка move_to_error: {e}",
                exc_info=True
            )
        
        # 2. Сохранить результат в Redis (мониторинг должен видеть error)
        if task_id:
            try:
                await asyncio.wait_for(
                    mq_client.save_result(task_id, abort_result),
                    timeout=ABORT_REDIS_TIMEOUT,
                )
                logger.info(
                    f"✅ [Worker {worker_id}] abort_result сохранён в Redis "
                    f"для task_id={task_id}"
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"❌ [Worker {worker_id}] Таймаут save_result "
                    f"({ABORT_REDIS_TIMEOUT}s) для task_id={task_id}"
                )
            except Exception as e:
                logger.error(
                    f"❌ [Worker {worker_id}] Ошибка save_result: {e}"
                )
            
            try:
                await asyncio.wait_for(
                    mq_client.delete_progress(task_id),
                    timeout=ABORT_REDIS_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"❌ [Worker {worker_id}] Таймаут delete_progress "
                    f"({ABORT_REDIS_TIMEOUT}s) для task_id={task_id}"
                )
            except Exception as e:
                logger.error(
                    f"❌ [Worker {worker_id}] Ошибка delete_progress: {e}"
                )
        
        # 3. SOAP-уведомление 1С — с таймаутом 3 сек
        try:
            from modules.soap_notify import notify_job_error
            await asyncio.wait_for(
                notify_job_error(bank, base, job_id, abort_result),
                timeout=ABORT_SOAP_TIMEOUT,
            )
            logger.info(
                f"✅ [Worker {worker_id}] SOAP-уведомление об abort "
                f"Job {bank}@{base}@{job_id} отправлено"
            )
        except asyncio.TimeoutError:
            logger.error(
                f"❌ [Worker {worker_id}] Таймаут SOAP-уведомления "
                f"({ABORT_SOAP_TIMEOUT}s) для Job {bank}@{base}@{job_id} — "
                f"1С, вероятно, недоступна"
            )
        except Exception as e:
            logger.error(
                f"❌ [Worker {worker_id}] Ошибка SOAP-уведомления: {e}",
                exc_info=True
            )
        
        # 4. nack без requeue — сообщение не возвращаем
        try:
            await message.nack(requeue=False)
            logger.info(
                f"📤 [Worker {worker_id}] Сообщение Job {bank}@{base}@{job_id} "
                f"nack(requeue=False)"
            )
        except Exception as e:
            logger.error(
                f"❌ [Worker {worker_id}] Ошибка nack(requeue=False): {e}"
            )