# modules/job_manager/cleanup.py
"""
Очистка старых Job-файлов.
"""

from datetime import datetime
from typing import Tuple,TYPE_CHECKING
# ✅ Импорт ТОЛЬКО для типизации (не выполняется в runtime)
if TYPE_CHECKING:
    from modules.job_manager.manager import JobManager
from modules.logger_config import logger, get_function_stack


class JobCleanup:
    """Очистка старых Job-файлов."""
    
    def __init__(self, parent):
        self.parent: 'JobManager' = parent
    
    def clean_old_jobs(self, days: int = 30) -> Tuple[int, int]:
        """
        Удаляет старые Job-файлы из папок success и error.
        
        Args:
            days: Возраст файлов в днях
        
        Returns:
            Tuple[int, int]: (удалено success, удалено error)
        """
        stack = get_function_stack()
        deleted_success = 0
        deleted_error = 0
        now = datetime.now()
        
        # Удаляем старые файлы из success
        for file_path in self.parent.success_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (now - mtime).days > days:
                    file_path.unlink()
                    deleted_success += 1
                    logger.debug(f"[{stack}] Удалён старый Job-файл из success: {file_path}")
            except Exception as e:
                logger.error(f"[{stack}] Ошибка удаления {file_path}: {e}")
        
        # Удаляем старые файлы из error
        for file_path in self.parent.error_dir.glob("*.json"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (now - mtime).days > days:
                    file_path.unlink()
                    deleted_error += 1
                    logger.debug(f"[{stack}] Удалён старый Job-файл из error: {file_path}")
            except Exception as e:
                logger.error(f"[{stack}] Ошибка удаления {file_path}: {e}")
        
        if deleted_success or deleted_error:
            logger.info(f"[{stack}] Удалено старых Job-файлов: success={deleted_success}, error={deleted_error}")
        
        return deleted_success, deleted_error
    
    def clean_by_bank(self, bank: str, days: int = 30) -> Tuple[int, int]:
        """
        Удаляет старые Job-файлы для указанного банка.
        
        Args:
            bank: Имя банка
            days: Возраст файлов в днях
        
        Returns:
            Tuple[int, int]: (удалено success, удалено error)
        """
        stack = get_function_stack()
        deleted_success = 0
        deleted_error = 0
        now = datetime.now()
        
        pattern = f"{bank}@*.json"
        
        for file_path in self.parent.success_dir.glob(pattern):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (now - mtime).days > days:
                    file_path.unlink()
                    deleted_success += 1
            except Exception as e:
                logger.error(f"[{stack}] Ошибка удаления {file_path}: {e}")
        
        for file_path in self.parent.error_dir.glob(pattern):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (now - mtime).days > days:
                    file_path.unlink()
                    deleted_error += 1
            except Exception as e:
                logger.error(f"[{stack}] Ошибка удаления {file_path}: {e}")
        
        return deleted_success, deleted_error