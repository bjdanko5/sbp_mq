# modules/worker/result_saver.py
"""
Сохранение результатов в Redis.
"""

import json
from typing import Dict, Any

import config
from modules.logger_config import logger


class ResultSaver:
    """Сохранение результатов в Redis."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def save_result(self, task_id: str, result: Dict[str, Any]) -> bool:
        """
        Сохранение результата в Redis с поддержкой UTF-8.
        
        Args:
            task_id: ID задачи
            result: Результат обработки
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            logger.warning(f"Worker [{self.parent.worker_id}] Redis клиент не инициализирован")
            return False
        
        try:
            existing = await redis_client.get(f'task:{task_id}')
            if existing:
                results = json.loads(existing)
            else:
                results = {'status': 'processing', 'files': []}
            
            if 'files' not in results:
                results['files'] = []
            results['files'].append(result)
            
            # Обновляем статус
            total_files = len(results['files'])
            completed_files = len([f for f in results['files'] if f.get('status') in ['completed', 'success']])
            error_files = len([f for f in results['files'] if f.get('status') == 'error'])
            
            if error_files > 0:
                results['status'] = 'error'
            elif total_files > 0 and total_files == completed_files:
                results['status'] = 'completed'
            else:
                results['status'] = 'processing'
            
            results['updated_at'] = self._get_timestamp()
            
            await redis_client.set(
                f'task:{task_id}',
                json.dumps(results, ensure_ascii=False)
            )
            
            await redis_client.expire(f'task:{task_id}', config.REDIS_TTL)
            
            logger.debug(f"Worker [{self.parent.worker_id}] Результат {task_id} сохранён")
            return True
            
        except Exception as e:
            logger.error(f"Worker [{self.parent.worker_id}] ошибка сохранения результата: {e}")
            return False
    
    async def save_error(self, task_id: str, error: str) -> bool:
        """
        Сохранение ошибки с поддержкой UTF-8.
        
        Args:
            task_id: ID задачи
            error: Текст ошибки
        
        Returns:
            bool: True при успехе
        """
        redis_client = self.parent.redis_client
        if redis_client is None:
            return False
        
        try:
            existing = await redis_client.get(f'task:{task_id}')
            if existing:
                results = json.loads(existing)
            else:
                results = {'status': 'error', 'files': []}
            
            results['status'] = 'error'
            results['error'] = error
            results['updated_at'] = self._get_timestamp()
            
            await redis_client.set(
                f'task:{task_id}',
                json.dumps(results, ensure_ascii=False)
            )
            
            await redis_client.expire(f'task:{task_id}', config.REDIS_TTL)
            
            return True
            
        except Exception as e:
            logger.error(f"Worker [{self.parent.worker_id}] ошибка сохранения ошибки: {e}")
            return False
    
    def _get_timestamp(self) -> str:
        """Возвращает текущую временную метку."""
        from datetime import datetime
        return datetime.now().isoformat()