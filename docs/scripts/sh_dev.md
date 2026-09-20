# Скрипты `sh_dev/`

Работают **только с DEV**:
- Сервисы: `sbp_mq-dev.service`, `sbp_mq-dev-worker*`
- Порт: 8512, Redis DB 1
- Папки: `/sbp/mq_dev/`, `/var/www/html/sbp_mq_dev/`

> ⚠️ **Запускать из `/var/www/html/sbp_mq_dev`**, из-под `user`, с `sudo`
> (кроме `health_dev.sh`).

---

## 📁 Структура

```
sh_dev/
├── restart_dev.sh             ← рестарт HTTP с ожиданием
├── restart_dev_workers.sh     ← рестарт всех воркеров
├── status_dev.sh              ← статус systemd
├── health_dev.sh              ← /health + /health/detailed
├── logs_dev.sh                ← journalctl (tail -n 30)
├── logs_dev_all.sh            ← tail -f logs/all.log (агрегированный)
├── reset_dev.sh               ← ⚠️ очистка Redis + Jobs + логов
├── quick_test.sh              ← быстрый smoke-тест (5 файлов)
├── test_create_payload_mq.sh  ← тест MQ-пайплайна (1 Job)
├── test_monitor_v2.sh         ← полный тест мониторинга (9 Job)
└── README.md
```

---

## 🔧 Основные

### `restart_dev.sh` — рестарт HTTP

```bash
./sh_dev/restart_dev.sh
```

- `systemctl restart sbp_mq-dev.service`
- Ожидание `200` на `/health` (30×1с)
- При провале — `journalctl -n 40`
- **Финал:** печатает `/health`, `/health/detailed` (кратко), ссылки на `/project-docs`, `/monitor`

**Когда:** после правок в коде, при зависании, после `reset_dev.sh`.

### `restart_dev_workers.sh` — рестарт воркеров

```bash
./sh_dev/restart_dev_workers.sh
```

- `systemctl restart sbp_mq-dev-worker*` — **все** воркеры
- `sleep 3`
- Печатает `systemctl status ... | grep '●|Active:'`

**Когда:** воркеры зависли, нужен «чистый» старт после правок.

### `status_dev.sh` — статус

```bash
./sh_dev/status_dev.sh
```

- `systemctl status sbp_mq-dev.service` → `Active`, `Main PID`
- `systemctl status sbp_mq-dev-worker*` → все воркеры

**Когда:** «что вообще работает?»

### `health_dev.sh` — healthcheck

```bash
./sh_dev/health_dev.sh
```

- `/health` → JSON (`jq .`)
- `/health/detailed` → JSON (`jq .`, полный, 7 компонентов)

**Когда:** быстрая проверка после деплоя/рестарта. **Не требует sudo.**

---

## 📜 Логи

### `logs_dev.sh` — последние строки

```bash
./sh_dev/logs_dev.sh
```

- `journalctl -u sbp_mq-dev.service -n 30 --no-pager`
- Разовый вывод, не `-f`

### `logs_dev_all.sh` — live агрегированный

```bash
./sh_dev/logs_dev_all.sh
```

- `tail -f logs/all.log`
- **Live** (`Ctrl+C` для выхода)
- Пишет **все** воркеры (короткие сообщения) + сервер

**Что видно:** кто взял Job, кто закончил, ошибки. **Ссылки на детальные
логи** (`logs/mq-worker-N.log`) — в каждом сообщении.

---

## ⚠️ `reset_dev.sh` — очистка DEV

```bash
./sh_dev/reset_dev.sh
```

⚠️ **Спрашивает подтверждение** (`y/n`). Очищает:

| Что | Как |
|-----|-----|
| Redis DB 1 | `redis-cli -n 1 FLUSHDB` |
| `/sbp/mq_dev/jobs/*.json` | `rm -f` |
| `/sbp/mq_dev/jobs/success/*.json` | `rm -f` |
| `/sbp/mq_dev/jobs/error/*.json` | `rm -f` |
| `logs/*.log` | `: > file` (truncate) |

**Когда:** перед полным тестом, при «мусоре» в состоянии.

⚠️ **`FLUSHDB`** удалит **все** ключи в DB 1: `req:*`, `task:*`, `progress:*`,
`lock:*`, `processed:*`. Это **DEV**, но осторожно.

### Что **не** очищает

- Файлы в `/sbp/mq_dev/ci/zkh_ursv/*.json` (исходные данные для worker'а)
- SQLite (`requests.db`) — там история callback'ов
- `.env`

Если нужно — вручную:

```bash
rm -f /sbp/mq_dev/ci/zkh_ursv/*.json
rm -f requests.db
```

---

## 🧪 Тесты

### `quick_test.sh` — быстрый smoke

```bash
./sh_dev/quick_test.sh
```

**Что делает:**

1. Создаёт 5 файлов (`7845.json`…`7849.json`) в `/sbp/mq_dev/ci/zkh_ursv/`
   с 2 запросами каждый
2. Очищает старые Job-файлы
3. Создаёт Job через API
4. Ждёт обработки
5. Проверяет результат

**Когда:** проверить, что пайплайн жив после рестарта.

### `test_create_payload_mq.sh` — один Job

```bash
./sh_dev/test_create_payload_mq.sh
```

**Что делает:**

1. Создаёт `zkh_ursv` файлы
2. Вызывает `GET /create_payload_mq/ci/zkh_ursv/999`
3. Показывает `task_id`
4. Ждёт обработки
5. Печатает `/create_payload_mq/ci/zkh_ursv/999/status`

**Когда:** проверить один Job от начала до конца.

### `test_monitor_v2.sh` — полный тест

```bash
./sh_dev/test_monitor_v2.sh
```

**Самый большой тест.** Создаёт **9 Job** (3 базы × 3 Job). Проверяет:

1. Создание и обработку 9 Job
2. Появление `req:{requestID}` → `task_id` в Redis
3. Callback: `base` резолвится через Redis
4. SOAP-вызов: успех/ошибка с детализацией
5. Удаление `req:*` после успешного SOAP
6. Fallback на SQLite
7. Логи: очистка перед тестом + анализ после

**Особенности:**
- Job ID — **глобально уникальные** (101, 102, 103, 201, 202, 203, 301, 302, 303)
  (`BASE_IDX * 100 + JOB_IDX`)
- requestId — **числа до 1000** (`BASE_IDX * 100 + JOB_IDX * 10 + REQ_IDX`)

**Когда:** перед деплоем в PROD — убедиться, что всё работает end-to-end.

---

## 🔗 Типовые сценарии

### После правок в коде

```bash
./sh_dev/restart_dev.sh
./sh_dev/health_dev.sh
```

### Проверить, что воркеры живы

```bash
./sh_dev/status_dev.sh
```

### Посмотреть, что происходит

```bash
./sh_dev/logs_dev_all.sh     # в одном окне
# в другом:
./sh_dev/health_dev.sh
```

### Полный сброс + тест

```bash
./sh_dev/reset_dev.sh        # подтвердить y
./sh_dev/restart_dev.sh
./sh_dev/quick_test.sh
```

### Проверить перед деплоем

```bash
./sh_dev/test_monitor_v2.sh
```

---

## 🧪 Отладка

### Проверить, что скрипт видит `.env`

```bash
cd /var/www/html/sbp_mq_dev
source sh_common/load_env.sh "$PWD"
echo "PORT=$SBP_MQ_PORT"        # 8512
echo "DEV_DIR=$DEV_DIR"
echo "PROD_DIR=$PROD_DIR"
```

### Если `restart_dev.sh` падает с ошибкой healthcheck

Смотри `journalctl`:

```bash
sudo journalctl -u sbp_mq-dev.service -n 100 --no-pager
```

Скорее всего — синтаксическая ошибка в коде (`python -c "import sbp"`).

### Если `reset_dev.sh` не сработал

Проверь права на `/sbp/mq_dev/jobs/*`:

```bash
ls -la /sbp/mq_dev/jobs/
```

Если владелец `root`, `rm` не сработает — `sudo rm`.

---

## 📋 Known issues (TODO)

| # | Файл | Проблема | Приоритет |
|---|------|----------|-----------|
| 1 | `restart_dev_workers.sh` | `systemctl status ... \| grep '●'` — при отсутствии активных воркеров grep вернёт пусто (ложно-успех) | низкий |
| 2 | `reset_dev.sh` | Не очищает `/sbp/mq_dev/ci/zkh_ursv/*.json` — только Jobs и Redis | средний |
| 3 | `logs_dev.sh` | Разовый вывод — нет `-f` варианта | низкий |
| 4 | `quick_test.sh` | Не проверяет 202 от API | низкий |
| 5 | `test_monitor_v2.sh` | Очень большой, плохо читается | низкий |

---

## 🔗 Связанные документы

- [deployment.md](../deployment.md) — контекст деплоя
- [configuration.md](../configuration.md) — переменные `.env`
- [scripts/sh_common.md](sh_common.md) — `load_env.sh`
- [scripts/sh_prod.md](sh_prod.md) — prod-скрипты
- [monitoring.md](../monitoring.md) — что смотреть в логах
