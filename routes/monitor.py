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

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime, timedelta
import json

import config
from modules.mq_client import mq_client
from modules.callback_stats import callback_stats
from modules.logger_config import logger
from modules.monitor import get_monitor_data

router = APIRouter()

# ============================================================
#                   НАСТРОЙКИ
# ============================================================

COMPLETED_TTL_MINUTES = 5  # Показывать завершённые за последние 5 минут


# ============================================================
#                   HTML RENDERING
# ============================================================

def render_status_badge(status: str) -> str:
    """Возвращает HTML-бейдж статуса."""
    colors = {
        "processing": "#1976d2",
        "completed": "#388e3c",
        "error": "#c62828",
        "pending": "#f57c00",
    }
    labels = {
        "processing": "В РАБОТЕ",
        "completed": "ЗАВЕРШЕНО",
        "error": "ОШИБКА",
        "pending": "ОЖИДАНИЕ",
    }
    color = colors.get(status, "#757575")
    label = labels.get(status, status)
    return f'<span class="badge" style="background:{color};">{label}</span>'


def _render_callback_html(
    callback_count: int,
    callback_last_error: Optional[dict]
) -> str:
    """
    Формирует HTML для callback-статистики.
    
    Args:
        callback_count: Количество callback'ов (обработанных requestId)
        callback_last_error: Последняя ошибка (dict) или None
    
    Returns:
        str: HTML-блок или пустая строка
    """
    if callback_count == 0:
        return ""
    
    # ✅ Счётчик callback'ов
    html = f'''
    <div class="card-callback">
        <span class="callback-count">📞 Callback'ов: {callback_count}</span>
    </div>
    '''
    
    # ✅ Последняя ошибка (если есть)
    if callback_last_error:
        error_text = callback_last_error.get('error', '')
        error_time = callback_last_error.get('timestamp', '')
        
        # Обрезаем текст для отображения (полный — в title)
        error_short = error_text[:100] + ('...' if len(error_text) > 100 else '')
        error_time_short = error_time[:19].replace('T', ' ') if error_time else '—'
        
        html += f'''
        <div class="card-callback-error" title="{error_text}">
            ❌ {error_short}
            <span class="time">🕐 {error_time_short}</span>
        </div>
        '''
    
    return html


def render_progress_card(job: dict) -> str:
    """Карточка активной задачи."""
    task_id = job.get('task_id', '')
    bank = job.get('bank', '—')
    base = job.get('base', '—')
    job_id = job.get('job_id', '—')
    job_name = job.get('job_name', '—')
    processed = job.get('processed_files', 0)
    total = job.get('total_files', 0)
    percent = job.get('progress_percent', 0)
    current = job.get('current_file') or '—'
    success = job.get('success_files', 0)
    errors = job.get('error_files', 0)
    started = job.get('started_at', '')
    
    # ✅ Callback-статистика
    callback_count = job.get('callback_count', 0)
    callback_last_error = job.get('callback_last_error')
    
    started_short = started[:19].replace('T', ' ') if started else '—'
    
    # ✅ HTML callback-блока
    callback_html = _render_callback_html(callback_count, callback_last_error)
    
    return f'''
    <div class="card processing" data-bank="{bank}" data-base="{base}" data-status="processing">
        <div class="card-header">
            <div class="card-title">
                <span class="bank">{bank}</span>@<span class="base">{base}</span>@<span class="job-id">{job_id}</span>
            </div>
            {render_status_badge('processing')}
        </div>
        <div class="card-name">{job_name}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width:{percent}%">
                <span>{percent}%</span>
            </div>
        </div>
        <div class="card-stats">
            <span title="Обработано файлов">📁 {processed}/{total}</span>
            <span title="Успешно" class="success">✅ {success}</span>
            <span title="Ошибок" class="errors">❌ {errors}</span>
        </div>
        <div class="card-current">
            📄 Сейчас: <strong>{current}</strong>
        </div>
        {callback_html}
        <div class="card-footer">
            <div class="task-id-block">
                <span class="task-id-label">🔑</span>
                <span class="task-id-value" title="{task_id}">{task_id}</span>
                <button class="copy-btn" onclick="copyToClipboard('{task_id}')" title="Скопировать task_id">📋</button>
            </div>
            <span class="time">🕐 {started_short}</span>
        </div>
    </div>
    '''


def render_completed_card(job: dict) -> str:
    """Карточка завершённой задачи."""
    task_id = job.get('task_id', '')
    bank = job.get('bank', '—')
    base = job.get('base', '—')
    job_id = job.get('job_id', '—')
    job_name = job.get('job_name', '—')
    status = job.get('status', 'unknown')
    summary = job.get('summary', {})
    finished = job.get('finished_at', '')
    
    # ✅ Callback-статистика
    callback_count = job.get('callback_count', 0)
    callback_last_error = job.get('callback_last_error')
    
    finished_short = finished[:19].replace('T', ' ') if finished else '—'
    
    # ✅ HTML callback-блока
    callback_html = _render_callback_html(callback_count, callback_last_error)
    
    return f'''
    <div class="card {status}" data-bank="{bank}" data-base="{base}" data-status="{status}">
        <div class="card-header">
            <div class="card-title">
                <span class="bank">{bank}</span>@<span class="base">{base}</span>@<span class="job-id">{job_id}</span>
            </div>
            {render_status_badge(status)}
        </div>
        <div class="card-name">{job_name}</div>
        <div class="card-stats">
            <span title="Файлов">📁 {summary.get('processed_files', 0)}/{summary.get('total_files', 0)}</span>
            <span title="Успешных запросов" class="success">✅ {summary.get('success_requests', 0)}</span>
            <span title="Ошибок" class="errors">❌ {summary.get('error_requests', 0)}</span>
        </div>
        {callback_html}
        <div class="card-footer">
            <div class="task-id-block">
                <span class="task-id-label">🔑</span>
                <span class="task-id-value" title="{task_id}">{task_id}</span>
                <button class="copy-btn" onclick="copyToClipboard('{task_id}')" title="Скопировать task_id">📋</button>
            </div>
            <span class="time">🕐 {finished_short}</span>
        </div>
    </div>
    '''


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
    
    processing_cards = ''.join([render_progress_card(j) for j in data['processing']])
    completed_cards = ''.join([render_completed_card(j) for j in data['completed']])
    
    if not processing_cards:
        processing_cards = '<div class="empty">Нет активных задач</div>'
    
    if not completed_cards:
        completed_cards = f'<div class="empty">Нет завершённых задач за последние {COMPLETED_TTL_MINUTES} минут</div>'
    
    html = f'''
    <div class="section">
        <h2>🔥 В обработке <span class="count">{len(data["processing"])}</span></h2>
        <div class="cards-grid">
            {processing_cards}
        </div>
    </div>
    <div class="section">
        <h2>✅ Завершённые <span class="count">{len(data["completed"])}</span> <small>(за {COMPLETED_TTL_MINUTES} мин)</small></h2>
        <div class="cards-grid">
            {completed_cards}
        </div>
    </div>
    '''
    
    return HTMLResponse(content=html)


def render_monitor_html() -> str:
    """Основной HTML дашборда."""
    return '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 Мониторинг SBP</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            padding: 20px;
            color: #1a1a2e;
        }
        
        .container { max-width: 1600px; margin: 0 auto; }
        
        .header {
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            color: white;
            padding: 24px 30px;
            border-radius: 16px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }
        
        .header h1 { font-size: 28px; font-weight: 700; }
        .header .time { font-size: 14px; color: #a8b2d1; margin-top: 4px; }
        
        .header-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #a8b2d1;
        }
        
        .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4caf50;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
            transition: transform 0.2s;
        }
        
        .summary-card:hover { transform: translateY(-2px); }
        
        .summary-card .number { font-size: 36px; font-weight: 700; color: #1a1a2e; }
        .summary-card .number.green { color: #388e3c; }
        .summary-card .number.blue { color: #1976d2; }
        .summary-card .number.red { color: #c62828; }
        .summary-card .number.orange { color: #e65100; }
        .summary-card .label { font-size: 14px; color: #666; margin-top: 4px; }
        
        .filters {
            display: flex;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            background: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        
        .filters input, .filters select {
            padding: 8px 14px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            background: white;
        }
        
        .filters input { flex: 1; min-width: 200px; }
        
        .filters input:focus, .filters select:focus {
            outline: none;
            border-color: #1976d2;
            box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.1);
        }
        
        .filters button {
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            background: #1976d2;
            color: white;
            font-size: 14px;
            cursor: pointer;
        }
        
        .filters button:hover { background: #1565c0; }
        
        .section { margin-bottom: 32px; }
        
        .section h2 {
            font-size: 22px;
            margin-bottom: 16px;
            color: #1a1a2e;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .section h2 .count {
            background: #e8eaf6;
            font-size: 16px;
            padding: 2px 12px;
            border-radius: 20px;
            color: #4a4a6a;
        }
        
        .section h2 small { font-size: 13px; color: #999; font-weight: normal; }
        
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 16px;
        }
        
        .card {
            background: white;
            border-radius: 12px;
            padding: 18px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid #ccc;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.10);
        }
        
        .card.processing { border-left-color: #1976d2; }
        .card.completed { border-left-color: #388e3c; }
        .card.error { border-left-color: #c62828; }
        .card.pending { border-left-color: #f57c00; }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .card-title {
            font-size: 15px;
            font-weight: 600;
            color: #1a1a2e;
            word-break: break-all;
        }
        
        .card-title .bank { color: #1976d2; }
        .card-title .base { color: #7b1fa2; }
        .card-title .job-id { color: #e65100; }
        
        .badge {
            font-size: 10px;
            padding: 3px 10px;
            border-radius: 12px;
            color: white;
            font-weight: 700;
            text-transform: uppercase;
            white-space: nowrap;
        }
        
        .card-name {
            font-size: 14px;
            color: #555;
            margin-bottom: 12px;
            font-style: italic;
            word-break: break-word;
        }
        
        .progress-bar {
            background: #e0e0e0;
            border-radius: 8px;
            height: 24px;
            overflow: hidden;
            margin-bottom: 12px;
            position: relative;
        }
        
        .progress-fill {
            background: linear-gradient(90deg, #1976d2, #42a5f5);
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
            font-weight: 700;
            transition: width 0.5s ease;
            min-width: 40px;
        }
        
        .card-stats {
            display: flex;
            gap: 16px;
            font-size: 13px;
            color: #555;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }
        
        .card-stats .success { color: #388e3c; font-weight: 600; }
        .card-stats .errors { color: #c62828; font-weight: 600; }
        
        .card-current {
            font-size: 13px;
            color: #333;
            margin-bottom: 8px;
            padding: 6px 10px;
            background: #f5f5f5;
            border-radius: 6px;
            word-break: break-all;
        }
        
        /* ✅ Callback-статистика */
        .card-callback {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #1976d2;
            margin-bottom: 8px;
            padding: 6px 10px;
            background: #e3f2fd;
            border-radius: 6px;
            border-left: 3px solid #1976d2;
        }
        
        .callback-count {
            font-weight: 600;
        }
        
        .card-callback-error {
            font-size: 12px;
            color: #c62828;
            margin-bottom: 8px;
            padding: 6px 10px;
            background: #ffebee;
            border-radius: 6px;
            border-left: 3px solid #c62828;
            word-break: break-word;
            line-height: 1.4;
        }
        
        .card-callback-error .time {
            display: block;
            margin-top: 4px;
            color: #999;
            font-size: 11px;
        }
        
        .card-footer {
            display: flex;
            flex-direction: column;
            gap: 8px;
            font-size: 11px;
            color: #999;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #eee;
        }
        
        .task-id-block {
            display: flex;
            align-items: flex-start;
            gap: 6px;
            width: 100%;
            background: #f8f9fa;
            padding: 6px 8px;
            border-radius: 6px;
            border: 1px solid #e9ecef;
        }
        
        .task-id-label { flex-shrink: 0; }
        
        .task-id-value {
            flex: 1;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            color: #495057;
            word-break: break-all;
            overflow-wrap: anywhere;
            line-height: 1.3;
            user-select: all;
            cursor: text;
        }
        
        .copy-btn {
            flex-shrink: 0;
            background: #e9ecef;
            border: none;
            border-radius: 4px;
            padding: 3px 8px;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s, transform 0.1s;
        }
        
        .copy-btn:hover {
            background: #1976d2;
            color: white;
        }
        
        .copy-btn:active { transform: scale(0.95); }
        .copy-btn.copied { background: #4caf50; color: white; }
        
        .time {
            align-self: flex-end;
            font-size: 11px;
            color: #999;
        }
        
        .empty {
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
            background: white;
            border-radius: 12px;
            grid-column: 1 / -1;
        }
        
        .notification {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #323232;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            z-index: 9999;
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.3s, transform 0.3s;
            pointer-events: none;
        }
        
        .notification.show {
            opacity: 1;
            transform: translateY(0);
        }
        
        @media (max-width: 600px) {
            .cards-grid { grid-template-columns: 1fr; }
            .header { flex-direction: column; text-align: center; }
            .filters { flex-direction: column; }
            .filters input { min-width: 100%; }
            .notification { left: 20px; right: 20px; bottom: 20px; text-align: center; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>📊 Мониторинг SBP</h1>
                <div class="time">Обновление: <span id="update-time">—</span></div>
            </div>
            <div class="header-status">
                <span class="status-dot"></span>
                <span id="status-text">Автообновление: 2 сек</span>
            </div>
        </div>
        
        <div class="summary">
            <div class="summary-card">
                <div class="number blue" id="processing-count">0</div>
                <div class="label">🔥 В обработке</div>
            </div>
            <div class="summary-card">
                <div class="number green" id="completed-count">0</div>
                <div class="label">✅ Завершено (5 мин)</div>
            </div>
            <div class="summary-card">
                <div class="number orange" id="banks-count">0</div>
                <div class="label">🏦 Банков</div>
            </div>
            <div class="summary-card">
                <div class="number orange" id="bases-count">0</div>
                <div class="label">📁 Баз</div>
            </div>
        </div>
        
        <div class="filters">
            <input type="text" id="filter-text" placeholder="🔍 Поиск по bank@base@job_id или task_id...">
            <select id="filter-bank"><option value="">Все банки</option></select>
            <select id="filter-base"><option value="">Все базы</option></select>
            <select id="filter-status">
                <option value="">Все статусы</option>
                <option value="processing">🔥 В обработке</option>
                <option value="completed">✅ Завершено</option>
                <option value="error">❌ С ошибками</option>
            </select>
            <button onclick="resetFilters()">🔄 Сброс</button>
        </div>
        
        <div id="cards-container"><div class="empty">Загрузка...</div></div>
    </div>
    
    <script>
        const REFRESH_INTERVAL = 2000;
        
        async function updateData() {
            try {
                const resp = await fetch('/monitor/data');
                const data = await resp.json();
                
                document.getElementById('processing-count').textContent = data.processing_count;
                document.getElementById('completed-count').textContent = data.completed_count;
                document.getElementById('banks-count').textContent = data.banks.length;
                document.getElementById('bases-count').textContent = data.bases.length;
                document.getElementById('update-time').textContent = new Date().toLocaleTimeString();
                
                updateFilterOptions('filter-bank', data.banks, 'Все банки');
                updateFilterOptions('filter-base', data.bases, 'Все базы');
                
                const cardsResp = await fetch('/monitor/cards');
                const cardsHtml = await cardsResp.text();
                document.getElementById('cards-container').innerHTML = cardsHtml;
                
                applyFilters();
            } catch (e) {
                console.error('Ошибка обновления:', e);
                document.getElementById('status-text').textContent = '⚠️ Ошибка';
            }
        }
        
        function updateFilterOptions(selectId, values, placeholder) {
            const select = document.getElementById(selectId);
            const currentValue = select.value;
            const currentOptions = Array.from(select.options).slice(1).map(o => o.value);
            
            if (JSON.stringify(currentOptions) !== JSON.stringify(values)) {
                select.innerHTML = `<option value="">${placeholder}</option>`;
                values.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v;
                    opt.textContent = v;
                    select.appendChild(opt);
                });
                if (currentValue && values.includes(currentValue)) select.value = currentValue;
            }
        }
        
        function applyFilters() {
            const text = document.getElementById('filter-text').value.toLowerCase().trim();
            const bank = document.getElementById('filter-bank').value;
            const base = document.getElementById('filter-base').value;
            const status = document.getElementById('filter-status').value;
            
            let visibleCount = 0;
            
            document.querySelectorAll('.card').forEach(card => {
                const cardText = card.textContent.toLowerCase();
                const cardBank = card.dataset.bank || '';
                const cardBase = card.dataset.base || '';
                const cardStatus = card.dataset.status || '';
                
                const visible = (!text || cardText.includes(text)) 
                             && (!bank || cardBank === bank)
                             && (!base || cardBase === base)
                             && (!status || cardStatus === status);
                
                card.style.display = visible ? '' : 'none';
                if (visible) visibleCount++;
            });
            
            document.getElementById('status-text').textContent = 
                visibleCount > 0 
                    ? `Показано: ${visibleCount} (авто: 2 сек)` 
                    : 'Нет задач по фильтру';
        }
        
        function resetFilters() {
            document.getElementById('filter-text').value = '';
            document.getElementById('filter-bank').value = '';
            document.getElementById('filter-base').value = '';
            document.getElementById('filter-status').value = '';
            applyFilters();
        }
        
        async function copyToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
                showNotification('✅ task_id скопирован!');
            } catch (err) {
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                try {
                    document.execCommand('copy');
                    showNotification('✅ task_id скопирован!');
                } catch (e) {
                    showNotification('❌ Не удалось скопировать');
                }
                document.body.removeChild(textarea);
            }
        }
        
        function showNotification(message) {
            document.querySelectorAll('.notification').forEach(n => n.remove());
            
            const notification = document.createElement('div');
            notification.className = 'notification';
            notification.textContent = message;
            document.body.appendChild(notification);
            
            setTimeout(() => notification.classList.add('show'), 10);
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, 2000);
        }
        
        document.getElementById('filter-text').addEventListener('input', applyFilters);
        document.getElementById('filter-bank').addEventListener('change', applyFilters);
        document.getElementById('filter-base').addEventListener('change', applyFilters);
        document.getElementById('filter-status').addEventListener('change', applyFilters);
        
        updateData();
        setInterval(updateData, REFRESH_INTERVAL);
    </script>
</body>
</html>
'''