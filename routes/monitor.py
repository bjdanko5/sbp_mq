# routes/monitor.py
"""
Мониторинг всех активных Job в реальном времени.

Поддерживает:
- Отображение активных задач (progress)
- Отображение завершённых задач (task) за последние 5 минут
- Отображение callback-статистики (количество + последняя ошибка)
- Фильтрацию по банку, базе, статусу, поиску
- Автообновление каждые 2 секунды
- Копирование task_id в буфер обмена
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime, timedelta
import json

import config
from modules.mq_client import mq_client
from modules.callback_stats import callback_stats
from modules.logger_config import logger
from modules.monitor import (
    get_monitor_data,
    render_cards_html,
    render_monitor_html,
    manager,
    get_bank_api_last,
)

router = APIRouter()

# ============================================================
#                   НАСТРОЙКИ
# ============================================================

COMPLETED_TTL_MINUTES = 5  # Показывать завершённые за последние 5 минут


# ============================================================
#                   ЭНДПОИНТЫ
# ============================================================

@router.get("/monitor", response_class=HTMLResponse)
async def monitor_dashboard():
    """Дашборд мониторинга всех Job."""
    return HTMLResponse(content=render_monitor_html())


@router.get("/monitor/data")
async def monitor_data():
    """API для получения данных мониторинга (JSON)."""
    data = await get_monitor_data()
    return {
        "timestamp": datetime.now().isoformat(),
        "processing_count": len(data['processing']),
        "completed_count": len(data['completed']),
        "banks": data['banks'],
        "bases": data['bases'],
        "processing": data['processing'],
        "completed": data['completed'],
    }


@router.get("/monitor/cards", response_class=HTMLResponse)
async def monitor_cards():
    """HTML с карточками (для автообновления)."""
    data = await get_monitor_data()
    html = render_cards_html(data)
    return HTMLResponse(content=html)

# ============================================================
#                   WEBSOCKET — realtime
# ============================================================

@router.websocket("/ws/monitor")
async def monitor_ws(websocket: WebSocket):
    """
    WebSocket для realtime-обновлений мониторинга.
    
    Логика:
    1. Принять соединение
    2. Отправить initial данные
    3. Держать соединение, ждать сообщений (или disconnect)
    4. При disconnect — отписаться от manager
    """
    await manager.connect(websocket)
    
    try:
        # Отправляем текущее состояние сразу (с HTML-карточками)
        data = await get_monitor_data()
        initial = {
            "timestamp": data["timestamp"],
            "processing_count": len(data["processing"]),
            "completed_count": len(data["completed"]),
            "banks": data["banks"],
            "bases": data["bases"],
            "cards_html": render_cards_html(data),
            "bank_api": get_bank_api_last(),
        }
        await websocket.send_json(initial)
        
        # Держим соединение: ждём сообщений/закрытия
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS] Ошибка в /ws/monitor: {e}", exc_info=True)
        await manager.disconnect(websocket)
