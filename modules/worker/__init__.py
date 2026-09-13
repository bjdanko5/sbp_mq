# modules/worker/__init__.py
"""
Worker — обработка задач из очереди RabbitMQ.

Поддерживает:
- Обработку Job-задач (несколько файлов в одном Job)
- Последовательную обработку файлов внутри Job
- При ошибке — Job прерывается
- Перемещение Job-файлов в success/error
- Мультибанковость через SBPRoot
"""

from .base import Worker
from .consumer import MessageConsumer
from .job_processor import JobProcessor
from .file_processor import FileProcessor
from .result_saver import ResultSaver

__all__ = [
    'Worker',
    'MessageConsumer',
    'JobProcessor',
    'FileProcessor',
    'ResultSaver',
]

# Глобальный экземпляр для обратной совместимости
from .base import worker