# Архитектура SBP MQ

## 🎯 Назначение

Сервис принимает запросы на создание **QR-кодов СБП**, отправляет их в банк,
обрабатывает асинхронные **callback'и** от банка через RabbitMQ, ведёт Job-файлы
и отдаёт статистику/мониторинг через HTTP + WebSocket. При ошибке Job
отправляет **SOAP-уведомление в 1С**.

## 🏗 Общая схема

```mermaid
flowchart TB
    Client["1С / Клиент"] -->|HTTP| API

    subgraph API["FastAPI (sbp.py)"]
        R["routes/*<br/>HTTP + WS"]
        L["lifespan<br/>start/stop"]
        P1["poller 1<br/>monitor"]
        P2["poller 2<br/>bank_api"]
    end

    R --> MOD
    L --> MOD
    P1 --> MON
    P2 --> MON

    subgraph MOD["modules/*"]
        JM["job_manager"]
        ABC["api_bank_client"]
        SN["soap_notify"]
        MQC["mq_client"]
        MON["monitor"]
    end

    JM --> FS["Файлы Job<br/>/sbp/mq*/"]
    ABC --> BANK["API банка<br/>ci / sb / vtb"]
    MQC --> MQ["RabbitMQ"]
    MQC --> RD["Redis"]
    MON --> RD
    MON --> TCP["TCP-проверка<br/>10.0.245.20:443"]

    MQ --> W["Worker'ы<br/>3 dev / 4 prod"]
    W --> ABC
    W --> JM
    W -.->|ошибка| SN

    BANK -->|callback| CB["POST /callback"]
    CB --> JM
    CB -.->|ошибка| SN

    SN -->|SOAP| ONES["1С"]
```

<details>
<summary>ASCII-версия схемы (для терминала)</summary>

```
1С/Клиент ──HTTP──▶ FastAPI (sbp.py)
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
   routes/*       lifespan        poller ×2
       │               │               │
       └───────┬───────┴───────┬───────┘
               ▼               ▼
          modules/*       modules/monitor
       ┌───────┼───────┐       │
       ▼       ▼       ▼       ▼
   job_mgr  mq_cli  bank_cl  Redis
       │       │       │
       ▼       ▼       ▼
    Файлы   Rabbit  API банка
    Job       MQ       │
               │       │ callback
               ▼       ▼
            Worker ──▶ POST /callback
               │            │
               └── ошибка ──┴──▶ soap_notify ──SOAP──▶ 1С
```

</details>

## 🧱 Слои

### 1. HTTP / WebSocket слой (`routes/`)

- FastAPI-роутеры, по одному файлу на группу эндпоинтов
- Тонкие — бизнес-логика в `modules/`
- Регистрация — единая точка: `routes/__init__.py` → `register_routes(app)`
- **Файлы:** `main`, `health`, `create_payload`, `create_payload_mq`, `callback`,
  `monitor`, `stats`, `stop_payload`, `clear_db`, `get_payload`, `mockapi`,
  `test`, `docs`

### 2. Бизнес-логика (`modules/`)

| Модуль | Ответственность |
|--------|-----------------|
| `job_manager/` | Создание / чтение / обновление Job-файлов |
| `api_bank_client/` | HTTP-клиенты банков (ci, sb, vtb) + factory + legacy |
| `mq_client/` | RabbitMQ (publish/consume) + Redis (req→task_id, TTL) |
| `worker/` | Обработка задач из очереди |
| `monitor/` | Дашборд, WS, TCP-проверка банков |
| `soap_notify.py` | SOAP-уведомление 1С при ошибке Job |
| `common_soap.py` | Общий SOAP-клиент (zeep) |
| `callback_stats.py` | Статистика callback'ов |
| `request_storage.py` | `req:*` → `task_id` в Redis |
| `sbp_root.py` | Умные пути банков |
| `db.py` | SQLite (история) |
| `stats.py` | Агрегация статистики |
| `docs_render.py` | Рендер `docs/*.md` в HTML |
| `docs_templates.py` | HTML-шаблоны для `/project-docs` |

### 3. Данные

- **Redis** — оперативное состояние (`req:*`, счётчики, каналы WS)
- **RabbitMQ** — очередь задач (`sbp_mq_queue` / `sbp_mq_dev_queue`)
- **Файлы Job** — `/sbp/mq/jobs/` (prod), `/sbp/mq_dev/jobs/` (dev)
- **SQLite** — история callback'ов (`requests.db`)

## 🔄 Потоки данных

### 1. Создание задачи (синхронно)

```mermaid
sequenceDiagram
    participant C as Клиент
    participant R as routes/create_payload
    participant B as api_bank_client
    participant J as job_manager

    C->>R: GET /create_payload/{base}
    R->>B: запрос в банк
    B-->>R: ответ
    R->>J: сохранить Job
    J-->>R: ok
    R-->>C: ответ
```

### 2. Создание задачи (через MQ)

```mermaid
sequenceDiagram
    participant C as Клиент
    participant R as routes/create_payload_mq
    participant Q as RabbitMQ
    participant W as worker
    participant B as api_bank_client
    participant J as job_manager
    participant S as soap_notify
    participant O as 1С

    C->>R: GET /create_payload_mq/...
    R->>Q: publish
    R-->>C: job_id
    Q->>W: consume
    W->>B: запрос в банк
    B-->>W: ok / error
    W->>J: обновить Job
    alt ошибка
        W->>S: notify
        S->>O: SOAP ProcessPayload
    end
```

### 3. Callback от банка

```mermaid
sequenceDiagram
    participant B as Банк
    participant R as routes/callback
    participant J as job_manager
    participant RS as request_storage
    participant CS as callback_stats
    participant S as soap_notify
    participant O as 1С

    B->>R: POST /callback
    R->>J: обновить Job по task_id
    R->>RS: get(task_id) → req
    R->>CS: record()
    alt ошибка
        R->>S: notify
        S->>O: SOAP ProcessPayload
    end
```

### 4. Мониторинг (realtime)

```mermaid
flowchart LR
    P1["poller monitor"] --> RD["Redis"]
    P2["poller bank_api"] --> RD
    RD --> WS["modules/monitor/ws.py<br/>ConnectionManager"]
    WS -->|broadcast| C1["WS-клиент"]
    WS -->|broadcast| C2["WS-клиент"]
    WS --> HTML["/monitor HTML"]
```

### 5. Просмотр документации

```mermaid
flowchart LR
    B["Браузер"] -->|GET /project-docs/name| R["routes/docs.py"]
    R --> DR["modules/docs_render.py"]
    DR -->|читает| FS["docs/name.md"]
    DR -->|markdown-it-py| HTML["HTML"]
    R --> T["modules/docs_templates.py"]
    T -->|Mermaid CDN| B
```

## 🧬 Два окружения (worktree)

```
/var/www/html/sbp_mq       [main]   PROD  8511  Redis 0  sbp_mq_queue
/var/www/html/sbp_mq_dev   [dev]    DEV   8512  Redis 1  sbp_mq_dev_queue
```

**Один `.git`** — два рабочих дерева (`git worktree`).
Различия — **только через `.env`**. `config.py` читает переменные и
выставляет `IS_DEV` / `IS_PROD`, `WORKER_PATTERN`, `SERVICE_PREFIX` и т.д.

Подробнее — [deployment.md](deployment.md) и [git_workflow.md](git_workflow.md).

## 📦 Ключевые зависимости

- **Web:** FastAPI + uvicorn + starlette
- **WS:** `websockets==17.1`
- **MQ:** `aio-pika`
- **Redis:** `redis` (async)
- **SOAP:** `zeep` + `lxml`
- **HTTP:** `httpx` + `requests`
- **Docs:** `markdown-it-py` + `mdit-py-plugins`
- **Debug:** `debugpy` (5679 prod / 5680 dev)

## 🗂 Структура проекта (DEV)

```
sbp_mq_dev/
├── config.py                ← ЕДИНЫЙ ИСТОЧНИК конфигурации
├── sbp.py                   ← FastAPI + lifespan + 2 poller'а
├── run_worker.py            ← запуск воркера
├── run_debug.sh             ← параметризован (по имени папки)
├── deploy.sh                ← обёртка для sh_prod/deploy_to_prod.sh
├── requirements.txt
├── job_example.json         ← пример Job-файла
├── settings.json
├── .env                     ← (не в git)
├── models/
│   └── schemas.py
├── modules/
│   ├── api_bank_client/     ← клиенты банков (ci, sb, vtb) + factory + legacy
│   ├── job_manager/         ← управление Job-файлами (5 файлов)
│   ├── monitor/             ← дашборд, WS, bank_api (6 файлов)
│   ├── mq_client/           ← RabbitMQ + Redis (6 файлов)
│   ├── worker/              ← воркеры (6 файлов)
│   ├── docs_render.py       ← рендер docs/*.md → HTML
│   ├── docs_templates.py    ← HTML-шаблоны /project-docs
│   ├── soap_notify.py       ← SOAP при ошибке Job
│   └── ... (см. таблицу выше)
├── routes/
│   ├── docs.py              ← /project-docs
│   ├── health.py            ← /health, /health/detailed
│   ├── monitor.py           ← /monitor, /ws/monitor
│   ├── create_payload_mq.py ← MQ-задачи
│   └── ... (см. api.md)
├── sh_common/               ← общие скрипты
├── sh_dev/                  ← dev-скрипты
├── sh_prod/                 ← prod-скрипты
├── docs/                    ← эта документация
│   └── *.md
├── logs/                    ← не в git
├── data/                    ← не в git
└── .venv/                   ← не в git
```

## 🔗 Связанные документы

- [api.md](api.md) — все эндпоинты HTTP + WebSocket
- [configuration.md](configuration.md) — `config.py` + `.env`
- [deployment.md](deployment.md) — деплой dev → prod
- [monitoring.md](monitoring.md) — как устроен мониторинг
- [soap_integration.md](soap_integration.md) — SOAP в 1С
- [git_workflow.md](git_workflow.md) — worktree, ветки
- [modules/](modules/) — детали по модулям