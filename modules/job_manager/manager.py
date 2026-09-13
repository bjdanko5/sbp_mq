# modules/job_manager/manager.py
"""
Основной менеджер Job-файлов.
Объединяет все подмодули в единый интерфейс.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import config
from modules.logger_config import logger, get_function_stack
from .file_operations import FileOperations
from .search import JobSearch
from .stats import JobStats
from .cleanup import JobCleanup


class JobManager:
    """
    Управление Job-файлами.
    
    Job-файлы — это JSON-файлы, которые создаёт 1С и помещает в папку /sbp/jobs/
    Формат имени: {bank}@{base}@{job_id}.json
    Пример: ci@zkh_ursv@123.json
    
    Структура Job-файла:
    {
        "bank": "ci",
        "base": "zkh_ursv",
        "job_id": 123,
        "job_name": "Печать квитанций",
        "created_at": "2026-09-05T10:00:00",
        "files": [
            {"filename": "7845.json", "count": 4, "request_ids": ["754316", ...]}
        ],
        "total_requests": 4,
        "status": "pending"
    }
    """
    
    def __init__(self):
        self.jobs_dir = Path(config.SBP_ROOT4JOBS)
        self.success_dir = self.jobs_dir / "success"
        self.error_dir = self.jobs_dir / "error"
        
        # Создаём все необходимые директории
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.success_dir.mkdir(parents=True, exist_ok=True)
        self.error_dir.mkdir(parents=True, exist_ok=True)
        
        # Инициализируем подмодули
        self._files = FileOperations(self)
        self._search = JobSearch(self)
        self._stats = JobStats(self)
        self._cleanup = JobCleanup(self)
        
        logger.debug(f"[JobManager] Инициализирован: jobs_dir={self.jobs_dir}")
    
    # ============================================================
    #                     ДОСТУП К ПОДМОДУЛЯМ
    # ============================================================
    
    @property
    def files(self) -> 'FileOperations':
        """Доступ к операциям с файлами."""
        return self._files
    
    @property
    def search(self) -> 'JobSearch':
        """Доступ к поиску Job-файлов."""
        return self._search
    
    @property
    def stats(self) -> 'JobStats':
        """Доступ к статистике."""
        return self._stats
    
    @property
    def cleanup(self) -> 'JobCleanup':
        """Доступ к очистке старых файлов."""
        return self._cleanup
    
    # ============================================================
    #                     ПРОКСИ-МЕТОДЫ (обратная совместимость)
    # ============================================================
    
    # Получение путей
    def get_job_file_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу."""
        return self._files.get_job_file_path(bank, base, job_id)
    
    def get_success_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу в папке success."""
        return self._files.get_success_path(bank, base, job_id)
    
    def get_error_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу в папке error."""
        return self._files.get_error_path(bank, base, job_id)
    
    def get_bank_base_path(self, bank: str, base: str) -> Path:
        """Возвращает путь к папке банка/базы."""
        return self._files.get_bank_base_path(bank, base)
    
    # Проверка существования
    def job_exists(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, существует ли Job-файл."""
        return self._files.job_exists(bank, base, job_id)
    
    def job_in_success(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, находится ли Job в папке success."""
        return self._files.job_in_success(bank, base, job_id)
    
    def job_in_error(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, находится ли Job в папке error."""
        return self._files.job_in_error(bank, base, job_id)
    
    def get_job_status(self, bank: str, base: str, job_id: int) -> str:
        """Возвращает статус Job: pending, success, error, not_found."""
        return self._files.get_job_status(bank, base, job_id)
    
    # Чтение
    def read_job(self, bank: str, base: str, job_id: int) -> Optional[Dict[str, Any]]:
        """Читает Job-файл."""
        return self._files.read_job(bank, base, job_id)
    
    def read_job_by_path(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Читает Job-файл по пути."""
        return self._files.read_job_by_path(file_path)
    
    # Запись
    def write_job(self, job_data: Dict[str, Any]) -> bool:
        """Записывает Job-файл."""
        return self._files.write_job(job_data)
    
    # Перемещение
    def move_to_success(self, bank: str, base: str, job_id: int) -> bool:
        """Перемещает Job-файл в папку success."""
        return self._files.move_to_success(bank, base, job_id)
    
    def move_to_error(self, bank: str, base: str, job_id: int) -> bool:
        """Перемещает Job-файл в папку error."""
        return self._files.move_to_error(bank, base, job_id)
    
    # Поиск
    def find_jobs(self, bank: Optional[str] = None, base: Optional[str] = None) -> List[Path]:
        """Находит Job-файлы в папке jobs."""
        return self._search.find_jobs(bank, base)
    
    def get_job_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Извлекает информацию о Job из имени файла."""
        return self._search.get_job_info(file_path)
    
    # Статистика
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по Job-файлам."""
        return self._stats.get_stats()
    
    # Очистка
    def clean_old_jobs(self, days: int = 30) -> Tuple[int, int]:
        """Удаляет старые Job-файлы."""
        return self._cleanup.clean_old_jobs(days)


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

job_manager = JobManager()