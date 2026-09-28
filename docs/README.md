# SBP MQ — документация

Полная документация проекта **SBP MQ** — сервиса приёма/обработки
уведомлений СБП через RabbitMQ с мониторингом, SOAP-интеграцией с 1С
и веб-дашбордом.

> Актуально на коммит: `d9e672a` (ветки `dev` / `main` синхронизированы)

## 🌐 Просмотр

| Способ | Ссылка |
|--------|--------|
| **В браузере (DEV)** | `http://localhost:8512/project-docs` |
| **В браузере (PROD)** | `http://localhost:8510/project-docs` |
| **Swagger (API)** | `http://localhost:8512/docs` |
| **В репозитории** | файлы `docs/*.md` — **единый источник** |
| **На GitHub** | Mermaid-диаграммы рендерятся автоматически |

Диаграммы — **Mermaid** (рендерятся на GitHub и в `/project-docs`).
Для критичных схем — ASCII-версия в `<details>`.

## 🗂 Структура документации

### 📖 Основное

| Документ | О чём |
|----------|-------|
| [architecture.md](architecture.md) | Архитектура: слои, модули, потоки данных |
| [api.md](api.md) | HTTP + WebSocket API — все эндпоинты |
| [configuration.md](configuration.md) | `config.py` + `.env`, переменные, статусы |
| [deployment.md](deployment.md) | Деплой dev → prod, worktree, systemd |
| [monitoring.md](monitoring.md) | Мониторинг: WS, bank_api, `/health/detailed` |
| [soap_integration.md](soap_integration.md) | SOAP-уведомления 1С (callback + ошибки Job) |
| [git_workflow.md](git_workflow.md) | Worktree, ветки `dev`/`main`, push, SSH |
| [pitfalls.md](pitfalls.md) | 🪤 **Грабли проекта** — неочевидные механизмы |

### 🧩 Модули (`modules/`)

| Документ | Модуль |
|----------|--------|
| [modules/monitor.md](modules/monitor.md) | `modules/monitor/` — дашборд, WS, bank_api, templates |
| [modules/worker.md](modules/worker.md) | `modules/worker/` — base, consumer, processors |
| [modules/mq_client.md](modules/mq_client.md) | `modules/mq_client/` — publisher, locker, storage |
| [modules/job_manager.md](modules/job_manager.md) | `modules/job_manager/` — Job-файлы, жизненный цикл |
| [modules/api_bank_client.md](modules/api_bank_client.md) | `modules/api_bank_client/` — factory, банки, legacy |

### 📜 Скрипты (`scripts/`)

| Документ | Группа |
|----------|--------|
| [scripts/sh_common.md](scripts/sh_common.md) | `sh_common/` — общие (load_env, service_start) |
| [scripts/sh_dev.md](scripts/sh_dev.md) | `sh_dev/` — DEV (restart, reset, тесты) |
| [scripts/sh_prod.md](scripts/sh_prod.md) | `sh_prod/` — PROD (deploy, backup, restore) |

### 🔄 Сценарии (`workflows/`)

| Документ | Сценарий |
|----------|----------|
| [workflows/create_job.md](workflows/create_job.md) | Создание и обработка Job (сквозной путь) |
| [workflows/callback_flow.md](workflows/callback_flow.md) | Callback от банка → SOAP в 1С |
| [workflows/error_handling.md](workflows/error_handling.md) | Обработка ошибок: статусы → действия |

## 🪤 Грабли проекта

**Неочевидные механизмы**, которые приводят к багам или потере времени:

👉 **[docs/pitfalls.md](pitfalls.md)**

Примеры:
- `deploy.sh` сам рестартует воркеры (через `run_debug.sh`) — ручной рестарт **не нужен**
- Pylance: `Optional[X]` в сигнатурах → early-return или `assert`
- `move_to_error` **не снимает лок** в Redis
- `time.sleep` в `async def` блокирует event loop (abort не сработает)
- `soap_notify` 404 на WSDL в DEV — **ожидаемо** для тестовых баз (`zkh_ursv2`, `zkh_ursv3`)

**Правило:** добавляй запись в `pitfalls.md` **в момент**, когда наступил на грабли.

## 🧭 С чего начать

| Роль | Куда |
|------|------|
| **Новый разработчик** | [architecture.md](architecture.md) → [modules/](modules/) → [pitfalls.md](pitfalls.md) |
| **Оператор / деплой** | [deployment.md](deployment.md) → [scripts/sh_prod.md](scripts/sh_prod.md) → [pitfalls.md](pitfalls.md) |
| **1С-разработчик** | [soap_integration.md](soap_integration.md) → [api.md](api.md#post-callback) |
| **Интегратор API** | [api.md](api.md) → [workflows/](workflows/) |
| **Дежурный** | [workflows/error_handling.md](workflows/error_handling.md) → [monitoring.md](monitoring.md) → [pitfalls.md](pitfalls.md) |

## 📊 Сводка

| Раздел | Файлов | Строк |
|--------|--------|-------|
| Основное | 8 | ~3 700 |
| Модули | 5 | ~2 800 |
| Скрипты | 3 | ~1 500 |
| Сценарии | 3 | ~2 200 |
| **Всего** | **19** | **~10 200** |

## 📌 Конвенции

- Все скрипты читают переменные из `.env` через `sh_common/load_env.sh`
- Хардкод портов / путей **запрещён** в скриптах
- `.env` **не в git** — настраивается вручную для DEV и PROD
- Секреты в документации **маскируются**
- Диаграммы — **Mermaid**, для критичных схем — ASCII в `<details>`
- Ссылки на другие документы — **относительные** `[text](file.md)` —
  работают и на GitHub, и в `/project-docs`

## 🔗 Ссылки

| Что | Где |
|-----|-----|
| **Репозиторий** | `git@github.com:bjdanko5/sbp_mq.git` |
| **DEV** | `http://localhost:8512` (ветка `dev`) |
| **PROD** | `http://localhost:8510` (ветка `main`) |
| **Swagger DEV** | `http://localhost:8512/docs` |
| **Документация DEV** | `http://localhost:8512/project-docs` |
| **Мониторинг DEV** | `http://localhost:8512/monitor` |

## 🔧 Обновление документации

### Как добавить новый `.md`

1. Создать файл в нужной подпапке `docs/`:
   ```bash
   nano docs/modules/new_module.md