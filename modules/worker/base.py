# modules/worker/base.py
"""
Базовый класс Worker.
Отвечает за подключение к RabbitMQ и Redis, запуск и остановку.

⚠️ Все настройки берутся из config.py (единый источник).

✅ Graceful shutdown (controlled abort):
- request_shutdown() вызывается из signal handler (синхронно)
- Отменяет _current_message_task (abort текущей Job) и _task (consume_loop)
- start() ждёт завершения _current_message_task (через _wait_for_abort)
  перед cleanup(), чтобы _handle_abort успел сделать nack
"""

import asyncio
import os
import uuid
from typing import Optional, TYPE_CHECKING

import aio_pika
from aio_pika.abc import AbstractConnection, AbstractChannel
import redis.asyncio as redis

import config
from modules.logger_config import logger, aggregated_logger


# ✅ Для аннотаций типов (без циклических импортов)
if TYPE_CHECKING:
    from .consumer import MessageConsumer
    from .job_processor import JobProcessor
    from .file_processor import FileProcessor


# ✅ Таймаут ожидания завершения abort в start()
ABORT_WAIT_TIMEOUT = 10.0


class Worker:
    """
    Базовый Worker для обработки задач из очереди RabbitMQ.
    """
    
    def __init__(self):
        # ✅ Worker ID (из окружения или случайный)
        self.worker_id = os.getenv('WORKER_ID') or uuid.uuid4().hex[:6]
        
        # ✅ Имя лога (для ссылки в агрегированном логе)
        self._log_name = os.getenv('LOG_NAME', f"worker-{self.worker_id}")
        
        # ✅ Все настройки из config.py (единый источник)
        self.rabbitmq_host = config.RABBITMQ_HOST
        self.rabbitmq_port = config.RABBITMQ_PORT
        self.rabbitmq_user = config.RABBITMQ_USER
        self.rabbitmq_pass = config.RABBITMQ_PASSWORD
        self.rabbitmq_queue = config.RABBITMQ_QUEUE
        
        self.redis_host = config.REDIS_HOST
        self.redis_port = config.REDIS_PORT
        self.redis_db = config.REDIS_DB
        
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.redis_client: Optional[redis.Redis] = None
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        
        # ✅ Состояние для controlled abort (SIGTERM)
        self._shutdown_requested = False
        self._current_job: Optional[dict] = None
        self._current_message_task: Optional[asyncio.Task] = None
        
        # ✅ Инициализируем подмодули (с аннотациями типов)
        self._consumer: Optional['MessageConsumer'] = None
        self._job_processor: Optional['JobProcessor'] = None
        self._file_processor: Optional['FileProcessor'] = None
    
    # ============================================================
    #                     ПОДКЛЮЧЕНИЕ
    # ============================================================
    
    async def connect(self):
        """Подключение к RabbitMQ и Redis."""
        try:
            self.connection = await aio_pika.connect_robust(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                login=self.rabbitmq_user,
                password=self.rabbitmq_pass
            )
            
            self.channel = await self.connection.channel()
            
            if self.channel is not None:
                await self.channel.set_qos(prefetch_count=1)
            else:
                raise Exception("Не удалось создать канал RabbitMQ")
            
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            
            if self.redis_client:
                await self.redis_client.ping()
            
            # ✅ Импортируем подмодули
            from .consumer import MessageConsumer
            from .job_processor import JobProcessor
            from .file_processor import FileProcessor
            
            self._consumer = MessageConsumer(self)
            self._job_processor = JobProcessor(self)
            self._file_processor = FileProcessor(self)
            
            logger.info(f"✅ Worker [{self.worker_id}] подключен к RabbitMQ и Redis")
            logger.info(f"   RabbitMQ: {self.rabbitmq_host}:{self.rabbitmq_port}")
            logger.info(f"   Redis:    {self.redis_host}:{self.redis_port}/{self.redis_db}")
            logger.info(f"   Queue:    {self.rabbitmq_queue}")
            
        except Exception as e:
            logger.error(f"❌ Worker [{self.worker_id}] ошибка подключения: {e}")
            raise
    
    async def cleanup(self):
        """Очистка ресурсов."""
        try:
            if self.connection is not None and not self.connection.is_closed:
                await self.connection.close()
                logger.debug(f"Worker [{self.worker_id}] RabbitMQ закрыт")
        except Exception as e:
            logger.warning(f"Worker [{self.worker_id}] ошибка при закрытии RabbitMQ: {e}")
        
        try:
            if self.redis_client is not None:
                await self.redis_client.close()
                logger.debug(f"Worker [{self.worker_id}] Redis закрыт")
        except Exception as e:
            logger.warning(f"Worker [{self.worker_id}] ошибка при закрытии Redis: {e}")
        
        logger.info(f"🧹 Worker [{self.worker_id}] ресурсы очищены")
    
    # ============================================================
    #                     ЗАПУСК И ОСТАНОВКА
    # ============================================================
    
    async def start(self):
        """Запуск Worker."""
        try:
            await self.connect()
            self.is_running = True
            
            if self.channel is None:
                raise Exception("Канал не инициализирован")
            
            queue = await self.channel.declare_queue(
                self.rabbitmq_queue,
                durable=True
            )
            
            logger.info(f"🚀 Worker [{self.worker_id}] запущен, ожидает задачи...")
            
            # ✅ АГРЕГИРОВАННЫЙ ЛОГ
            aggregated_logger.info(
                f"🟢 [Worker {self.worker_id}] ЗАПУЩЕН | "
                f"queue: {self.rabbitmq_queue} | "
                f"детали: logs/{self._log_name}.log"
            )
            
            # ✅ Проверяем, что consumer инициализирован
            if self._consumer is None:
                raise Exception("MessageConsumer не инициализирован")
            
            self._task = asyncio.create_task(self._consumer.consume_loop(queue))
            
            try:
                await self._task
            except asyncio.CancelledError:
                logger.info(f"👋 Worker [{self.worker_id}] consume_loop отменён")
            finally:
                # ✅ Ждём завершения abort, если он ещё работает
                await self._wait_for_abort()
                
                await self.cleanup()
                # ✅ АГРЕГИРОВАННЫЙ ЛОГ
                aggregated_logger.info(
                    f"🔴 [Worker {self.worker_id}] ОСТАНОВЛЕН"
                )
            
        except Exception as e:
            logger.error(f"❌ Worker [{self.worker_id}] ошибка в работе: {e}", exc_info=True)
            aggregated_logger.error(
                f"❌ [Worker {self.worker_id}] ОШИБКА запуска | "
                f"детали: logs/{self._log_name}_errors.log"
            )
            await self.cleanup()
            raise
    
    async def _wait_for_abort(self):
        """
        Ждёт завершения _current_message_task (abort), если он ещё работает.
        
        Вызывается из start() перед cleanup(). Нужно, чтобы _handle_abort
        успел сделать nack до закрытия RabbitMQ-соединения.
        
        _current_message_task НЕ обнуляется в consume_loop — это позволяет
        _wait_for_abort видеть ссылку даже после выхода из consume_loop.
        """
        task = self._current_message_task
        if task is None or task.done():
            return
        
        logger.info(
            f"⏳ Worker [{self.worker_id}] жду завершения abort "
            f"(таймаут {ABORT_WAIT_TIMEOUT}s)..."
        )
        try:
            await asyncio.wait_for(task, timeout=ABORT_WAIT_TIMEOUT)
            logger.info(f"✅ Worker [{self.worker_id}] abort завершён")
        except asyncio.TimeoutError:
            logger.error(
                f"❌ Worker [{self.worker_id}] таймаут ожидания abort "
                f"({ABORT_WAIT_TIMEOUT}s) — abort не завершился"
            )
        except asyncio.CancelledError:
            # Task был отменён (это ожидаемо), abort уже отработал внутри
            logger.info(
                f"✅ Worker [{self.worker_id}] abort завершён (по CancelledError)"
            )
        except Exception as e:
            logger.error(
                f"❌ Worker [{self.worker_id}] ошибка abort: {e}",
                exc_info=True
            )
    
    # ============================================================
    #                CONTROLLED ABORT (SIGTERM)
    # ============================================================
    
    def request_shutdown(self) -> None:
        """
        Синхронный вызов из signal handler.
        
        Отменяет:
        - _current_message_task (если Job в работе → abort через CancelledError)
        - _task (consume_loop, если ждёт сообщение)
        
        ⚠️ Не делать здесь await или сложную логику — signal handler
        должен быть максимально быстрым.
        """
        self._shutdown_requested = True
        self.is_running = False
        
        # 1. Отменяем текущую обработку (если есть) — это запустит _handle_abort
        if self._current_message_task and not self._current_message_task.done():
            logger.debug(
                f"[Worker {self.worker_id}] request_shutdown: "
                f"отменяю _current_message_task"
            )
            self._current_message_task.cancel()
        
        # 2. Отменяем consume_loop (если ждёт сообщение — разбудим)
        if self._task and not self._task.done():
            logger.debug(
                f"[Worker {self.worker_id}] request_shutdown: "
                f"отменяю consume_loop"
            )
            self._task.cancel()
    
    async def stop(self):
        """Остановка Worker (ручная, не через сигнал)."""
        self._shutdown_requested = True
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.cleanup()
    
    # ============================================================
    #                     ДОСТУП К ПОДМОДУЛЯМ
    # ============================================================
    
    @property
    def consumer(self) -> Optional['MessageConsumer']:
        return self._consumer
    
    @property
    def job_processor(self) -> Optional['JobProcessor']:
        return self._job_processor
    
    @property
    def file_processor(self) -> Optional['FileProcessor']:
        return self._file_processor
    
    # ============================================================
    #                     ПРОКСИ-МЕТОДЫ
    # ============================================================
    
    async def _process_message(self, message):
        if self._consumer:
            await self._consumer.process_message(message)
    
    async def _process_job(self, bank, base, job_id, files):
        if self._job_processor:
            return await self._job_processor.process_job(bank, base, job_id, files)
        return {'status': 'error', 'error': 'JobProcessor не инициализирован'}
    
    async def _process_file_for_bank(self, file_path, bank, base, paths, request_ids):
        if self._file_processor:
            return await self._file_processor.process_file(
                file_path, bank, base, paths, request_ids
            )
        return {'status': 'error', 'error': 'FileProcessor не инициализирован'}


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

worker = Worker()