# modules/monitor/templates.py
"""
HTML-шаблон дашборда /monitor.

Читает templates/monitor.html из корня проекта.
CSS/JS подключены через /static/ (см. sbp.py — app.mount).
"""
from pathlib import Path

# Корень проекта (sbp_mq_dev/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
HTML_FILE = BASE_DIR / "templates" / "monitor.html"


def render_monitor_html() -> str:
    """Читает HTML дашборда из templates/monitor.html."""
    return HTML_FILE.read_text(encoding="utf-8")
