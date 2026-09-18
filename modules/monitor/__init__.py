# modules/monitor/__init__.py
"""Monitor — модуль мониторинга."""

from .data import get_monitor_data
from .render import (
    render_status_badge,
    render_callback_html,
    render_progress_card,
    render_completed_card,
    render_cards_html,
    COMPLETED_TTL_MINUTES,
)

__all__ = [
    "get_monitor_data",
    "render_status_badge",
    "render_callback_html",
    "render_progress_card",
    "render_completed_card",
    "render_cards_html",
    "COMPLETED_TTL_MINUTES",
]
