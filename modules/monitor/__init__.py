# modules/monitor/__init__.py
"""
Monitor — модуль мониторинга активных задач.

Разбит на подмодули:
- data.py — сбор данных из Redis
- render.py — HTML-рендеринг (карточки)
- templates.py — HTML-шаблон дашборда
- ws.py — WebSocket + poller
"""

from .data import get_monitor_data

__all__ = [
    "get_monitor_data",
]
