# modules/mq_client/publisher.py
"""
Публикация сообщений в RabbitMQ.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from aio_pika import Message, DeliveryMode

import config
from modules.logger_config import logger


class Publisher:
    """Публикация сообщений в очередь RabbitMQ."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def publish_task(
        self,
        base: str,
        file_path: Union[str, Path],
        task_id: Optional[str] = None
    ) -> str:
        """
        Публикует одну задачу в очередь.
        
        Args:
            base: Имя базы
            file_path: Путь к файлу
            task_id: ID задачи (если None — генерируется)
        
        Returns:
            str: ID задачи
        """
        await self.parent.ensure_connected()
        
        if task_id is None:
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        file_path = Path(file_path)
        message_data = {
            "task_id": task_id,
            "base": base,
            "file_name": file_path.name,
            "file_path": str(file_path),
            "created_at": datetime.now().isoformat()
        }
        
        await self._publish_message(message_data)
        logger.debug(f"[MQClient] Задача {task_id} опубликована: {base}/{file_path.name}")
        
        return task_id
    
    async def publish_batch(
        self,
        base: str,
        file_paths: List[Path],
        task_id: Optional[str] = None
    ) -> str:
        """
        Публикует пакет задач в очередь.
        
        Args:
            base: Имя базы
            file_paths: Список путей к файлам
            task_id: ID задачи (если None — генерируется)
        
        Returns:
            str: ID задачи (общий для всех файлов)
        """
        if task_id is None:
            task_id = f"batch_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        for file_path in file_paths:
            await self.publish_task(base, file_path, task_id)
        
        logger.debug(f"[MQClient] Пакет {task_id} опубликован: {len(file_paths)} файлов")
        return task_id
    
    async def publish_job(self, job_data: Dict[str, Any]) -> str:
        """
        Публикует Job в очередь RabbitMQ.
        
        Args:
            job_data: Данные Job-файла
        
        Returns:
            str: task_id
        """
        await self.parent.ensure_connected()
        
        task_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        # Проверяем обязательные поля
        required_fields = ['bank', 'base', 'job_id']
        for field in required_fields:
            if field not in job_data:
                raise ValueError(f"Отсутствует обязательное поле: {field}")
        
        # ✅ Передаём все реквизиты Job
        message_data = {
            "task_id": task_id,
            "bank": job_data.get("bank"),
            "base": job_data.get("base"),
            "job_id": job_data.get("job_id"),
            "job_name": job_data.get("job_name", ""),
            "created_at": job_data.get("created_at", ""),  # ✅ Добавлено
            "files": job_data.get("files", []),
            "total_requests": job_data.get("total_requests", 0),
            "published_at": datetime.now().isoformat()
        }
        
        await self._publish_message(message_data)
        
        logger.info(
            f"[MQClient] Job {task_id} опубликован: "
            f"{job_data.get('bank')}@{job_data.get('base')}@{job_data.get('job_id')}, "
            f"файлов: {len(job_data.get('files', []))}"
        )
        
        return task_id
    
    async def _publish_message(self, message_data: Dict[str, Any]) -> None:
        """
        Внутренний метод для публикации сообщения в RabbitMQ.
        
        Args:
            message_data: Данные для отправки
        """
        channel = self.parent.channel
        if channel is None:
            raise Exception("Канал RabbitMQ не инициализирован")
        
        message = Message(
            body=json.dumps(message_data, ensure_ascii=False).encode('utf-8'),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await channel.default_exchange.publish(
            message,
            routing_key=config.RABBITMQ_QUEUE
        )