# routes/stats.py
from datetime import datetime
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import config
from modules.logger_config import log_error_with_context
from modules.response_utils import create_response
from modules.stats import get_stats

router = APIRouter()


def _render_base_card(base_name: str, data: dict) -> str:
    files_html = ''.join([f'<span class="file-tag">{f}</span>' for f in data.get('files', [])])
    return f"""
    <div class="base-card">
        <div class="base-name">📁 {base_name}</div>
        <div class="base-stats">
            <span>📨 Запросов: <strong>{data.get('requests', 0)}</strong></span>
            <span>✅ Успешно: <strong style="color:#2e7d32;">{data.get('success', 0)}</strong></span>
            <span>❌ Ошибок: <strong style="color:#c62828;">{data.get('errors', 0)}</strong></span>
            <span>📄 Файлов: <strong>{data.get('files_processed', 0)}</strong></span>
            <span>🔌 SOAP: <strong>{data.get('soap_calls', 0)}</strong></span>
            <span>🗑️ Удалено: <strong>{data.get('db_deletes', 0)}</strong></span>
        </div>
        <div style="margin-top: 8px;">
            <span style="font-size: 13px; color: #666;">Файлы:</span>
            {files_html if files_html else '<span class="empty">нет</span>'}
        </div>
    </div>
    """


def _render_file_item(filename: str, data: dict) -> str:
    status_class = 'success' if data.get('success') else 'error' if data.get('processed') else ''
    status_text = '✅ Успешно' if data.get('success') else '❌ Ошибка' if data.get('processed') else '⏳ В обработке'
    return f"""
    <div class="file-tag {status_class}">
        📄 {filename}
        <span style="font-weight:normal;font-size:12px;color:#666;">
            ({data.get('base', '—')}) {status_text}
        </span>
    </div>
    """


def _render_empty_message(data: dict) -> str:
    return '<p class="empty">Нет данных за выбранный период</p>'


@router.get("/stats")
async def get_statistics(
    hours: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    base: Optional[str] = None
):
    try:
        result = get_stats(hours, start, end, base)
        
        # ✅ Проверка на None
        if result is None:
            return create_response(
                status=config.STATUS["API_ERROR"],
                error="Статистика не доступна"
            )
        
        if result.get('error'):
            return create_response(
                status=config.STATUS["API_ERROR"],
                error=result['error']
            )
        
        stats = result['stats']
        response_data = {
            'period': stats['period'],
            'total': stats['total'],
            'bases': stats['bases']
        }
        
        return create_response(
            status=config.STATUS["SUCCESS"],
            message=f"Статистика за {stats['period']['hours']} часов",
            data=response_data
        )
        
    except Exception as e:
        log_error_with_context(e, "get_statistics")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error="Ошибка получения статистики"
        )


@router.get("/stats/html", response_class=HTMLResponse)
async def stats_html(
    hours: Optional[int] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    base: Optional[str] = None
):
    try:
        result = get_stats(hours, start, end, base)
        
        # ✅ Проверка на None
        if result is None:
            return HTMLResponse(
                content="<h1>Ошибка</h1><p>Статистика не доступна</p>",
                status_code=500
            )
        
        if result.get('error'):
            return HTMLResponse(
                content=f"<h1>Ошибка</h1><p>{result['error']}</p>",
                status_code=500
            )
        
        stats = result['stats']
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Статистика SBP</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; padding: 20px; color: #1a1a2e; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 30px; border-radius: 16px; margin-bottom: 30px; box-shadow: 0 4px 20px rgba(0,0,0,0.15); }}
                .header h1 {{ font-size: 32px; font-weight: 700; margin-bottom: 8px; }}
                .header p {{ color: #a8b2d1; font-size: 16px; }}
                .period {{ background: #e8eaf6; padding: 15px 20px; border-radius: 10px; margin-bottom: 25px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; }}
                .period .label {{ font-weight: 600; color: #1a1a2e; }}
                .period .value {{ color: #4a4a6a; }}
                .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }}
                .stat-card {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); text-align: center; transition: transform 0.2s; }}
                .stat-card:hover {{ transform: translateY(-4px); box-shadow: 0 4px 16px rgba(0,0,0,0.10); }}
                .stat-card .number {{ font-size: 32px; font-weight: 700; color: #1a1a2e; }}
                .stat-card .label {{ font-size: 14px; color: #666; margin-top: 4px; }}
                .stat-card .number.green {{ color: #2e7d32; }}
                .stat-card .number.red {{ color: #c62828; }}
                .stat-card .number.blue {{ color: #1565c0; }}
                .stat-card .number.purple {{ color: #6a1b9a; }}
                .stat-card .number.orange {{ color: #e65100; }}
                .section {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
                .section h2 {{ font-size: 20px; margin-bottom: 16px; color: #1a1a2e; border-bottom: 2px solid #e8eaf6; padding-bottom: 12px; }}
                .section h2 .badge {{ background: #e8eaf6; font-size: 14px; padding: 2px 12px; border-radius: 20px; color: #4a4a6a; margin-left: 10px; }}
                .base-card {{ border: 1px solid #e8eaf6; border-radius: 10px; padding: 16px 20px; margin-bottom: 12px; transition: background 0.2s; }}
                .base-card:hover {{ background: #f8f9ff; }}
                .base-card .base-name {{ font-size: 18px; font-weight: 600; color: #1a1a2e; }}
                .base-card .base-stats {{ display: flex; flex-wrap: wrap; gap: 20px; margin-top: 8px; }}
                .base-card .base-stats span {{ font-size: 14px; color: #555; }}
                .base-card .base-stats strong {{ color: #1a1a2e; }}
                .file-tag {{ display: inline-block; background: #e8eaf6; padding: 4px 12px; border-radius: 20px; font-size: 13px; color: #1a1a2e; margin: 4px 4px 0 0; }}
                .file-tag.success {{ background: #c8e6c9; color: #1b5e20; }}
                .file-tag.error {{ background: #ffcdd2; color: #b71c1c; }}
                .file-tag.processed {{ background: #bbdefb; color: #0d47a1; }}
                .empty {{ color: #999; font-style: italic; }}
                .filters {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
                .filters .filter-item {{ background: white; padding: 8px 16px; border-radius: 8px; border: 1px solid #ddd; font-size: 14px; }}
                .filters .filter-item strong {{ color: #1a1a2e; }}
                @media (max-width: 600px) {{ .stats-grid {{ grid-template-columns: repeat(2, 1fr); }} .period {{ flex-direction: column; align-items: flex-start; }} }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Статистика SBP</h1>
                    <p>Сводка по обработке файлов и запросов</p>
                </div>
                <div class="period">
                    <span><span class="label">📅 Период:</span> <span class="value">{stats['period']['from']} — {stats['period']['to']}</span></span>
                    <span><span class="label">⏱️ Всего часов:</span> <span class="value">{stats['period']['hours']} ч.</span></span>
                </div>
                <div class="filters">
                    <div class="filter-item"><strong>📁 База:</strong> {base or 'Все'}</div>
                    <div class="filter-item"><strong>📄 Файлов:</strong> {stats['total']['files_processed']}</div>
                    <div class="filter-item"><strong>📨 Запросов:</strong> {stats['total']['requests']}</div>
                </div>
                <div class="stats-grid">
                    <div class="stat-card"><div class="number blue">{stats['total']['requests']}</div><div class="label">Всего запросов</div></div>
                    <div class="stat-card"><div class="number green">{stats['total']['success']}</div><div class="label">✅ Успешно</div></div>
                    <div class="stat-card"><div class="number red">{stats['total']['errors']}</div><div class="label">❌ Ошибок</div></div>
                    <div class="stat-card"><div class="number purple">{stats['total']['files_processed']}</div><div class="label">📄 Файлов обработано</div></div>
                    <div class="stat-card"><div class="number orange">{stats['total']['soap_calls']}</div><div class="label">🔌 SOAP вызовов</div></div>
                    <div class="stat-card"><div class="number blue">{stats['total']['db_deletes']}</div><div class="label">🗑️ Удалено из БД</div></div>
                </div>
                <div class="section">
                    <h2>🏢 По базам <span class="badge">{len(stats['bases'])}</span></h2>
                    {''.join([_render_base_card(base_name, base_data) for base_name, base_data in stats['bases'].items()])}
                    {_render_empty_message(stats['bases']) if not stats['bases'] else ''}
                </div>
                <div class="section">
                    <h2>📄 По файлам <span class="badge">{len(stats['files'])}</span></h2>
                    {''.join([_render_file_item(filename, file_data) for filename, file_data in stats['files'].items()])}
                    {_render_empty_message(stats['files']) if not stats['files'] else ''}
                </div>
                <div style="text-align: center; color: #999; font-size: 13px; padding: 20px 0;">
                    SBP Service • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html)
        
    except Exception as e:
        log_error_with_context(e, "stats_html")
        return HTMLResponse(
            content=f"<h1>Ошибка</h1><p>{str(e)}</p>",
            status_code=500
        )
