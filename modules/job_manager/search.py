# modules/job_manager/search.py
"""
Поиск и фильтрация Job-файлов.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List


class JobSearch:
    """Поиск Job-файлов."""
    
    def __init__(self, parent):
        self.parent = parent
    
    def find_jobs(self, bank: Optional[str] = None, base: Optional[str] = None) -> List[Path]:
        """
        Находит Job-файлы в папке jobs.
        
        Args:
            bank: Фильтр по банку (опционально)
            base: Фильтр по базе (опционально)
        
        Returns:
            List[Path]: Список путей к Job-файлам
        """
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
        """Находит все Job-файлы для указанного банка."""
        return self.find_jobs(bank=bank)
    
    def find_by_base(self, base: str) -> List[Path]:
        """Находит все Job-файлы для указанной базы."""
        return self.find_jobs(base=base)