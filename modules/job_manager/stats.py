# modules/job_manager/stats.py
"""
Статистика по Job-файлам.
"""

from typing import Dict, Any, List
from pathlib import Path


class JobStats:
    """Статистика Job-файлов."""
    
    def __init__(self, parent):
        self.parent = parent
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику по Job-файлам.
        
        Returns:
            Dict[str, Any]: Статистика
        """
        jobs = list(self.parent.jobs_dir.glob("*.json"))
        success = list(self.parent.success_dir.glob("*.json"))
        error = list(self.parent.error_dir.glob("*.json"))
        
        return {
            'pending': len(jobs),
            'success': len(success),
            'error': len(error),
            'total': len(jobs) + len(success) + len(error)
        }
    
    def get_stats_by_bank(self, bank: str) -> Dict[str, Any]:
        """
        Возвращает статистику для указанного банка.
        
        Args:
            bank: Имя банка
        
        Returns:
            Dict[str, Any]: Статистика по банку
        """
        jobs = list(self.parent.jobs_dir.glob(f"{bank}@*.json"))
        success = list(self.parent.success_dir.glob(f"{bank}@*.json"))
        error = list(self.parent.error_dir.glob(f"{bank}@*.json"))
        
        return {
            'bank': bank,
            'pending': len(jobs),
            'success': len(success),
            'error': len(error),
            'total': len(jobs) + len(success) + len(error)
        }
    
    def get_stats_by_base(self, bank: str, base: str) -> Dict[str, Any]:
        """
        Возвращает статистику для указанной базы.
        
        Args:
            bank: Имя банка
            base: Имя базы
        
        Returns:
            Dict[str, Any]: Статистика по базе
        """
        pattern = f"{bank}@{base}@*.json"
        jobs = list(self.parent.jobs_dir.glob(pattern))
        success = list(self.parent.success_dir.glob(pattern))
        error = list(self.parent.error_dir.glob(pattern))
        
        return {
            'bank': bank,
            'base': base,
            'pending': len(jobs),
            'success': len(success),
            'error': len(error),
            'total': len(jobs) + len(success) + len(error)
        }