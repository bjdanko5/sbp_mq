# modules/request_storage.py
"""
Хранилище связок requestID → task_id для callback.

Использует Redis.

Зачем:
- При callback приходит список requestID
- Нужно найти base, чтобы отправить в SOAP нужной базы
- base хранится в task:{task_id} (полный результат Job)
- Этот модуль даёт быстрый переход: requestID → task_id → base

Жизненный цикл:
1. Worker сохраняет req:{requestID} → task_id (TTL: REQUEST_TTL)
   ДО отправки в банк — чтобы callback точно нашёл base
2. Callback находит task_id по requestID
3. Читает task:{task_id} → извлекает base
4. После успешной обработки — удаляет req:{requestID}

⚠️ Fallback:
Если req:{requestID} не найден (например, старые данные) —
callback ищет base в SQLite (db.py).
"""

from typing import List, Dict, Optional, cast

import redis.asyncio as redis

import config
from modules.logger_config import logger


class RequestStorage:
    """
    Хранилище requestID → task_id в Redis.
    
    Ключи:
    - req:{requestID} → task_id (строка)
    
    TTL: REQUEST_TTL (по умолчанию 1 час)
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._ttl = config.REQUEST_TTL
    
    # ============================================================
    #                     ПОДКЛЮЧЕНИЕ
    # ============================================================
    
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
        logger.info(f"[RequestStorage] Подключено к Redis (TTL: {self._ttl} сек)")
    
    async def close(self):
        """Закрытие соединения."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            logger.info("[RequestStorage] Соединение закрыто")
    
    async def _ensure_connected(self):
        """Проверяет соединение."""
        if self._redis is None:
            await self.connect()
    
    # ============================================================
    #                     СОХРАНЕНИЕ
    # ============================================================
    
    async def save_requests(self, request_ids: List[str], task_id: str) -> int:
        """
        Сохраняет связки requestID → task_id с автоматическим TTL.
        
        Args:
            request_ids: Список requestID
            task_id: ID задачи (Job)
        
        Returns:
            int: Количество сохранённых
        """
        await self._ensure_connected()
        
        if self._redis is None or not request_ids:
            return 0
        
        try:
            pipe = self._redis.pipeline()
            
            for rid in request_ids:
                key = f"req:{rid}"
                # ✅ Автоматическое удаление через TTL
                pipe.setex(key, self._ttl, task_id)
            
            await pipe.execute()
            
            logger.debug(
                f"[RequestStorage] Сохранено {len(request_ids)} requestID → "
                f"task_id={task_id} (TTL: {self._ttl} сек)"
            )
            return len(request_ids)
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка сохранения: {e}")
            return 0
    
    # ============================================================
    #                     ЧТЕНИЕ
    # ============================================================
    
    async def get_task_id(self, request_id: str) -> Optional[str]:
        """
        Получает task_id по requestID.
        
        Args:
            request_id: ID запроса
        
        Returns:
            Optional[str]: task_id или None
        """
        await self._ensure_connected()
        
        if self._redis is None:
            return None
        
        try:
            key = f"req:{request_id}"
            raw = await self._redis.get(key)
            
            # ✅ Явное приведение: decode_responses=True → str,
            # но Pylance видит bytes | str | None
            if raw is None:
                return None
            return cast(str, raw)
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка чтения {request_id}: {e}")
            return None
    
    async def get_task_ids_for_requests(
        self,
        request_ids: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        Получает task_ids для списка requestID (batch, MGET).
        
        Args:
            request_ids: Список requestID
        
        Returns:
            Dict[str, Optional[str]]: {requestID: task_id}
        """
        await self._ensure_connected()
        
        if self._redis is None or not request_ids:
            return {rid: None for rid in request_ids}
        
        try:
            keys = [f"req:{rid}" for rid in request_ids]
            raw_results = await self._redis.mget(keys)
            
            # ✅ Явное приведение каждого элемента
            result: Dict[str, Optional[str]] = {}
            for rid, raw in zip(request_ids, raw_results):
                if raw is None:
                    result[rid] = None
                else:
                    result[rid] = cast(str, raw)
            
            return result
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка batch-чтения: {e}")
            return {rid: None for rid in request_ids}
    
    # ============================================================
    #                     УДАЛЕНИЕ
    # ============================================================
    
    async def delete_requests(self, request_ids: List[str]) -> int:
        """
        Удаляет requestID (после успешного callback).
        
        Args:
            request_ids: Список requestID
        
        Returns:
            int: Количество удалённых
        """
        await self._ensure_connected()
        
        if self._redis is None or not request_ids:
            return 0
        
        try:
            keys = [f"req:{rid}" for rid in request_ids]
            deleted = await self._redis.delete(*keys)
            
            if deleted > 0:
                logger.debug(f"[RequestStorage] Удалено {deleted} requestID")
            
            return deleted
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка удаления: {e}")
            return 0
    
    async def clear_all(self) -> int:
        """
        Удаляет ВСЕ req:* ключи.
        
        ⚠️ Использовать для отладки.
        
        Returns:
            int: Количество удалённых
        """
        await self._ensure_connected()
        
        if self._redis is None:
            return 0
        
        try:
            count = 0
            cursor = 0
            
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match="req:*",
                    count=1000
                )
                
                if keys:
                    count += await self._redis.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.warning(f"[RequestStorage] clear_all: удалено {count} requestID")
            return count
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка clear_all: {e}")
            return 0
    
    # ============================================================
    #                     СТАТИСТИКА
    # ============================================================
    
    async def count(self) -> int:
        """
        Возвращает количество req:* ключей.
        
        ⚠️ Медленно при большом количестве (SCAN).
        """
        await self._ensure_connected()
        
        if self._redis is None:
            return 0
        
        try:
            count = 0
            cursor = 0
            
            while True:
                cursor, keys = await self._redis.scan(
                    cursor=cursor,
                    match="req:*",
                    count=1000
                )
                count += len(keys)
                
                if cursor == 0:
                    break
            
            return count
            
        except Exception as e:
            logger.error(f"[RequestStorage] Ошибка count: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, object]:
        """Возвращает статистику."""
        total = await self.count()
        return {
            "total_requests": total,
            "ttl_seconds": self._ttl,
            "ttl_minutes": round(self._ttl / 60, 1),
            "ttl_hours": round(self._ttl / 3600, 2)
        }


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

request_storage = RequestStorage()