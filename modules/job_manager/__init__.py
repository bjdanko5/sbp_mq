# modules/job_manager/__init__.py
"""
Job Manager — управление Job-файлами для SBP системы.

Job-файлы — это JSON-файлы, которые создаёт 1С и помещает в папку /sbp/jobs/
Формат имени: {bank}@{base}@{job_id}.json
"""

from .manager import JobManager
from .file_operations import FileOperations
from .search import JobSearch
from .stats import JobStats
from .cleanup import JobCleanup

__all__ = [
    'JobManager',
    'FileOperations',
    'JobSearch',
    'JobStats',
    'JobCleanup',
]

# Глобальный экземпляр для обратной совместимости
from .manager import job_manager