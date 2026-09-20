# SBP MQ — документация

Полная документация проекта **SBP MQ** — сервиса приёма/обработки
уведомлений СБП через RabbitMQ с мониторингом, SOAP-интеграцией с 1С
и веб-дашбордом.

> Актуально на коммит: `2b2f5aa` (ветки `dev` / `main` синхронизированы)

## 🌐 Просмотр

- **В браузере:** [`/project-docs`](http://localhost:8512/project-docs) (DEV) / [`/project-docs`](http://localhost:8511/project-docs) (PROD)
- **Swagger (API):** [`/docs`](http://localhost:8512/docs)
- **В репозитории:** файлы `docs/*.md` — единый источник
- **На GitHub:** Mermaid-диаграммы рендерятся автоматически

## 🗂 Структура документации

### Основное

| Документ | О чём |
|----------|-------|
| [architecture.md](architecture.md) | Архитектура: слои, модули, потоки данных |
| [api.md](api.md) | HTTP + WebSocket API — все эндпоинты |
| [configuration.md](configuration.md) | `config.py` + `.env`, переменные окружения |
| [deployment.md](deployment.md) | Деплой dev → prod, worktree, systemd |
| [monitoring.md](monitoring.md) | Мониторинг: WS, bank_api, `/health/detailed` |
| [soap_integration.md](soap_integration.md) | SOAP-уведомления 1С (callback + ошибки Job) |
| [git_workflow.md](git_workflow.md) | Worktree, ветки `dev`/`main`, push, GitHub |

### Модули (`modules/`)

| Документ | Модуль |
|----------|--------|
| [modules/monitor.md](modules/monitor.md) | `modules/monitor/` — дашборд, WS, bank_api |
| [modules/worker.md](modules/worker.md) | `modules/worker/` — воркеры RabbitMQ |
| [modules/mq_client.md](modules/mq_client.md) | `modules/mq_client/` — RabbitMQ + Redis |
| [modules/job_manager.md](modules/job_manager.md) | `modules/job_manager/` — Job-файлы |
| [modules/api_bank_client.md](modules/api_bank_client.md) | `modules/api_bank_client/` — клиенты банков |

### Скрипты (`scripts/`)

| Документ | Группа |
|----------|--------|
| [scripts/sh_common.md](scripts/sh_common.md) | `sh_common/` — общие скрипты |
| [scripts/sh_dev.md](scripts/sh_dev.md) | `sh_dev/` — dev-скрипты |
| [scripts/sh_prod.md](scripts/sh_prod.md) | `sh_prod/` — prod-скрипты |

### Сценарии (`workflows/`)

| Документ | Сценарий |
|----------|----------|
| [workflows/create_job.md](workflows/create_job.md) | Создание и обработка Job |
| [workflows/callback_flow.md](workflows/callback_flow.md) | Callback от банка |
| [workflows/error_handling.md](workflows/error_handling.md) | Обработка ошибок, SOAP в 1С |

## 🧭 С чего начать

- **Новый разработчик** → [architecture.md](architecture.md)
- **Оператор / деплой** → [deployment.md](deployment.md)
- **1С-разработчик** → [soap_integration.md](soap_integration.md)
- **Интегратор API** → [api.md](api.md)

## 📌 Конвенции

- Все скрипты читают переменные из `.env` через `sh_common/load_env.sh`
- Хардкод портов/путей **запрещён**
- `.env` **не в git** — настраивается вручную для DEV и PROD
- Секреты в документации **маскируются**
- Диаграммы — **Mermaid** (рендерятся на GitHub и в `/project-docs`)
- Для критичных схем дополнительно приложена ASCII-версия в `<details>`

## 🔗 Ссылки

- **Репозиторий:** `git@github.com:bjdanko5/sbp_mq.git`
- **DEV:** `http://localhost:8512` (ветка `dev`)
- **PROD:** `http://localhost:8511` (ветка `main`)
- **Swagger DEV:** `http://localhost:8512/docs`
- **Документация DEV:** `http://localhost:8512/project-docs`