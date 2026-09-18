# modules/monitor/__init__.py
"""Monitor — модуль мониторинга активных задач."""

from .data import get_monitor_data
from .render import (
    render_status_badge,
    render_callback_html,
    render_progress_card,
    render_completed_card,
    render_cards_html,
    COMPLETED_TTL_MINUTES,
)
from .templates import render_monitor_html
from .ws import (
    ConnectionManager,
    monitor_poller,
    bank_api_poller,
    manager,
    bank_api_state,
)

__all__ = [
    "get_monitor_data",
    "render_status_badge",
    "render_callback_html",
    "render_progress_card",
    "render_completed_card",
    "render_cards_html",
    "COMPLETED_TTL_MINUTES",
    "render_monitor_html",
    "ConnectionManager",
    "monitor_poller",
    "manager",
    "bank_api_poller",
    "bank_api_state",
]
