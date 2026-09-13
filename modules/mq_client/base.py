# modules/mq_client/base.py
"""
Базовый класс MQClient.
Отвечает за подключение к RabbitMQ и Redis.
"""

import aio_pika
from aio_pika.abc import AbstractConnection, AbstractChannel
import redis.asyncio as redis
from typing import Optional, Dict, Any, List, Union

import config
from modules.logger_config import logger


class MQClient:
    """
    Клиент для работы с Message Queue (RabbitMQ) и Redis.
    
    Поддерживает:
    - Публикацию задач (publish_task, publish_batch, publish_job)
    - Блокировку файлов (lock_file, unlock_file)
    - Сохранение результата (save_result)
    - Сохранение прогресса (save_progress)
    """
    
    def __init__(self):
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._redis: Optional[redis.Redis] = None
        self._connected = False
        
        # Инициализируем подмодули (будут установлены после подключения)
        self._publisher = None
        self._locker = None
        self._result_storage = None
    
    @property
    def is_connected(self) -> bool:
        """Проверяет, установлено ли соединение."""
        return self._connected
    
    @property
    def publisher(self):
        """Доступ к публикации сообщений."""
        return self._publisher
    
    @property
    def locker(self):
        """Доступ к блокировке файлов."""
        return self._locker
    
    @property
    def result_storage(self):
        """Доступ к хранению результатов."""
        return self._result_storage
    
    @property
    def channel(self) -> Optional[AbstractChannel]:
        """Возвращает канал RabbitMQ."""
        return self._channel
    
    @property
    def redis_client(self) -> Optional[redis.Redis]:
        """Возвращает клиент Redis."""
        return self._redis
    
    # ============================================================
    #                     ПОДКЛЮЧЕНИЕ
    # ============================================================
    
    async def connect(self) -> None:
        """Подключается к RabbitMQ и Redis."""
        try:
            # RabbitMQ
            self._connection = await aio_pika.connect_robust(
                host=config.RABBITMQ_HOST,
                port=config.RABBITMQ_PORT,
                login=config.RABBITMQ_USER,
                password=config.RABBITMQ_PASSWORD,
            )
            self._channel = await self._connection.channel()
            
            if self._channel is not None:
                await self._channel.declare_queue(
                    config.RABBITMQ_QUEUE,
                    durable=True
                )
            else:
                raise Exception("Не удалось создать канал RabbitMQ")
            
            # Redis
            self._redis = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                decode_responses=True
            )
            
            if self._redis is not None:
                await self._redis.ping()
            
            self._connected = True
            
            # Инициализируем подмодули
            from .publisher import Publisher
            from .locker import Locker
            from .result_storage import ResultStorage
            
            self._publisher = Publisher(self)
            self._locker = Locker(self)
            self._result_storage = ResultStorage(self)
            
            logger.info("[MQClient] Подключение к RabbitMQ и Redis установлено")
            
        except Exception as e:
            self._connected = False
            logger.error(f"[MQClient] Ошибка подключения: {e}")
            raise
    
    async def close(self) -> None:
        """Закрывает соединения с RabbitMQ и Redis."""
        try:
            if self._connection is not None and not self._connection.is_closed:
                await self._connection.close()
                logger.debug("[MQClient] Соединение с RabbitMQ закрыто")
        except Exception as e:
            logger.warning(f"[MQClient] Ошибка при закрытии RabbitMQ: {e}")
        
        try:
            if self._redis is not None:
                await self._redis.close()
                logger.debug("[MQClient] Соединение с Redis закрыто")
        except Exception as e:
            logger.warning(f"[MQClient] Ошибка при закрытии Redis: {e}")
        
        self._connected = False
        logger.info("[MQClient] Соединения закрыты")
    
    async def ensure_connected(self) -> None:
        """Проверяет соединение и переподключает при необходимости."""
        if not self._connected or self._connection is None or self._connection.is_closed:
            await self.connect()
    
    # ============================================================
    #                     ПРОКСИ-МЕТОДЫ (обратная совместимость)
    # ============================================================
    
    async def publish_task(self, base: str, file_path, task_id: Optional[str] = None) -> str:
        """Публикует одну задачу в очередь (обратная совместимость)."""
        if self._publisher:
            return await self._publisher.publish_task(base, file_path, task_id)
        raise Exception("Publisher не инициализирован")
    
    async def publish_batch(self, base: str, file_paths, task_id: Optional[str] = None) -> str:
        """Публикует пакет задач (обратная совместимость)."""
        if self._publisher:
            return await self._publisher.publish_batch(base, file_paths, task_id)
        raise Exception("Publisher не инициализирован")
    
    async def publish_job(self, job_data: Dict[str, Any]) -> str:
        """Публикует Job (обратная совместимость)."""
        if self._publisher:
            return await self._publisher.publish_job(job_data)
        raise Exception("Publisher не инициализирован")
    
    async def lock_file(self, file_path, ttl: int = 3600) -> bool:
        """Блокирует файл (обратная совместимость)."""
        if self._locker:
            return await self._locker.lock_file(file_path, ttl)
        return False
    
    async def unlock_file(self, file_path) -> bool:
        """Снимает блокировку (обратная совместимость)."""
        if self._locker:
            return await self._locker.unlock_file(file_path)
        return False
    
    async def is_file_locked(self, file_path) -> bool:
        """Проверяет блокировку (обратная совместимость)."""
        if self._locker:
            return await self._locker.is_file_locked(file_path)
        return False
    
    async def is_file_processed(self, file_path) -> bool:
        """Проверяет обработку (обратная совместимость)."""
        if self._locker:
            return await self._locker.is_file_processed(file_path)
        return False
    
    async def mark_processed(self, file_path, result: Dict[str, Any]) -> bool:
        """Отмечает файл как обработанный (обратная совместимость)."""
        if self._locker:
            return await self._locker.mark_processed(file_path, result)
        return False
    
    # ============================================================
    #                     ПОЛНЫЙ РЕЗУЛЬТАТ
    # ============================================================
    
    async def save_result(
        self,
        task_id: str,
        result: Dict[str, Any],
        file_path: Optional[str] = None,
        ttl: int = config.REDIS_TTL
    ) -> bool:
        """Сохраняет полный результат (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.save_result(task_id, result, file_path, ttl)
        return False
    
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получает полный результат (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.get_result(task_id)
        return None
    
    async def delete_result(self, task_id: str) -> bool:
        """Удаляет полный результат (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.delete_result(task_id)
        return False
    
    # ============================================================
    #                     КРАТКИЙ ПРОГРЕСС
    # ============================================================
    
    async def save_progress(
        self,
        task_id: str,
        progress: Dict[str, Any],
        ttl: int = config.REDIS_TTL
    ) -> bool:
        """Сохраняет краткий прогресс (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.save_progress(task_id, progress, ttl)
        return False
    
    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получает краткий прогресс (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.get_progress(task_id)
        return None
    
    async def delete_progress(self, task_id: str) -> bool:
        """Удаляет краткий прогресс (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.delete_progress(task_id)
        return False
    
    # ============================================================
    #                     КОМБИНИРОВАННЫЙ СТАТУС
    # ============================================================
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Получает статус задачи (обратная совместимость)."""
        if self._result_storage:
            return await self._result_storage.get_task_status(task_id)
        return {"task_id": task_id, "status": "unknown", "message": "ResultStorage не инициализирован"}


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

mq_client = MQClient()