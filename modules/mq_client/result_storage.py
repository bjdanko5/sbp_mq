# modules/mq_client/result_storage.py
"""
Сохранение и получение результатов и прогресса из Redis.

Поддерживает:
- Полный результат задачи: task:{task_id}
- Краткий прогресс задачи: progress:{task_id}
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Any, Optional

import config
from modules.logger_config import logger
# ✅ Импорт ТОЛЬКО для типизации (не выполняется в runtime)
if TYPE_CHECKING:
    from modules.mq_client.base import MQClient

class ResultStorage:
    """Сохранение и получение результатов и прогресса из Redis."""
    
    def __init__(self, parent: 'MQClient'):
        self.parent: 'MQClient' = parent
    
    # ============================================================
    #                   ПОЛНЫЙ РЕЗУЛЬТАТ
    # ============================================================
    
    async def save_result(
        self,
        task_id: str,
        result: Dict[str, Any],
        file_path: Optional[str] = None,
        ttl: int = config.REDIS_TTL
    ) -> bool:
        """
        Сохраняет ПОЛНЫЙ результат выполнения задачи.
        Вызывается только в конце обработки.
        
        Args:
            task_id: ID задачи
            result: Полный результат (симметричный заданию)
            file_path: Путь к файлу (для отметки обработанного)
            ttl: Время жизни (секунд)
        
        Returns:
            bool: True при успехе
        """
        logger.info(f"📝 [Redis] save_result START для task_id={task_id}")
        
        redis_client = self.parent.redis_client
        if redis_client is None:
            logger.warning("[MQClient] Redis не инициализирован, сохранение результата невозможно")
            return False
        
        key = f"task:{task_id}"
        
        try:
            await redis_client.setex(
                key,
                ttl,
                json.dumps(result, ensure_ascii=False)
            )
            
            logger.info(f"✅ [Redis] Результат {task_id} сохранён, статус: {result.get('status')}")
            
            if file_path and self.parent.locker:
                await self.parent.locker.mark_processed(file_path, result)
                await self.parent.locker.unlock_file(file_path)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [Redis] Ошибка сохранения результата {task_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает полный результат задачи из Redis.
        
        Args:
            task_id: ID задачи
        
        Returns:
            Optional[Dict[str, Any]]: Результат или None
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return None
        
        key = f"task:{task_id}"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    async def delete_result(self, task_id: str) -> bool:
        """
        Удаляет полный результат задачи из Redis.
        
        Args:
            task_id: ID задачи
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        key = f"task:{task_id}"
        result = await redis_client.delete(key)
        return result > 0
    
    # ============================================================
    #                   КРАТКИЙ ПРОГРЕСС
    # ============================================================
    
    async def save_progress(
        self,
        task_id: str,
        progress: Dict[str, Any],
        ttl: int = config.REDIS_TTL
    ) -> bool:
        """
        Сохраняет КРАТКИЙ прогресс задачи.
        Вызывается после обработки каждого файла.
        
        Args:
            task_id: ID задачи
            progress: Краткий прогресс (~300 байт)
            ttl: Время жизни (секунд)
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            logger.warning("[MQClient] Redis не инициализирован, сохранение прогресса невозможно")
            return False
        
        key = f"progress:{task_id}"
        
        try:
            # Добавляем timestamp обновления
            progress['updated_at'] = datetime.now().isoformat()
            
            await redis_client.setex(
                key,
                ttl,
                json.dumps(progress, ensure_ascii=False)
            )
            
            logger.debug(
                f"📊 [Redis] Прогресс {task_id}: "
                f"{progress.get('processed_files')}/{progress.get('total_files')} файлов "
                f"({progress.get('progress_percent')}%)"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ [Redis] Ошибка сохранения прогресса {task_id}: {e}")
            return False
    
    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Получает краткий прогресс задачи из Redis.
        
        Args:
            task_id: ID задачи
        
        Returns:
            Optional[Dict[str, Any]]: Прогресс или None
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return None
        
        key = f"progress:{task_id}"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None
    
    async def delete_progress(self, task_id: str) -> bool:
        """
        Удаляет прогресс задачи из Redis.
        Вызывается после сохранения полного результата.
        
        Args:
            task_id: ID задачи
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        key = f"progress:{task_id}"
        result = await redis_client.delete(key)
        
        if result > 0:
            logger.debug(f"🗑️ [Redis] Прогресс {task_id} удалён")
        
        return result > 0
    
    # ============================================================
    #                   КОМБИНИРОВАННЫЙ СТАТУС
    # ============================================================
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Получает статус задачи.
        
        Логика:
        1. Если есть полный результат → возвращаем его
        2. Если есть прогресс → возвращаем прогресс
        3. Иначе → pending
        
        Args:
            task_id: ID задачи
        
        Returns:
            Dict[str, Any]: Статус задачи
        """
        # 1. Полный результат
        result = await self.get_result(task_id)
        if result:
            return {
                "task_id": task_id,
                "status": result.get("status", "unknown"),
                "result": result
            }
        
        # 2. Прогресс
        progress = await self.get_progress(task_id)
        if progress:
            return {
                "task_id": task_id,
                "status": "processing",
                "progress": progress
            }
        
        # 3. Ничего нет
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Задача ещё не обработана или не найдена"
        }