# modules/job_manager/file_operations.py
"""
Операции с файловой системой:
- Чтение/запись Job-файлов
- Перемещение между папками
- Проверка существования
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

import config
from modules.logger_config import logger, get_function_stack


class FileOperations:
    """Операции с файлами Job."""
    
    def __init__(self, parent):
        self.parent = parent
    
    # ============================================================
    #                     ПОЛУЧЕНИЕ ПУТЕЙ
    # ============================================================
    
    def get_job_file_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу."""
        filename = f"{bank}@{base}@{job_id}.json"
        return self.parent.jobs_dir / filename
    
    def get_success_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу в папке success."""
        filename = f"{bank}@{base}@{job_id}.json"
        return self.parent.success_dir / filename
    
    def get_error_path(self, bank: str, base: str, job_id: int) -> Path:
        """Возвращает путь к Job-файлу в папке error."""
        filename = f"{bank}@{base}@{job_id}.json"
        return self.parent.error_dir / filename
    
    def get_bank_base_path(self, bank: str, base: str) -> Path:
        """Возвращает путь к папке банка/базы."""
        #return Path(str(config.SBP_ROOT / bank / base))
        return config.SBP_ROOT.bank_pathlib(bank, base)
    
    # ============================================================
    #                     ПРОВЕРКА СУЩЕСТВОВАНИЯ
    # ============================================================
    
    def job_exists(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, существует ли Job-файл."""
        return self.get_job_file_path(bank, base, job_id).exists()
    
    def job_in_success(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, находится ли Job в папке success."""
        return self.get_success_path(bank, base, job_id).exists()
    
    def job_in_error(self, bank: str, base: str, job_id: int) -> bool:
        """Проверяет, находится ли Job в папке error."""
        return self.get_error_path(bank, base, job_id).exists()
    
    def get_job_status(self, bank: str, base: str, job_id: int) -> str:
        """
        Возвращает статус Job.
        
        Returns:
            str: 'pending', 'success', 'error', 'not_found'
        """
        if self.job_exists(bank, base, job_id):
            return 'pending'
        if self.job_in_success(bank, base, job_id):
            return 'success'
        if self.job_in_error(bank, base, job_id):
            return 'error'
        return 'not_found'
    
    # ============================================================
    #                     ЧТЕНИЕ
    # ============================================================
    
    def read_job(self, bank: str, base: str, job_id: int) -> Optional[Dict[str, Any]]:
        """Читает Job-файл и возвращает его содержимое."""
        stack = get_function_stack()
        file_path = self.get_job_file_path(bank, base, job_id)
        
        if not file_path.exists():
            logger.error(f"[{stack}] Job-файл не найден: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"[{stack}] Job-файл прочитан: {file_path}")
                return data
        except json.JSONDecodeError as e:
            logger.error(f"[{stack}] Ошибка парсинга JSON в {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"[{stack}] Ошибка чтения Job-файла {file_path}: {e}")
            return None
    
    def read_job_by_path(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Читает Job-файл по пути."""
        stack = get_function_stack()
        
        if not file_path.exists():
            logger.error(f"[{stack}] Job-файл не найден: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"[{stack}] Job-файл прочитан: {file_path.name}")
                return data
        except Exception as e:
            logger.error(f"[{stack}] Ошибка чтения Job-файла {file_path}: {e}")
            return None
    
    # ============================================================
    #                     ЗАПИСЬ
    # ============================================================
    
    def write_job(self, job_data: Dict[str, Any]) -> bool:
        """Записывает Job-файл."""
        stack = get_function_stack()
        
        bank = job_data.get('bank')
        base = job_data.get('base')
        job_id = job_data.get('job_id')
        
        #if not all([bank, base, job_id]):
        if not bank or not base or not job_id:    
            logger.error(f"[{stack}] Недостаточно данных для записи Job: {job_data}")
            return False
        
        file_path = self.get_job_file_path(bank, base, job_id)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[{stack}] Job-файл записан: {file_path}")
            return True
        except Exception as e:
            logger.error(f"[{stack}] Ошибка записи Job-файла {file_path}: {e}")
            return False
    
    # ============================================================
    #                     ПЕРЕМЕЩЕНИЕ
    # ============================================================
    
    def move_to_success(self, bank: str, base: str, job_id: int) -> bool:
        """Перемещает Job-файл в папку success."""
        stack = get_function_stack()
        src = self.get_job_file_path(bank, base, job_id)
        dst = self.get_success_path(bank, base, job_id)
        return self._move_job_file(src, dst, "success", stack)
    
    def move_to_error(self, bank: str, base: str, job_id: int) -> bool:
        """Перемещает Job-файл в папку error."""
        stack = get_function_stack()
        src = self.get_job_file_path(bank, base, job_id)
        dst = self.get_error_path(bank, base, job_id)
        return self._move_job_file(src, dst, "error", stack)
    
    def _move_job_file(self, src: Path, dst: Path, folder: str, stack: str) -> bool:
        """Внутренний метод для перемещения Job-файла."""
        if not src.exists():
            logger.error(f"[{stack}] Job-файл не найден для перемещения: {src}")
            return False
        
        try:
            # Если файл уже существует в папке назначения, удаляем его
            if dst.exists():
                dst.unlink()
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            
            # Извлекаем bank, base, job_id из имени файла
            parts = src.stem.split('@')
            if len(parts) == 3:
                bank, base, job_id = parts
                logger.info(f"[{stack}] Job {job_id} ({bank}@{base}) перемещён в {folder}")
            else:
                logger.info(f"[{stack}] Job-файл {src.name} перемещён в {folder}")
            
            return True
        except Exception as e:
            logger.error(f"[{stack}] Ошибка перемещения Job-файла {src} -> {dst}: {e}")
            return False