# modules/mq_client/__init__.py
"""
MQ Client — клиент для работы с RabbitMQ и Redis.

Поддерживает:
- Публикацию Job (publish_job) — для мультибанковости
- Блокировку файлов (защита от дублирования)
- Сохранение и получение результатов из Redis
"""

from .base import MQClient
from .publisher import Publisher
from .locker import Locker
from .result_storage import ResultStorage

__all__ = [
    'MQClient',
    'Publisher',
    'Locker',
    'ResultStorage',
]

# Глобальный экземпляр для обратной совместимости
from .base import mq_client