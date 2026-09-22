# Workflow: обработка ошибок

Полная карта ошибок: **от кода статуса до конкретного действия**.

> 📖 Связанные: [configuration.md → Статусы](../configuration.md#-статусы),
> [soap_integration.md](../soap_integration.md),
> [workflows/create_job.md](create_job.md),
> [workflows/callback_flow.md](callback_flow.md).

---

## 🎯 Три уровня ошибок

| Уровень | Где | Кто видит |
|---------|-----|-----------|
| **HTTP-код** | ответ API | 1С / оператор |
| **`status` в JSON** | тело ответа | 1С (парсит) |
| **`STATUS_GROUPS`** | внутри системы | `is_success()`, `is_error()`, статистика |

Три уровня — **согласованы**: `API_ERROR` → HTTP 200 + `"status": "API_ERROR"` +
группа `ERROR`.

---

## 📋 Все статусы (`config.STATUS`)

### ✅ SUCCESS (3)

| Статус | Что значит |
|--------|-----------|
| `SUCCESS` | Всё ок |
| `NO_FILES` | Нет файлов для обработки |
| `PARTIAL_SUCCESS` | Частичный успех (часть запросов ок) |

### ⚠️ WARNING (1)

| Статус | Что значит |
|--------|-----------|
| `API_OK_FILE_ERROR` | API ок, но при сохранении файла ошибка |

### ❌ ERROR (23)

**Файлы:**
- `FILE_ERROR` — общая ошибка файла
- `FILE_NOT_FOUND` — файл не найден
- `DIRECTORY_ERROR` — ошибка директории
- `FILE_MOVE_TO_PROCESSING_ERROR`
- `FILE_MOVE_TO_SENDED_ERROR`
- `FILE_MOVE_TO_GETED_ERROR`
- `FILE_MOVE_TO_STOPED_ERROR`

**JSON:**
- `JSON_ERROR`
- `JSON_READ_ERROR`
- `JSON_EMPTY`

**БД:**
- `DB_ERROR`
- `DB_SAVE_ERROR`
- `DB_CLEAR_ERROR`

**API банка:**
- `API_ERROR` — общая ошибка API
- `API_TIMEOUT` — timeout запроса
- `API_CONNECTION_ERROR` — нет соединения
- `API_SOAP_ERROR` — ошибка SOAP (обычно не тут, но есть)

**SOAP:**
- `SOAP_ERROR`
- `SOAP_CONNECTION_ERROR`
- `SOAP_AUTH_ERROR`

**Job:**
- `JOB_ALREADY_PROCESSING`
- `JOB_ALREADY_COMPLETED`
- `JOB_NOT_FOUND`

**Прочее:**
- `UNKNOWN_ERROR`
- `VALIDATION_ERROR`
- `CONFIG_ERROR`

---

## 🧭 Карта: где возникает → что делать

### На этапе `GET /create_payload_mq/...`

| Статус | Причина | HTTP | Что делать |
|--------|---------|------|-----------|
| `CONFIG_ERROR` | Неизвестный банк / база | 200 | Проверить `config.SBP_ROOT` и `BANK_CONFIG` |
| `JOB_NOT_FOUND` | Нет Job-файла в `jobs/` | 200 | `ls /sbp/mq_dev/jobs/{bank}@{base}@{job_id}.json` |
| `JSON_ERROR` | Job-файл не парсится | 200 | `cat ... \| jq .` — валидировать JSON |
| `JOB_ALREADY_PROCESSING` | (пока не реализовано) | — | — |
| `JOB_ALREADY_COMPLETED` | (пока не реализовано) | — | — |
| `VALIDATION_ERROR` | Битый запрос | 422 | Проверить параметры URL |
| `UNKNOWN_ERROR` | Что-то ещё | 200 | Смотреть `journalctl` |

### На этапе worker → банк

| Статус | Причина | Что видно | Что делать |
|--------|---------|-----------|-----------|
| `API_TIMEOUT` | Банк не отвечает (>30 сек) | `result.files[].error` | Проверить доступность банка |
| `API_CONNECTION_ERROR` | Нет TCP-соединения | то же | Проверить сеть, VPN |
| `API_ERROR` | Банк вернул 4xx/5xx | то же | Смотреть `response.text` в логах |
| `JSON_ERROR` | Файл с запросами не парсится | `result.error` | `jq .` файла |
| `DB_SAVE_ERROR` | SQLite не сохранил | `result.error` | Проверить `requests.db`, права |
| `SOAP_ERROR` | SOAP упал (в `notify_job_error`) | — (SOAP вызывается при ошибке) | Смотреть `journalctl \| grep SOAP` |
| `FILE_MOVE_*` | `shutil.move` упал | `result.files[].error` | Проверить права, наличие файла |

### На этапе callback

| Симптом | Причина | Что делать |
|---------|---------|-----------|
| `base = None` для всех | Нет `req:*` в Redis и нет в SQLite | См. [callback_flow.md → Гонка](callback_flow.md#-гонка-callback-приходит-раньше-workerа) |
| SOAP не отправился | `base = None` (не знаем базу) | См. выше |
| `SOAP_AUTH_ERROR` | Пароль 1С неверный | Проверить `config.SOAP_CONFIG["base"]` |
| `SOAP_CONNECTION_ERROR` | 1С недоступна | `telnet 192.168.10.238 80` |

---

## 🔄 Поток ошибки внутри worker'а

**`worker/job_processor.process_job`** — если **любой файл** упал:

```python
if file_result['status'] not in ['completed', 'success']:
    has_error = True
    break     # ← СТОП. Остальные файлы НЕ обрабатываются.
```

→ `result['status'] = 'error'`
→ `result.summary.error_files += 1`

**`worker/consumer.process_message`** — после `process_job`:

1. `save_result(task_id, result)` — в Redis
2. `delete_progress(task_id)`
3. **`if result['status'] != 'completed': notify_job_error(...)`** — SOAP в 1С
4. `job_manager.move_to_error(bank, base, job_id)` — файл → `jobs/error/`

**Итог:** Job-файл в `error/`, `task:*` в Redis со `status="error"`, SOAP
отправлен в 1С.

---

## 📨 Что уходит в SOAP при ошибке Job

**Формат** (см. [soap_integration.md](../soap_integration.md)):

```json
[
  {
    "jobId": "123",
    "bank": "ci",
    "base": "zkh_ursv",
    "errorMessage": "VPN timeout | 7845.json: API 500",
    "jobName": "Печать квитанций"
  }
]
```

**`errorMessage`** собирается `_collect_errors`:

1. `result["error"]` — общая ошибка Job
2. `files[].error` — по файлам, с именем файла
3. Fallback: `"Job failed"`

**Разделитель:** `" | "`.
**Максимум:** 500 символов (обрезается).

**Кто получает:** 1С по `SOAP_CONFIG["base"]["url_template"]`.

---

## 🧪 Как воспроизвести ошибку (для теста)

### 1. Ошибка банка (API)

**Способ 1:** В TEST_MODE `mockapi` вернёт ошибку, если `requestId` начинается с `err`:
```bash
echo '[{"requestId":"err-1","amount":100}]' > /sbp/mq_dev/ci/zkh_ursv/9999.json
```

**Способ 2:** Поменять `BANK_URLS["ci"]` на несуществующий URL в `.env` (или
временно в `config.py`).

### 2. Ошибка JSON

```bash
echo 'not a valid json' > /sbp/mq_dev/ci/zkh_ursv/broken.json
```

### 3. Ошибка SOAP

Поменять `SOAP_CONFIG["base"]["url_template"]` на несуществующий host.

### 4. Ошибка БД

Сделать `requests.db` недоступным:
```bash
chmod 000 requests.db
```

⚠️ Вернуть права после теста: `chmod 644 requests.db`

---

## 🆘 Типовые проблемы

### Job попал в `error/`, но SOAP не отправился

**Причины:**
1. `notify_job_error` **не бросил исключение** — упал тихо
2. `result["status"]` был `"completed"` (не `"error"`)
3. Ошибка в `_collect_errors`

**Что проверить:**
```bash
sudo journalctl -u sbp_mq-dev.service | grep -A2 "SOAP Notify"
```

Должно быть `[SOAP Notify] ❌ Ошибка ...` или `[SOAP Notify] ✅ ... отправлено`.

⚠️ **Известный баг** в `worker/consumer.py`:
`if result.get("status") != "completed":` — SOAP вызывается при **любом**
статусе ≠ `completed`. Если Job случайно в `status="processing"` (не должен,
но), SOAP уйдёт с пустым `errorMessage` (fallback `"Job failed"`).
См. [modules/worker.md → Known issues](../modules/worker.md#-known-issues-todo).

### Все Job падают с одной ошибкой

**Диагностика:**

```bash
cat /sbp/mq_dev/jobs/error/*.json | jq '.files[].error' | sort | uniq -c
```

Если массово `API_CONNECTION_ERROR` — проблема с сетью/банком.

### Job висит в `processing` (не завершается)

**Возможные причины:**
1. Worker завис на шаге HTTP (нет таймаута в `file_processor` — использует
   `config.REQUEST_TIMEOUT=30` в httpx)
2. `redis-cli -n 1 keys 'lock:*'` — есть блокировка, которая не снялась
3. Worker упал, но `lock:*` остался

**Что делать:**
```bash
# посмотреть прогресс
redis-cli -n 1 get 'progress:job_...'

# сбросить блокировку (осторожно!)
redis-cli -n 1 del 'lock:/sbp/mq_dev/ci/zkh_ursv/7845.json'

# рестарт воркеров
./sh_dev/restart_dev_workers.sh
```

### `PARTIAL_SUCCESS` — что это

Статус определён в `STATUS`, но **сейчас не выставляется** нигде в пайплайне.
Ошибка в любом файле → `status="error"` (не `partial`).

**TODO:** в `job_processor` — `if error_files > 0 and success_files > 0: status = "partial"`.

Согласовать с 1С, прежде чем включать.

### `API_OK_FILE_ERROR` (WARNING)

Файл отправлен в банк (202), но при сохранении в SQLite/Redis что-то упало.
Сейчас **не выставляется** — TODO.

---

## 📊 Мониторинг ошибок

### Карточки в `/monitor`

В карточке завершённой задачи с ошибкой видно **текст ошибки**:

```
┌────────────────────────────────────────┐
│ ci@zkh_ursv@123               [ОШИБКА] │
│ Печать квитанций                        │
│ 📁 1/2  ✅ 4  ❌ 3                      │
│ ❌ VPN timeout | 7846.json: API 500    │
│ 🔑 job_...                        📋    │
└────────────────────────────────────────┘
```

**Как посмотреть:** `http://localhost:8512/monitor` → блок «Завершённые».

### Логи ошибок

```bash
# DEV
sudo journalctl -u sbp_mq-dev.service | grep -E "ERROR|❌"
sudo journalctl -u 'sbp_mq-dev-worker*' | grep -E "ERROR|❌"

# конкретный воркер
tail -f logs/mq-worker-1_errors.log
```

---

## 🛡 Профилактика

### 1. Проверять перед деплоем

```bash
./sh_dev/test_monitor_v2.sh    # end-to-end тест
```

### 2. Мониторить `/health/detailed`

```bash
watch -n 5 'curl -s http://localhost:8511/health/detailed | jq ".status, .components.workers.active, .components.rabbitmq.queue_size"'
```

### 3. Следить за размером `error/`

```bash
ls /sbp/mq/jobs/error/ | wc -l
```

Если растёт — что-то системно сломано. **TODO:** автоматический алерт.

### 4. Чистить старые Job

```bash
curl -X DELETE "http://localhost:8511/create_payload_mq/jobs/clean?days=30"
```

### 5. Проверять `callback_count` в мониторинге

Если Job завершился успешно, но `callback_count = 0` — банк не прислал
callback. Возможные проблемы:
- Банк настроен на неправильный URL
- Файрвол блокирует
- **Для `TEST_MODE=false`** — callback от реального банка должен приходить

---

## 🔗 Связанные документы

- [configuration.md](../configuration.md#-статусы) — все `STATUS` и `STATUS_GROUPS`
- [soap_integration.md](../soap_integration.md) — SOAP при ошибках
- [modules/worker.md](../modules/worker.md) — где возникают ошибки
- [modules/mq_client.md](../modules/mq_client.md) — Redis-состояние
- [workflows/create_job.md](create_job.md) — happy path
- [workflows/callback_flow.md](callback_flow.md) — обработка callback
- [deployment.md](../deployment.md) — troubleshooting деплоя
