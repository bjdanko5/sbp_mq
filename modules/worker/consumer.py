# modules/worker/consumer.py
"""
Потребление сообщений из очереди RabbitMQ.

Пишет в:
- Свой лог (logs/{LOG_NAME}.log) — детали
- Общий лог (logs/all.log) — ключевые события
"""

import json
import time

from aio_pika.abc import AbstractIncomingMessage

from modules.logger_config import logger, aggregated_logger
from modules.job_manager import job_manager
from modules.mq_client import mq_client


class MessageConsumer:
    """Потребитель сообщений из очереди."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def consume_loop(self, queue):
        """Цикл потребления сообщений с поддержкой остановки."""
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self.parent.is_running:
                    break
                await self.process_message(message)
    
    async def process_message(self, message: AbstractIncomingMessage):
        """Обработка сообщения из очереди."""
        async with message.process():
            worker_id = self.parent.worker_id
            log_name = self.parent._log_name
            start_time = time.time()
            
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
                
                result = await self.parent.job_processor.process_job(
                    bank, base, job_id, files, job_data,
                    task_id=task_id
                )
                
                # Сохраняем результат
                await mq_client.save_result(task_id, result)
                
                # ✅ УДАЛЯЕМ прогресс (задача завершена)
                await mq_client.delete_progress(task_id)
                
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
                    errors = result.get('errors', 0)
                    
                    # ✅ ДЕТАЛЬНЫЙ ЛОГ
                    logger.warning(
                        f"⚠️ [Worker {worker_id}] Job {bank}@{base}@{job_id} "
                        f"ЗАВЕРШЁН С ОШИБКАМИ за {elapsed:.2f} сек | "
                        f"ошибок: {errors}, "
                        f"файлов: {summary.get('processed_files', 0)}/{summary.get('total_files', 0)} | "
                        f"task_id: {task_id}"
                    )
                    
                    # ✅ АГРЕГИРОВАННЫЙ ЛОГ
                    aggregated_logger.warning(
                        f"⚠️ [Worker {worker_id}] ОШИБКА Job "
                        f"{bank}@{base}@{job_id} за {elapsed:.2f} сек | "
                        f"{errors} ошибок | детали: logs/{log_name}_errors.log"
                    )
                
            except json.JSONDecodeError as e:
                logger.error(
                    f"❌ [Worker {worker_id}] Ошибка парсинга JSON: {e}",
                    exc_info=True
                )
                aggregated_logger.error(
                    f"❌ [Worker {worker_id}] Ошибка парсинга JSON | "
                    f"детали: logs/{log_name}_errors.log"
                )
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
                except:
                    pass