# modules/mq_client/locker.py
"""
Блокировка файлов через Redis.
"""

import json
from pathlib import Path
from typing import Dict, Any, Union

import config
from modules.logger_config import logger


class Locker:
    """Блокировка файлов через Redis."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def lock_file(self, file_path: Union[str, Path], ttl: int = 3600) -> bool:
        """
        Блокирует файл для обработки.
        
        Args:
            file_path: Путь к файлу
            ttl: Время жизни блокировки (секунд)
        
        Returns:
            bool: True — файл заблокирован, False — уже заблокирован
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            logger.warning("[MQClient] Redis не инициализирован, блокировка невозможна")
            return False
        
        file_path = str(file_path)
        key = f"lock:{file_path}"
        result = await redis_client.set(key, "locked", nx=True, ex=ttl)
        return result is True
    
    async def unlock_file(self, file_path: Union[str, Path]) -> bool:
        """
        Снимает блокировку с файла.
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        file_path = str(file_path)
        key = f"lock:{file_path}"
        result = await redis_client.delete(key)
        return result > 0
    
    async def is_file_locked(self, file_path: Union[str, Path]) -> bool:
        """Проверяет, заблокирован ли файл."""
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        file_path = str(file_path)
        key = f"lock:{file_path}"
        return await redis_client.exists(key) == 1
    
    async def is_file_processed(self, file_path: Union[str, Path]) -> bool:
        """Проверяет, обработан ли файл."""
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        file_path = str(file_path)
        key = f"processed:{file_path}"
        return await redis_client.exists(key) == 1
    
    async def mark_processed(self, file_path: Union[str, Path], result: Dict[str, Any]) -> bool:
        """Отмечает файл как обработанный."""
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        file_path = str(file_path)
        key = f"processed:{file_path}"
        await redis_client.setex(
            key,
            config.REDIS_TTL,
            json.dumps(result, ensure_ascii=False)
        )
        return True