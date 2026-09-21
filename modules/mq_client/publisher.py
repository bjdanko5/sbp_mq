# modules/mq_client/publisher.py
"""
Публикация сообщений в RabbitMQ.

Используется Job-модель — основной метод publish_job.
"""

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any

from aio_pika import Message, DeliveryMode

import config
from modules.logger_config import logger

# ✅ Импорт ТОЛЬКО для типизации (не выполняется в runtime)
if TYPE_CHECKING:
    from modules.mq_client.base import MQClient


class Publisher:
    """Публикация сообщений в очередь RabbitMQ."""
    
    def __init__(self, parent: 'MQClient'):
        self.parent: 'MQClient' = parent
    
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
            "created_at": job_data.get("created_at", ""),
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