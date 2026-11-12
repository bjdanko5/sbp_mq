# modules/monitor/ws.py
"""
WebSocket-менеджер + фоновый poller для мониторинга.
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Set

from fastapi import WebSocket

from modules.logger_config import logger
from .data import get_monitor_data
from .render import render_cards_html
from .bank_api import check_all_banks, BankApiHealthState


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
    #logger.info("[WS] Poller запущен")
    last_hash: str = ""
    
    while not stop_event.is_set():
        try:
            data = await get_monitor_data()
            # Сравниваем БЕЗ timestamp (он всегда новый)
            data_for_hash = {k: v for k, v in data.items() if k != 'timestamp'}
            current_hash = json.dumps(data_for_hash, sort_keys=True, default=str)
            
            if current_hash != last_hash:
                payload = {
                    "timestamp": data["timestamp"],
                    "processing_count": len(data["processing"]),
                    "completed_count": len(data["completed"]),
                    "banks": data["banks"],
                    "bases": data["bases"],
                    "cards_html": render_cards_html(data),
                }
                # ✅ Добавляем bank_api (если есть данные)
                if bank_api_last:
                    payload["bank_api"] = bank_api_last
                await manager.broadcast(payload)
                last_hash = current_hash
                
                #if manager.count > 0:
                #    logger.debug(
                #        f"[WS] Broadcast: "
                #        f"{len(data.get('processing', []))} активных, "
                #        f"{len(data.get('completed', []))} завершённых, "
                #        f"клиентов: {manager.count}"
                #    )
        except Exception as e:
            pass
            #logger.error(f"[WS] Poller ошибка: {e}", exc_info=True)
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            break
        except asyncio.TimeoutError:
            pass
    
    #logger.info("[WS] Poller остановлен")

# ============================================================
#                   BANK API POLLER (TCP)
# ============================================================
# Отдельная задача: TCP-проверка банков с backoff.
# Минимальная нагрузка: 1 SYN каждые 5 мин.

bank_api_state = BankApiHealthState()
bank_api_last: dict = {}


def get_bank_api_last() -> dict:
    """Возвращает последний статус банков (актуальный).
    
    Приоритет:
    1. bank_api_last — заполнен после первого broadcast
    2. bank_api_state.last_result — заполнен при каждом check_all_banks
    
    Это решает проблему "bank_api: {}" в первые 5-30 сек после старта.
    """
    if bank_api_last:
        return bank_api_last
    # Fallback — берём из bank_api_state (заполняется в record())
    if bank_api_state is not None:
        last = bank_api_state.last_result
        if last:
            return last
    return {}


async def bank_api_poller(stop_event: asyncio.Event) -> None:
    """TCP-проверка банков с backoff."""
    global bank_api_last
    
    #logger.info("[BankAPI] Poller запущен")
    
    # Стартовый jitter
    initial_delay = random.uniform(5, 30)
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=initial_delay)
        return
    except asyncio.TimeoutError:
        pass
    
    while not stop_event.is_set():
        try:
            result = await check_all_banks()
            bank_api_state.record(result)
            
            new_hash = json.dumps(result, sort_keys=True, default=str)
            old_hash = json.dumps(bank_api_last, sort_keys=True, default=str)
            
            if new_hash != old_hash:
                bank_api_last = result
                await manager.broadcast({
                    "timestamp": datetime.now().isoformat(),
                    "bank_api": result,
                })
                #logger.info(f"[BankAPI] Broadcast: {list(result.keys())}")
        except Exception as e:
            pass
            #logger.error(f"[BankAPI] Ошибка: {e}", exc_info=True)
        
        interval = bank_api_state.get_next_interval()
        #logger.debug(f"[BankAPI] Next check через {interval}s")
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            pass
    
    #logger.info("[BankAPI] Poller остановлен")

