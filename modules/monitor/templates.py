# modules/monitor/templates.py
"""
HTML-шаблон дашборда /monitor.

Содержит полный HTML + CSS + JS.
"""


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
        // WebSocket для realtime-обновлений
        let ws = null;
        let reconnectDelay = 3000;
        
        function connectWS() {
            ws = new WebSocket(`ws://${location.host}/ws/monitor`);
            
            ws.onopen = () => {
                console.log('✅ WS подключён');
                reconnectDelay = 3000;
                document.getElementById('status-text').textContent = 'WS: подключено';
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    renderData(data);
                } catch (e) {
                    console.error('Ошибка парсинга WS:', e);
                }
            };
            
            ws.onclose = () => {
                console.log(`⚠️ WS закрыт, переподключение через ${reconnectDelay}ms`);
                document.getElementById('status-text').textContent = 'WS: переподключение...';
                setTimeout(connectWS, reconnectDelay);
                reconnectDelay = Math.min(reconnectDelay * 1.5, 30000);
            };
            
            ws.onerror = (err) => {
                console.error('WS ошибка:', err);
                document.getElementById('status-text').textContent = 'WS: ошибка';
            };
        }
        
        function renderData(data) {
            // Счётчики
            document.getElementById('processing-count').textContent = data.processing_count;
            document.getElementById('completed-count').textContent = data.completed_count;
            document.getElementById('banks-count').textContent = data.banks.length;
            document.getElementById('bases-count').textContent = data.bases.length;
            document.getElementById('update-time').textContent = new Date(data.timestamp).toLocaleTimeString();
            
            // Фильтры
            updateFilterOptions('filter-bank', data.banks, 'Все банки');
            updateFilterOptions('filter-base', data.bases, 'Все базы');
            
            // Карточки (HTML от сервера)
            document.getElementById('cards-container').innerHTML = data.cards_html;
            
            applyFilters();
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
                    ? `Показано: ${visibleCount} (WS)` 
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
        
        // Запуск WebSocket
        connectWS();
    </script>
</body>
</html>
'''