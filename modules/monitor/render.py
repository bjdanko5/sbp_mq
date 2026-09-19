# modules/monitor/render.py
"""
HTML-рендеринг карточек мониторинга.
"""

from typing import Optional


COMPLETED_TTL_MINUTES = 5


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


def render_callback_html(
    callback_count: int,
    callback_last_error: Optional[dict]
) -> str:
    """Формирует HTML для callback-статистики."""
    if callback_count == 0:
        return ""
    
    html = f'''
    <div class="card-callback">
        <span class="callback-count">📞 Callback'ов: {callback_count}</span>
    </div>
    '''
    
    if callback_last_error:
        error_text = callback_last_error.get('error', '')
        error_time = callback_last_error.get('timestamp', '')
        
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
    
    callback_count = job.get('callback_count', 0)
    callback_last_error = job.get('callback_last_error')
    
    started_short = started[:19].replace('T', ' ') if started else '—'
    callback_html = render_callback_html(callback_count, callback_last_error)
    
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


def _collect_job_error(job: dict) -> str:
    """
    Собирает текст ошибки из job.
    
    1. job["error"] — если есть
    2. files[].error — с именем файла
    3. "" — если ничего
    """
    errors = []
    
    general = job.get("error")
    if general:
        errors.append(str(general))
    
    for f in job.get("files", []):
        if f.get("error"):
            filename = f.get("filename", "unknown")
            errors.append(f"{filename}: {f['error']}")
    
    if not errors:
        return ""
    
    text = " | ".join(errors)
    if len(text) > 300:
        text = text[:297] + "..."
    return text


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
    
    callback_count = job.get('callback_count', 0)
    callback_last_error = job.get('callback_last_error')
    
    finished_short = finished[:19].replace('T', ' ') if finished else '—'
    callback_html = render_callback_html(callback_count, callback_last_error)
    
    # ✅ Собираем ошибку
    error_text = _collect_job_error(job)
    error_html = f'<div class="card-error">❌ {error_text}</div>' if error_text else ''
    
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
        {error_html}
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


def render_cards_html(data: dict) -> str:
    """HTML обоих списков карточек."""
    processing_cards = ''.join([render_progress_card(j) for j in data['processing']])
    completed_cards = ''.join([render_completed_card(j) for j in data['completed']])
    
    if not processing_cards:
        processing_cards = '<div class="empty">Нет активных задач</div>'
    
    if not completed_cards:
        completed_cards = f'<div class="empty">Нет завершённых задач за последние {COMPLETED_TTL_MINUTES} минут</div>'
    
    return f'''
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
