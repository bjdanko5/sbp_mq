# modules/monitor/ws.py
"""
WebSocket-менеджер + фоновый poller для мониторинга.
"""

import asyncio
import json
from typing import Set

from fastapi import WebSocket

from modules.logger_config import logger
from .data import get_monitor_data


class ConnectionManager:
    """Управление активными WebSocket-соединениями."""
    
    def __init__(self):
        self._active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
    
    async def connect(self, ws: WebSocket) -> None:
        """Принять соединение и добавить в список."""
        await ws.accept()
        async with self._lock:
            self._active.add(ws)
        logger.debug(f"[WS] Клиент подключён (всего: {len(self._active)})")
    
    async def disconnect(self, ws: WebSocket) -> None:
        """Убрать соединение из списка."""
        async with self._lock:
            self._active.discard(ws)
        logger.debug(f"[WS] Клиент отключён (осталось: {len(self._active)})")
    
    async def broadcast(self, data: dict) -> None:
        """Отправить JSON всем активным клиентам."""
        if not self._active:
            return
        
        message = json.dumps(data, ensure_ascii=False, default=str)
        
        async with self._lock:
            clients = self._active.copy()
        
        dead: Set[WebSocket] = set()
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.debug(f"[WS] Ошибка отправки: {e}")
                dead.add(ws)
        
        if dead:
            async with self._lock:
                self._active -= dead
            logger.debug(f"[WS] Удалено мёртвых: {len(dead)}")
    
    @property
    def count(self) -> int:
        return len(self._active)


manager = ConnectionManager()


async def monitor_poller(stop_event: asyncio.Event) -> None:
    """Фоновый poller: каждые 2 сек читает данные, шлёт broadcast при изменениях."""
    logger.info("[WS] Poller запущен")
    last_hash: str = ""
    
    while not stop_event.is_set():
        try:
            data = await get_monitor_data()
            current_hash = json.dumps(data, sort_keys=True, default=str)
            
            if current_hash != last_hash:
                await manager.broadcast(data)
                last_hash = current_hash
                
                if manager.count > 0:
                    logger.debug(
                        f"[WS] Broadcast: "
                        f"{len(data.get('processing', []))} активных, "
                        f"{len(data.get('completed', []))} завершённых, "
                        f"клиентов: {manager.count}"
                    )
        except Exception as e:
            logger.error(f"[WS] Poller ошибка: {e}", exc_info=True)
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            break
        except asyncio.TimeoutError:
            pass
    
    logger.info("[WS] Poller остановлен")
