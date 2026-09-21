# modules/job_manager/search.py
"""
Поиск и фильтрация Job-файлов.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, TYPE_CHECKING

from modules.logger_config import logger

# ✅ Импорт ТОЛЬКО для типизации (не выполняется в runtime)
if TYPE_CHECKING:
    from modules.job_manager.manager import JobManager


class JobSearch:
    """Поиск Job-файлов."""
    
    def __init__(self, parent):
        self.parent: 'JobManager' = parent
    
    def find_jobs(
        self,
        bank: Optional[str] = None,
        base: Optional[str] = None,
    ) -> List[Path]:
        """
        Находит Job-файлы в папке jobs.
        
        Args:
            bank: Фильтр по банку (опционально)
            base: Фильтр по базе (опционально).
                  ⚠️ Без bank — ошибка: base не уникален между банками,
                  поэтому поиск только по base даст неверный результат.
        
        Returns:
            List[Path]: Список путей к Job-файлам.
                        Пустой список, если передан base без bank.
        """
        # ⚠️ base без bank — некорректный вызов: логируем и возвращаем []
        if base and not bank:
            logger.error(
                f"[JobSearch] find_jobs: base='{base}' указан без bank — "
                f"некорректный вызов (base не уникален между банками), "
                f"возвращаю пустой список"
            )
            return []
        
        pattern = "*.json"
        
        if bank and base:
            pattern = f"{bank}@{base}@*.json"
        elif bank:
            pattern = f"{bank}@*@*.json"
        
        return list(self.parent.jobs_dir.glob(pattern))
    
    def get_job_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Извлекает информацию о Job из имени файла.
        
        Returns:
            Optional[Dict[str, Any]]: {bank, base, job_id} или None
        """
        try:
            stem = file_path.stem
            parts = stem.split('@')
            if len(parts) == 3:
                return {
                    'bank': parts[0],
                    'base': parts[1],
                    'job_id': int(parts[2])
                }
        except Exception:
            pass
        return None
    
    def find_by_bank(self, bank: str) -> List[Path]:
        """
        Находит все Job-файлы для указанного банка.
        
        Эквивалентно find_jobs(bank=bank).
        """
        return self.find_jobs(bank=bank)
    
    def find_by_base(self, base: str) -> List[Path]:
        """
        Находит все Job-файлы для указанной базы.
        
        ⚠️ ВНИМАНИЕ: требует bank для корректной работы.
        Так как `base` не уникален между банками, метод find_jobs(base=base)
        без bank возвращает пустой список + пишет ошибку в лог.
        
        Для корректного поиска используйте find_jobs(bank=bank, base=base).
        """
        return self.find_jobs(base=base)