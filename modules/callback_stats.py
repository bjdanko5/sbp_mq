# modules/callback_stats.py
"""
Хранилище статистики callback'ов в Redis.

Ключи:
- callback:count:{bank}:{base}:{job_id}     → INTEGER (счётчик)
- callback:last_error:{bank}:{base}:{job_id} → JSON
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any

import redis.asyncio as redis

import config
from modules.logger_config import logger


class CallbackStats:
    """Статистика callback'ов."""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
    
    async def connect(self):
        """Подключение к Redis."""
        if self._redis is not None:
            return
        
        self._redis = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=True
        )
        await self._redis.ping()
        logger.info("[CallbackStats] Подключено к Redis")
    
    async def close(self):
        """Закрытие соединения."""
        if self._redis:
            await self._redis.close()
            self._redis = None
    
    async def _ensure_connected(self):
        if self._redis is None:
            await self.connect()
    
    # ============================================================
    #                     ЗАПИСЬ
    # ============================================================
    
    async def increment(self, bank: str, base: str, job_id: int) -> int:
        """
        Увеличивает счётчик callback'ов.
        
        Returns:
            int: Новое значение счётчика
        """
        await self._ensure_connected()
        if self._redis is None:
            return 0
        
        key = f"callback:count:{bank}:{base}:{job_id}"
        count = await self._redis.incr(key)
        await self._redis.expire(key, config.REQUEST_TTL)
        return count
    
    async def save_error(
        self,
        bank: str,
        base: str,
        job_id: int,
        error: str
    ) -> bool:
        """
        Сохраняет последнюю ошибку callback'а.
        
        Args:
            bank, base, job_id: идентификация Job
            error: текст ошибки
        """
        await self._ensure_connected()
        if self._redis is None:
            return False
        
        key = f"callback:last_error:{bank}:{base}:{job_id}"
        data = {
            "error": error,
            "timestamp": datetime.now().isoformat(),
            "base": base
        }
        await self._redis.setex(key, config.REQUEST_TTL, json.dumps(data, ensure_ascii=False))
        return True
    
    # ============================================================
    #                     ЧТЕНИЕ
    # ============================================================
    
    async def get_count(self, bank: str, base: str, job_id: int) -> int:
        """Возвращает счётчик callback'ов."""
        await self._ensure_connected()
        if self._redis is None:
            return 0
        
        key = f"callback:count:{bank}:{base}:{job_id}"
        value = await self._redis.get(key)
        return int(value) if value else 0
    
    async def get_last_error(
        self,
        bank: str,
        base: str,
        job_id: int
    ) -> Optional[Dict[str, Any]]:
        """Возвращает последнюю ошибку callback'а."""
        await self._ensure_connected()
        if self._redis is None:
            return None
        
        key = f"callback:last_error:{bank}:{base}:{job_id}"
        data = await self._redis.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

callback_stats = CallbackStats()