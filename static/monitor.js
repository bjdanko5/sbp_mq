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
            
            // 🏦 API банков
            if (data.bank_api) {
                renderBankApi(data.bank_api);
            }
            
            applyFilters();
        }
        
        function renderBankApi(banks) {
            const container = document.getElementById('bank-api-grid');
            const countEl = document.getElementById('bank-api-count');
            
            if (!banks || Object.keys(banks).length === 0) {
                container.innerHTML = '<div class="empty">Нет данных</div>';
                countEl.textContent = '0';
                return;
            }
            
            countEl.textContent = Object.keys(banks).length;
            
            const cards = Object.entries(banks).map(([bank, info]) => {
                const available = info.available;
                const statusClass = available ? 'bank-available' : 'bank-error';
                const color = available ? '#388e3c' : '#c62828';
                const label = available ? 'ДОСТУПЕН' : 'НЕДОСТУПЕН';
                const latency = info.latency_ms != null ? `${info.latency_ms} мс` : '—';
                const host = info.host ? `${info.host}:${info.port}` : '—';
                const errorType = info.error_type || '';
                const checked = info.checked_at ? info.checked_at.slice(11, 19) : '—';
                
                return `
                    <div class="card ${statusClass}" data-status="${statusClass}">
                        <div class="card-header">
                            <div class="card-title">
                                <span class="bank">${bank.toUpperCase()}</span>
                            </div>
                            <span class="badge" style="background:${color};">${label}</span>
                        </div>
                        <div class="card-name">${host}</div>
                        <div class="card-stats">
                            <span>⏱️ ${latency}</span>
                            ${errorType ? `<span style="color:#c62828;">🔴 ${errorType}</span>` : ''}
                        </div>
                        ${info.error ? `<div class="card-current" style="color:#c62828;">${info.error}</div>` : ''}
                        <div class="card-footer">
                            <span class="time">🕐 ${checked}</span>
                        </div>
                    </div>
                `;
            }).join('');
            
            container.innerHTML = cards;
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