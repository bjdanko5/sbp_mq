# SBP MQ — документация

Полная документация проекта **SBP MQ** — сервиса приёма/обработки
уведомлений СБП через RabbitMQ с мониторингом, SOAP-интеграцией с 1С
и веб-дашбордом.

> Актуально на коммит: `bd3b8a7` (ветки `dev` / `main` синхронизированы)

## 🌐 Просмотр

| Способ | Ссылка |
|--------|--------|
| **В браузере (DEV)** | `http://localhost:8512/project-docs` |
| **В браузере (PROD)** | `http://localhost:8511/project-docs` |
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

## 🧭 С чего начать

| Роль | Куда |
|------|------|
| **Новый разработчик** | [architecture.md](architecture.md) → [modules/](modules/) |
| **Оператор / деплой** | [deployment.md](deployment.md) → [scripts/sh_prod.md](scripts/sh_prod.md) |
| **1С-разработчик** | [soap_integration.md](soap_integration.md) → [api.md](api.md#post-callback) |
| **Интегратор API** | [api.md](api.md) → [workflows/](workflows/) |
| **Дежурный** | [workflows/error_handling.md](workflows/error_handling.md) → [monitoring.md](monitoring.md) |

## 📊 Сводка

| Раздел | Файлов | Строк |
|--------|--------|-------|
| Основное | 7 | ~3 500 |
| Модули | 5 | ~2 800 |
| Скрипты | 3 | ~1 500 |
| Сценарии | 3 | ~2 200 |
| **Всего** | **18** | **~10 000** |

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
| **PROD** | `http://localhost:8511` (ветка `main`) |
| **Swagger DEV** | `http://localhost:8512/docs` |
| **Документация DEV** | `http://localhost:8512/project-docs` |
| **Мониторинг DEV** | `http://localhost:8512/monitor` |

## 🔧 Обновление документации

### Как добавить новый `.md`

1. Создать файл в нужной подпапке `docs/`:
   ```bash
   nano docs/modules/new_module.md
   ```
2. **Первый заголовок `# Title`** — станет именем в навигации `/project-docs`
3. **Ссылки между документами** — относительные: `[api.md](../api.md)`
   - Работают и на GitHub, и в `/project-docs` (см. `render_doc` — срезает `.md`)
4. **Mermaid** — блок ` ```mermaid `
5. **Обновить этот файл** — добавить ссылку в нужную таблицу выше
6. Коммит:
   ```bash
   git add docs/
   git commit -m "docs: add new_module.md"
   git push origin dev
   ```

### Как обновлять

- **Правки в `docs/*.md`** — коммит в `dev`, уйдёт с ближайшим `./deploy.sh`
- **Роут `/project-docs`** — сам подхватит новые `.md` (сканирует `docs/` через `rglob`)
- **Навигация** — обновляется автоматически (список файлов)

### Проверка рендера

```bash
# 1. Что новый файл в индексе
curl -s http://localhost:8512/project-docs | grep '<название>'

# 2. Что отдаёт 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8512/project-docs/modules/new_module
```

## 📋 Известные TODO в кодовой базе

Отражены в разделах **Known issues** внутри соответствующих документов:

| Модуль / файл | Проблема | Документ |
|---------------|----------|----------|
| `config.py` | Пароль SOAP в коде (не в `.env`) | [soap_integration.md](soap_integration.md#-безопасность) |
| `worker/consumer.py` | `result.get('errors', 0)` — ключа нет | [modules/worker.md](modules/worker.md#-known-issues-todo) |
| `worker/consumer.py` | Пустой `except:` глотает `KeyboardInterrupt` | [modules/worker.md](modules/worker.md#-known-issues-todo) |
| `job_manager/file_operations.py` | `if not job_id:` — считает `0` пустым | [modules/job_manager.md](modules/job_manager.md#-known-issues-todo) |
| `job_manager/search.py` | `find_jobs(base=...)` игнорирует base без bank | [modules/job_manager.md](modules/job_manager.md#-known-issues-todo) |
| `worker/file_processor.py` | Использует legacy `api_bank` (только ci) | [modules/api_bank_client.md](modules/api_bank_client.md#-known-issues-todo) |
| `routes/callback.py` | Нет `/callback_sb` и `/callback_vtb` | [modules/api_bank_client.md](modules/api_bank_client.md#-known-issues-todo) |
| `sh_prod/restart_prod.sh` | `sleep 5` не ждёт старта | [scripts/sh_prod.md](scripts/sh_prod.md#-known-issues-todo) |