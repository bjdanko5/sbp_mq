# Конфигурация SBP MQ

## 🎯 Единый источник

**`config.py`** — единая точка конфигурации. Читает переменные из **`.env`**
через `parse_*_env()`, выставляет разумные значения по умолчанию.

```
.env ──▶ config.py ──▶ константы ──▶ используется в коде
         (парсинг)
```

- **`.env`** — **не в git** (`.gitignore`), свой для DEV и PROD
- **`config.py`** — **в git**, содержит только дефолты

### Парсеры

| Функция | Что делает |
|---------|-----------|
| `parse_bool_env(name, default)` | `true/1/yes/on/y/t` → `True`; `false/0/no/off/n/f` → `False` |
| `parse_int_env(name, default)` | `int(value)`, при ошибке → default |
| `parse_float_env(name, default)` | `float(value)`, при ошибке → default |
| `parse_str_env(name, default)` | `os.getenv(name, default)` |

---

## 🗂 Определение окружения

Окружение **определяется автоматически** по имени папки:

```python
PROJECT_NAME = os.path.basename(BASE_DIR)   # sbp_mq_dev или sbp_mq
IS_DEV  = "_dev" in PROJECT_NAME
IS_PROD = not IS_DEV
```

Производные:

| Константа | DEV | PROD |
|-----------|-----|------|
| `PROJECT_NAME` | `sbp_mq_dev` | `sbp_mq` |
| `IS_DEV` | `True` | `False` |
| `IS_PROD` | `False` | `True` |
| `SERVICE_PREFIX` | `sbp_mq-dev` | `sbp_mq` |
| `WORKER_PATTERN` | `sbp_mq-dev-worker` | `sbp_mq-worker` |
| `SERVER_SERVICE` | `sbp_mq-dev.service` | `sbp_mq.service` |

**Используется в:**
- `sbp.py` — лог о воркерах при старте
- `routes/health.py` — `_check_workers()` через `WORKER_PATTERN`
- `config.SBP_ROOT` — определяет, куда складывать Job-файлы

> ⚠️ **Важно:** переименование папки ломает окружение. `sbp_mq_dev` → `sbp_mq_dev2`
> → станет DEV-ом (есть `_dev`) ✓. А `sbp_mq2` → станет PROD ✓. Но `sbp_mq_dev_prod`
> → тоже DEV — следить за именами.

---

## 📂 Пути

| Константа | .env | Default | Смысл |
|-----------|------|---------|-------|
| `BASE_DIR` | — | `dirname(config.py)` | корень проекта |
| `DB_FILE` | — | `BASE_DIR/requests.db` | SQLite (история callback'ов) |
| `SBP_ROOT4MQ` | `SBP_ROOT4MQ` | `/sbp/mq` | корень данных SBP |
| `SBP_ROOT4JOBS` | — | `SBP_ROOT4MQ/jobs` | Job-файлы |
| `LOG_DIR` | `LOG_DIR` | `BASE_DIR/logs` | логи приложения |
| `DATA_DIR` | `DATA_DIR` | `BASE_DIR/data` | рантайм-данные |

**DEV:** `SBP_ROOT4MQ=/sbp/mq_dev`, `LOG_DIR=.../sbp_mq_dev/logs`
**PROD:** `SBP_ROOT4MQ=/sbp/mq`, `LOG_DIR=.../sbp_mq/logs`

---

## 🧠 `SBP_ROOT` — «умные пути» банков

Создаётся через `create_sbp_root(SBP_ROOT4MQ, default_bank="ci")` из
`modules/sbp_root.py`.

**Идея:** у каждого банка — **своя подпапка** внутри `SBP_ROOT4MQ/jobs/`:

```
/sbp/mq_dev/jobs/
├── ci/
│   ├── zkh_ursv/
│   │   ├── 123.json       ← pending
│   │   └── 124.json
│   └── ...
├── sb/
└── vtb/
```

Доступ:

```python
config.SBP_ROOT["ci"]                   # → SBPPath для ci
config.SBP_ROOT["ci"]["zkh_ursv"]      # → путь для базы zkh_ursv
config.SBP_ROOT_STR                     # → str(SBP_ROOT) для логов
```

**`default_bank="ci"`** — куда складывать, если банк не указан.

Проверить доступные банки:

```python
import config
list(config.SBP_ROOT.keys())      # ['ci', 'sb', 'vtb']
```

---

## 🏦 Банки

### `BANK_URLS`

```python
BANK_URLS = {
    "ci":  "https://10.0.245.20:443/ivolga-api/qr-code"
           if not TEST_MODE
           else f"http://localhost:{SBP_MQ_PORT}/mockapi/qr-code",
    "sb":  "https://sb.api.sberbank.ru/...",   # TODO
    "vtb": "https://api.vtb.ru/..."            # TODO
}
```

⚠️ **Логика `ci`:** если `TEST_MODE=true` (DEV), URL автоматически переключается
на **локальный `/mockapi/qr-code`** — запросы идут «в себя», банк не дёргается.

### `BANK_CONFIG`

```python
BANK_CONFIG = {
    "ci": {
        "name": "Центринвест",
        "url": BANK_URLS["ci"],
        "sbp_root": SBP_ROOT["ci"],
        "callback_url": CALLBACK_URLS["ci"],
        "verify_ssl": False,
        "api_class": "BankCI",
    },
    "sb": {
        "name": "Сбербанк",
        "url": BANK_URLS["sb"],
        "sbp_root": SBP_ROOT["sb"],
        "callback_url": CALLBACK_URLS["sb"],
        "verify_ssl": True,
        "api_class": "BankSB",
    },
    "vtb": {
        "name": "ВТБ",
        "url": BANK_URLS["vtb"],
        "sbp_root": SBP_ROOT["vtb"],
        "callback_url": CALLBACK_URLS["vtb"],
        "verify_ssl": True,
        "api_class": "BankVTB",
    },
}
```

`api_class` — имя класса в `modules/api_bank_client/` (factory создаёт нужный).

### `CALLBACK_URLS`

```python
CALLBACK_URLS = {
    "ci":  "/callback",
    "sb":  "/callback_sb",
    "vtb": "/callback_vtb",
}
```

⚠️ **Сейчас реализован только `/callback`** (см. `routes/callback.py`).
`/callback_sb` и `/callback_vtb` — **TODO**, пока не реализованы.

### `check_all_banks` и заглушки

В `/health/detailed` и `/monitor` банки с `...` в URL **пропускаются**:

```python
if "..." in url:
    logger.debug(f"[BankAPI] Пропуск {bank}: URL-заглушка")
    continue
```

Практически: `ci` — рабочий, `sb` и `vtb` — заглушки, в мониторинге не отображаются.

---

## 🌐 HTTP API банка

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `REQUEST_TIMEOUT` | `30.0` | ✅ | timeout запроса к банку (сек) |
| `DELAY_BETWEEN_REQUESTS` | `1` | ✅ | пауза между запросами (сек) |
| `VERIFY_SSL` | `False` | ✅ | проверять SSL-сертификат банка |
| `DEFAULT_HEADERS` | `{"Content-Type": "application/json"}` | — | заголовки по умолчанию |

⚠️ **`VERIFY_SSL=False`** по умолчанию — банк `ci` использует **самоподписанный**
сертификат, лежащий на `10.0.245.20:443`. Отключение проверки — **осознанное
решение** для внутренней сети. В проде **не включать без необходимости**.

---

## 📨 SOAP (1С)

```python
SOAP_CONFIG = {
    "default": { ... },
    "base": {
        "url_template": "http://192.168.10.238/{base}/ws/WebLK?wsdl",
        "username": "Администратор",
        "password": "***",   # ⚠️ см. ниже
    }
}
```

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `SOAP_TIMEOUT` | `60` | ✅ | общий timeout zeep-транспорта |
| `SOAP_OPERATION_TIMEOUT` | `30` | ✅ | timeout одной операции |
| `SOAP_MAX_RETRIES` | `3` | ✅ | кол-во попыток при `RequestException` |
| `SOAP_RETRY_DELAY` | `1` | ✅ | пауза между попытками (сек) |

Подробнее — [soap_integration.md](soap_integration.md).

> 🛡️ **TODO:** `SOAP_CONFIG["base"]["password"]` захардкожен в `config.py`.
> Вынести в `.env` (`SOAP_PASSWORD`) — задача отложена.

---

## 🐇 RabbitMQ

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `RABBITMQ_HOST` | `localhost` | ✅ | хост |
| `RABBITMQ_PORT` | `5672` | ✅ | порт |
| `RABBITMQ_USER` | `guest` | ✅ | логин |
| `RABBITMQ_PASSWORD` | `guest` | ✅ | пароль |
| `RABBITMQ_QUEUE` | `sbp_mq_queue` | ✅ | имя очереди |

**DEV:** `RABBITMQ_QUEUE=sbp_mq_dev_queue`
**PROD:** `RABBITMQ_QUEUE=sbp_mq_queue`

⚠️ **Разные очереди** — чтобы DEV и PROD не забирали задачи друг у друга.

---

## 📦 Redis

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `REDIS_HOST` | `localhost` | ✅ | хост |
| `REDIS_PORT` | `6379` | ✅ | порт |
| `REDIS_DB` | `0` | ✅ | номер БД (0–15) |
| `REDIS_TTL` | `3600` | ✅ | TTL ключей по умолчанию (сек) |
| `REQUEST_TTL` | `3600` | ✅ | TTL связки `req:* → task_id` |

**DEV:** `REDIS_DB=1`, **PROD:** `REDIS_DB=0`

⚠️ **Разные БД** — чтобы DEV и PROD не пересекались по ключам.

`REQUEST_TTL=3600` — callback обычно приходит за 1–5 мин, 1 час — с запасом.

---

## 🌐 Веб-сервер

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `SBP_MQ_PORT` | `8511` | ✅ | HTTP-порт |
| `SBP_MQ_DEBUG_PORT` | `5679` | ✅ | порт debugpy |

**DEV:** `8512` / `5680`, **PROD:** `8511` / `5679`

`config.py` также выставляет:

```python
os.environ.setdefault('PYTHONUNBUFFERED', '1')
os.environ.setdefault('PYDEVD_USE_FRAME_EVAL', 'NO')
```

- `PYTHONUNBUFFERED=1` — не буферизовать stdout (логи сразу)
- `PYDEVD_USE_FRAME_EVAL=NO` — отключить frame eval в debugpy (стабильнее)

---

## 🧪 Режимы

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `TEST_MODE` | `True` | ✅ | `true` — моки банка; `false` — реальный банк |
| `DEBUG_VERBOSE` | `True` | ✅ | подробные логи |

**DEV:** `TEST_MODE=true`, **PROD:** `TEST_MODE=false`

⚠️ **`TEST_MODE` по умолчанию `True`** — на проде **обязательно** указать
`TEST_MODE=false` в `.env`, иначе запросы пойдут в мок.

`TEST_MODE=true` переключает `BANK_URLS["ci"]` на локальный `/mockapi/qr-code`.

---

## 📊 Логирование

| Переменная | Default | .env | Смысл |
|------------|---------|------|-------|
| `LOG_DIR` | `BASE_DIR/logs` | ✅ | директория логов |
| `LOG_NAME` | — | ✅ (через systemd) | имя лога |
| `STATS_LOG_FILE` | `"sbp.log"` | — | имя файла статистики |
| `DEBUG_VERBOSE` | `True` | ✅ | уровень детализации |

`LOG_NAME` устанавливается **в systemd-юните** через `Environment=`:

```ini
Environment="LOG_NAME=sbp-dev"    # DEV
Environment="LOG_NAME=sbp"        # PROD
```

---

## 🚦 Статусы

`STATUS` — **словарь констант** (строки). Используется в `create_response()`
и в логике модулей.

### Группы

| Группа | Кол-во | Примеры |
|--------|--------|---------|
| **SUCCESS** | 3 | `SUCCESS`, `NO_FILES`, `PARTIAL_SUCCESS` |
| **ERROR** | 23 | `FILE_ERROR`, `DB_ERROR`, `API_ERROR`, `SOAP_ERROR`, `JOB_NOT_FOUND`, … |
| **WARNING** | 1 | `API_OK_FILE_ERROR` |

### Полный `STATUS`

**Успех:**
- `SUCCESS` — всё ок
- `NO_FILES` — нет файлов для обработки
- `PARTIAL_SUCCESS` — частичный успех

**Файлы:**
- `FILE_ERROR`, `FILE_NOT_FOUND`, `DIRECTORY_ERROR`
- `FILE_MOVE_TO_PROCESSING_ERROR`, `FILE_MOVE_TO_SENDED_ERROR`,
  `FILE_MOVE_TO_GETED_ERROR`, `FILE_MOVE_TO_STOPED_ERROR`

**JSON:**
- `JSON_ERROR`, `JSON_READ_ERROR`, `JSON_EMPTY`

**БД:**
- `DB_ERROR`, `DB_SAVE_ERROR`, `DB_CLEAR_ERROR`

**API банка:**
- `API_ERROR`, `API_TIMEOUT`, `API_CONNECTION_ERROR`, `API_OK_FILE_ERROR` (WARNING)
- `API_SOAP_ERROR`

**SOAP:**
- `SOAP_ERROR`, `SOAP_CONNECTION_ERROR`, `SOAP_AUTH_ERROR`

**Job:**
- `JOB_ALREADY_PROCESSING`, `JOB_ALREADY_COMPLETED`, `JOB_NOT_FOUND`

**Прочее:**
- `UNKNOWN_ERROR`, `VALIDATION_ERROR`, `CONFIG_ERROR`

### Функции

```python
config.is_success("SUCCESS")            # True
config.is_error("API_ERROR")            # True
config.is_warning("API_OK_FILE_ERROR")  # True
config.get_status_group("DB_ERROR")     # "ERROR"
config.get_response_status("SUCCESS")   # "SUCCESS"
```

### `STATUS_GROUPS`

```python
STATUS_GROUPS = {
    "SUCCESS": [STATUS["SUCCESS"], STATUS["NO_FILES"], STATUS["PARTIAL_SUCCESS"]],
    "ERROR":   [...23 статуса...],
    "WARNING": [STATUS["API_OK_FILE_ERROR"]],
}
```

Используется в `stats.py`, `job_manager`, `callback_stats`.

---

## 🔀 DEV vs PROD — таблица `.env`

| Переменная | DEV | PROD |
|------------|-----|------|
| `SBP_MQ_PORT` | `8512` | `8511` |
| `SBP_MQ_DEBUG_PORT` | `5680` | `5679` |
| `SBP_ROOT4MQ` | `/sbp/mq_dev` | `/sbp/mq` |
| `LOG_DIR` | `/var/www/html/sbp_mq_dev/logs` | `/var/www/html/sbp_mq/logs` |
| `DATA_DIR` | `/var/www/html/sbp_mq_dev/data` | `/var/www/html/sbp_mq/data` |
| `LOG_NAME` | `sbp-dev` (systemd) | `sbp` (systemd) |
| `REDIS_DB` | `1` | `0` |
| `RABBITMQ_QUEUE` | `sbp_mq_dev_queue` | `sbp_mq_queue` |
| `TEST_MODE` | `true` | `false` |
| `DEBUG_VERBOSE` | `true` | `false` |
| `DEV_DIR` | `/var/www/html/sbp_mq_dev` | `/var/www/html/sbp_mq_dev` |
| `PROD_DIR` | `/var/www/html/sbp_mq` | `/var/www/html/sbp_mq` |

`DEV_DIR` и `PROD_DIR` **одинаковые в обоих `.env`** — они абсолютные, нужны
скриптам (`sh_common/load_env.sh`, `sh_prod/*`) для навигации.

---

## 📝 `.env.example` (шаблон)

Для нового разработчика / нового окружения — **создать `.env`** со следующим
содержимым (и заполнить своими значениями):

```bash
# ============================================================
# СЕРВЕР
# ============================================================
SBP_MQ_PORT=8512
SBP_MQ_DEBUG_PORT=5680

# ============================================================
# РЕЖИМ
# ============================================================
TEST_MODE=true
DEBUG_VERBOSE=true

# ============================================================
# ПУТИ ПРОЕКТОВ (используются в sh_common/, sh_prod/)
# ============================================================
DEV_DIR=/var/www/html/sbp_mq_dev
PROD_DIR=/var/www/html/sbp_mq

# ============================================================
# ПУТИ
# ============================================================
SBP_ROOT4MQ=/sbp/mq_dev
LOG_DIR=/var/www/html/sbp_mq_dev/logs
DATA_DIR=/var/www/html/sbp_mq_dev/data
LOG_NAME=sbp-dev

# ============================================================
# REDIS
# ============================================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1
REDIS_TTL=3600

# ============================================================
# RABBITMQ
# ============================================================
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_QUEUE=sbp_mq_dev_queue

# ============================================================
# REQUEST STORAGE
# ============================================================
REQUEST_TTL=3600

# ============================================================
# HTTP API БАНКА
# ============================================================
REQUEST_TIMEOUT=30.0
DELAY_BETWEEN_REQUESTS=1
VERIFY_SSL=false

# ============================================================
# SOAP (1С)
# ============================================================
SOAP_TIMEOUT=60
SOAP_OPERATION_TIMEOUT=30
SOAP_MAX_RETRIES=3
SOAP_RETRY_DELAY=1
# SOAP_PASSWORD=***    ← TODO: вынести после рефакторинга

# ============================================================
# ДОПОЛНИТЕЛЬНО
# ============================================================
PYTHONUNBUFFERED=1
PYDEVD_USE_FRAME_EVAL=NO
```

Для PROD — заменить значения на продовые (`8511`, `false`, `/sbp/mq`, `0`,
`sbp_mq_queue`, `sbp`).

---

## 🛡️ Секреты

### Что **нельзя** коммитить в `config.py`

- Пароли SOAP (`SOAP_CONFIG["base"]["password"]`)
- Пароли БД / Redis / RabbitMQ
- Токены, ключи

### Что **можно** (в `.env`, не в git)

Все секреты — **только в `.env`**. `.gitignore` уже включает `.env`.

### Проверка `.gitignore`

```bash
grep -E "^\.env|/\.env" .gitignore
# должно быть: .env
```

### Что делать, если секрет попал в коммит

1. **Сменить секрет** (пароль, токен) — считать скомпрометированным
2. **Убрать из истории:** см. [git_workflow.md → Случайно закоммичен .env](git_workflow.md#-случайно-закоммичен-env-или-пароль)

### ⚠️ Текущие TODO по секретам

- **`SOAP_CONFIG["base"]["password"]`** — захардкожен в `config.py`.
  Вынести в `.env` (`SOAP_PASSWORD`). **Отложено** до стабилизации.

---

## 🔍 Отладка конфигурации

### Посмотреть текущие значения

```python
import config
print(config.IS_DEV, config.SBP_MQ_PORT, config.REDIS_DB)
print(config.RABBITMQ_QUEUE, config.TEST_MODE)
print(list(config.SBP_ROOT.keys()))    # доступные банки
```

### Что реально загрузилось из `.env`

```python
import os
print(os.getenv("RABBITMQ_QUEUE"))
print(os.getenv("REDIS_DB"))
print(os.getenv("TEST_MODE"))
```

### Проверить, что `.env` виден процессу

```bash
# через systemd
sudo systemctl show sbp_mq-dev.service --property=EnvironmentFiles
# EnvironmentFiles=/var/www/html/sbp_mq_dev/.env (ignore_errors=no)

# переменные конкретного процесса
sudo cat /proc/$(pgrep -f 'uvicorn.*8512' | head -1)/environ | tr '\0' '\n' | sort
```

### Найти все `parse_*_env`

```bash
grep -E "parse_(int|float|str|bool)_env" config.py
```

---

## 🔗 Связанные документы

- [architecture.md](architecture.md) — как `config.py` встроен в слои
- [deployment.md](deployment.md) — `systemd EnvironmentFile=.env`
- [soap_integration.md](soap_integration.md) — секция SOAP
- [git_workflow.md](git_workflow.md) — `.gitignore`, работа с секретами