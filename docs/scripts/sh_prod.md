# Скрипты `sh_prod/`

Работают **только с PROD**:
- Сервисы: `sbp_mq-debug.service`, `sbp_mq-worker*`
- Порт: 8510, Redis DB 0
- Папки: `/sbp/mq/`, `/var/www/html/sbp_mq/`

> ⚠️ **WARNING:** скрипты работают с продакшеном. Перед запуском — убедиться,
> что понимаешь последствия. Все требуют `sudo`.

---

## 📁 Структура

```
sh_prod/
├── deploy_to_prod.sh           ← главный деплой (dev → prod)
├── restart_prod.sh             ← рестарт HTTP
├── restart_prod_workers.sh     ← рестарт воркеров
├── status_prod.sh              ← статус systemd
├── health_prod.sh              ← /health + /health/detailed
├── logs_prod.sh                ← journalctl (tail -n 30)
├── backup_sbp_mq.sh            ← бэкап всего проекта
├── restore_sbp_mq.sh           ← восстановление (venv сохраняется)
├── restore_sbp_mq_with_venv.sh ← восстановление + пересоздание venv
└── README.md
```

---

## 🚀 `deploy_to_prod.sh` — главный деплой

**Полностью описан в [deployment.md](../deployment.md#-обычный-деплой-dev--prod).**
Здесь — только краткая ссылка.

```bash
cd /var/www/html/sbp_mq_dev
./deploy.sh                    # обёртка → sh_prod/deploy_to_prod.sh
```

**Что делает:**

1. Проверка worktree (DEV=dev, PROD=main)
2. Проверка чистоты git (DEV и PROD)
3. Проверка `processing_count=0` на PROD (`/monitor/data`)
4. `git push origin dev`
5. `PROD: git pull origin main && git merge dev && git push origin main`
6. `pip install -r requirements.txt` (только если менялся, timeout 120s)
7. `systemctl restart sbp_mq-debug.service`
8. Healthcheck (30×1с)
9. Финальный вывод: `/health`, `/health/detailed`

**При любой ошибке — стоп, PROD не трогается.**

---

## 🔧 Основные

### `restart_prod.sh` — рестарт HTTP

```bash
./sh_prod/restart_prod.sh
```

- `systemctl restart sbp_mq-debug.service`
- `sleep 5` (⚠️ **фиксированный, не ждёт healthcheck**)
- `curl /health`

⚠️ **Не ждёт готовности** — если uvicorn стартует дольше 5 сек, увидишь
пустой `Health: ❌`. См. known issues.

**Когда:** быстрый рестарт без деплоя (после правки `.env`, например).

### `restart_prod_workers.sh` — рестарт воркеров

```bash
./sh_prod/restart_prod_workers.sh
```

- `systemctl restart sbp_mq-worker*` — **все** воркеры
- `sleep 3`
- `systemctl status ... | grep '●|Active:'`

**Когда:** воркеры зависли.

### `status_prod.sh` — статус

```bash
./sh_prod/status_prod.sh
```

- Загружает `.env` из DEV (для `PROD_DIR`), потом из PROD (для `SBP_MQ_PORT=8510`)
- `systemctl status sbp_mq-debug.service` → `Active`, `Main PID`
- `systemctl status sbp_mq-worker*` → все воркеры

### `health_prod.sh` — healthcheck

```bash
./sh_prod/health_prod.sh
```

- `/health` → JSON (`jq .`)
- `/health/detailed` → JSON (полный)

**Не требует sudo**, только curl.

---

## 📜 Логи

### `logs_prod.sh` — последние строки

```bash
./sh_prod/logs_prod.sh
```

- Загружает `.env` из DEV (для `PROD_DIR`) и из PROD (для `SBP_MQ_PORT`)
- `journalctl -u sbp_mq-debug.service -n 30 --no-pager`

**Live-вариант:** в `sh_common/log_show.sh` (там хардкод пути, но работает).

---

## 💾 Бэкап

### `backup_sbp_mq.sh` — бэкап

```bash
./sh_prod/backup_sbp_mq.sh
```

**Что делает:**

- **Не останавливает** сервисы (бэкап «на лету»)
- Создаёт `.tar.gz` в `/var/www/html/backups/`
- Имя: `sbp_mq_backup_YYYYMMDD_HHMMSS.tar.gz`
- **Проверяет** статусы всех сервисов:

```bash
ALL_SERVICES=(
    "sbp_mq-debug"
    "sbp_mq-worker"
    "sbp_mq-worker@1"
    "sbp_mq-worker@2"
    "sbp_mq-worker@3"
)
```

**Что в бэкапе:** `/var/www/html/sbp_mq` целиком, **включая** `.venv` и `.env`.

⚠️ **`.env` попадёт в архив!** Хранить бэкапы в защищённом месте.

### `restore_sbp_mq.sh` — восстановление

```bash
./sh_prod/restore_sbp_mq.sh /path/to/backup.tar.gz
```

- Останавливает сервисы
- Распаковывает бэкап
- **Сохраняет текущий `.venv`** (не пересоздаёт)
- Запускает сервисы
- Healthcheck

**Когда:** откат после неудачного обновления, восстановление после сбоя.

### `restore_sbp_mq_with_venv.sh` — восстановление + venv

```bash
./sh_prod/restore_sbp_mq_with_venv.sh /path/to/backup.tar.gz
```

- То же, но **пересоздаёт `.venv`**:
  - Удаляет текущий
  - Создаёт новый (`python -m venv .venv`)
  - `pip install -r requirements.txt`
- **Медленнее** (устанавливает зависимости)

**Когда:** venv сломан, обновление Python, миграция на другую машину.

---

## 🔗 Типовые сценарии

### Обычный деплой

```bash
cd /var/www/html/sbp_mq_dev
./deploy.sh
```

### Быстрый рестарт PROD без деплоя

```bash
./sh_prod/restart_prod.sh
```

### Проверить статус

```bash
./sh_prod/status_prod.sh
./sh_prod/health_prod.sh
```

### Логи

```bash
./sh_prod/logs_prod.sh
# или live:
./sh_common/log_show.sh
```

### Плановый бэкап

```bash
./sh_prod/backup_sbp_mq.sh
ls -lh /var/www/html/backups/
```

### Аварийный откат

```bash
# вариант 1 — git
cd /var/www/html/sbp_mq
git reset --hard HEAD~1
sudo systemctl restart sbp_mq-debug.service

# вариант 2 — из бэкапа
./sh_prod/restore_sbp_mq.sh /var/www/html/backups/sbp_mq_backup_20260920_193000.tar.gz
```

---

## 🧪 Отладка

### Проверить, что `PROD_DIR` правильный

```bash
cd /var/www/html/sbp_mq_dev
source sh_common/load_env.sh "$PWD"
echo "DEV_DIR=$DEV_DIR, PROD_DIR=$PROD_DIR"
```

### Если `restart_prod.sh` печатает `Health: ❌`

Скорее всего `sleep 5` мало. Используй:

```bash
./sh_prod/health_prod.sh
```

Если и там пусто — `journalctl`:

```bash
sudo journalctl -u sbp_mq-debug.service -n 100 --no-pager
```

### Если бэкап не создаётся

Проверь `BACKUP_DIR`:

```bash
ls -ld /var/www/html/backups/
df -h /var/www/html/
```

### Если `restore` падает

Смотри полный вывод (там печатает шаги). Типовые причины:
- битый архив (`tar -tzf archive.tar.gz`)
- нет прав на `/var/www/html/sbp_mq`
- сервисы не остановились

---

## 📋 Known issues (TODO)

| # | Файл | Проблема | Приоритет |
|---|------|----------|-----------|
| 1 | `restart_prod.sh` | `sleep 5` фикс — не ждёт старта, как `restart_dev.sh` (30×1с) | **средний** |
| 2 | `backup_sbp_mq.sh` | Включает `.env` в архив — хранить в защищённом месте | низкий |
| 3 | `restart_prod.sh`, `status_prod.sh`, `health_prod.sh`, `logs_prod.sh` | Двойной `source load_env.sh` — работает, но громоздко | низкий |
| 4 | `restart_prod_workers.sh` | Как в `sh_dev` — `grep '●'` при отсутствии активных даёт ложно-успех | низкий |
| 5 | `backup_sbp_mq.sh` | Проверяет `sbp_mq-worker@1/@2/@3`, но не `sbp_mq-worker@N` для N>3 | низкий |
| 6 | `restore_sbp_mq_with_venv.sh` | Долгий `pip install` без прогресс-бара | низкий |

---

## ⚠️ Общие предупреждения

1. **`WARNING`** из `README.md` — **не шутка**. Все скрипты в `sh_prod/` могут
   повлиять на боевую систему.
2. **Перед деплоем** — всегда `./deploy.sh` (там встроены проверки), а не
   ручные `git` + `systemctl`.
3. **Перед `restore`** — сделать **свежий бэкап** текущего состояния на случай,
   если восстановление окажется не тем, что нужно.
4. **`FLUSHDB`** в `sh_dev/reset_dev.sh` — только DEV. В PROD такого нет, и
   слава богу.

---

## 🔗 Связанные документы

- [deployment.md](../deployment.md) — **главный документ по деплою**
- [git_workflow.md](../git_workflow.md) — worktree, ветки
- [configuration.md](../configuration.md) — переменные `.env`
- [scripts/sh_common.md](sh_common.md) — `load_env.sh`
- [scripts/sh_dev.md](sh_dev.md) — dev-скрипты
