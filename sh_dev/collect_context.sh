#!/bin/bash
# sh_dev/collect_context.sh
#
# Собирает контекст проекта для новой сессии с ИИ.
# Вывод — markdown, можно скопировать в чат целиком.
#
# Использование:
#   ./sh_dev/collect_context.sh              # весь контекст
#   ./sh_dev/collect_context.sh --short      # без health и git log
#   ./sh_dev/collect_context.sh > /tmp/ctx.md

set -e

# ============================================================
#                   ПАРАМЕТРЫ
# ============================================================

SHORT=0
if [[ "$1" == "--short" ]]; then
    SHORT=1
fi

# ============================================================
#                   ОПРЕДЕЛЕНИЕ ОКРУЖЕНИЯ
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

# ✅ Загружаем DEV .env
# shellcheck disable=SC1091
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

DEV_PORT="$SBP_MQ_PORT"
DEV_QUEUE="$RABBITMQ_QUEUE"
DEV_REDIS="$REDIS_DB"
DEV_TEST_MODE="$TEST_MODE"

# ✅ Загружаем PROD .env (если PROD_DIR существует)
if [ -d "$PROD_DIR" ] && [ -f "$PROD_DIR/.env" ]; then
    # shellcheck disable=SC1091
    source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR" || true

    PROD_PORT="$SBP_MQ_PORT"
    PROD_QUEUE="$RABBITMQ_QUEUE"
    PROD_REDIS="$REDIS_DB"
    PROD_TEST_MODE="$TEST_MODE"
else
    PROD_PORT="?"
    PROD_QUEUE="?"
    PROD_REDIS="?"
    PROD_TEST_MODE="?"
fi

# ============================================================
#                   ШАПКА
# ============================================================

echo "# SBP MQ — контекст сессии"
echo
echo "> Сгенерировано: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "> Скрипт: \`sh_dev/collect_context.sh\`"
echo

# ============================================================
#                   GIT — DEV
# ============================================================

echo "## 📦 Git: dev"
echo
echo '```'
cd "$DEV_DIR"
echo "Ветка:    $(git branch --show-current)"
echo "HEAD:     $(git rev-parse --short HEAD)"
echo "origin:   $(git rev-parse --short origin/dev 2>/dev/null || echo '?')"
STATUS=$(git status --short | head -5)
if [ -z "$STATUS" ]; then
    echo "Статус:   clean"
else
    echo "Статус:"
    echo "$STATUS" | sed 's/^/          /'
fi
echo '```'
echo

if [ "$SHORT" -eq 0 ]; then
    echo "### Последние 10 коммитов (dev)"
    echo
    echo '```'
    git log --oneline -10
    echo '```'
    echo
fi

# ============================================================
#                   GIT — PROD
# ============================================================

echo "## 📦 Git: main (PROD)"
echo
echo '```'
if [ -d "$PROD_DIR" ]; then
    cd "$PROD_DIR"
    echo "Ветка:    $(git branch --show-current)"
    echo "HEAD:     $(git rev-parse --short HEAD)"
    echo "origin:   $(git rev-parse --short origin/main 2>/dev/null || echo '?')"
    STATUS=$(git status --short | head -5)
    if [ -z "$STATUS" ]; then
        echo "Статус:   clean"
    else
        echo "Статус:"
        echo "$STATUS" | sed 's/^/          /'
    fi
else
    echo "PROD_DIR не существует: $PROD_DIR"
fi
echo '```'
echo

# ============================================================
#                   РАСХОЖДЕНИЕ DEV vs MAIN
# ============================================================

cd "$DEV_DIR"

AHEAD=$(git rev-list --count main..dev 2>/dev/null || echo "?")
BEHIND=$(git rev-list --count dev..main 2>/dev/null || echo "?")

echo "## 🔀 Расхождение dev ↔ main"
echo
echo "- \`dev\` впереди \`main\` на **$AHEAD** коммитов"
echo "- \`main\` впереди \`dev\` на **$BEHIND** коммитов"
echo

if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then
    echo "### Коммиты в dev, которых нет в main"
    echo
    echo '```'
    git log --oneline main..dev | head -20
    echo '```'
    echo
fi

# ============================================================
#                   HEALTH
# ============================================================

if [ "$SHORT" -eq 0 ]; then
    echo "## 🏥 Health"
    echo

    # DEV
    echo "### DEV (:$DEV_PORT)"
    echo
    echo '```json'
    timeout 3 curl -s "http://localhost:${DEV_PORT}/health/detailed" \
        | jq -c '{status, queue: .components.rabbitmq.queue, db: .components.redis.db, workers: .components.workers.active}' 2>/dev/null \
        || echo '{"error": "DEV недоступен"}'
    echo '```'
    echo

    # PROD
    echo "### PROD (:$PROD_PORT)"
    echo
    echo '```json'
    timeout 3 curl -s "http://localhost:${PROD_PORT}/health/detailed" \
        | jq -c '{status, queue: .components.rabbitmq.queue, db: .components.redis.db, workers: .components.workers.active}' 2>/dev/null \
        || echo '{"error": "PROD недоступен"}'
    echo '```'
    echo
fi

# ============================================================
#                   ОКРУЖЕНИЯ
# ============================================================

echo "## 🌍 Окружения"
echo
echo "| | DEV | PROD |"
echo "|---|---|---|"
echo "| **Путь** | \`$DEV_DIR\` | \`$PROD_DIR\` |"
echo "| **Ветка** | \`dev\` | \`main\` |"
echo "| **HTTP** | \`http://localhost:${DEV_PORT}\` | \`http://localhost:${PROD_PORT}\` |"
echo "| **Очередь** | \`$DEV_QUEUE\` | \`$PROD_QUEUE\` |"
echo "| **Redis DB** | $DEV_REDIS | $PROD_REDIS |"
echo "| **TEST_MODE** | $DEV_TEST_MODE | $PROD_TEST_MODE |"
echo

# ============================================================
#                   ДОКУМЕНТАЦИЯ
# ============================================================

echo "## 📚 Документация"
echo
echo "**Всегда бросать в начале сессии:**"
echo "- \`docs/README.md\` — карта проекта"
echo "- \`docs/pitfalls.md\` — грабли"
echo
echo "**Если задача про:**"
echo "- воркер / abort / async → \`docs/pitfalls.md\`"
echo "- деплой / systemd → \`docs/pitfalls.md\`"
echo "- документацию → \`docs/pitfalls.md\`"
echo "- SOAP / 1С → \`docs/pitfalls.md\`, \`docs/soap_integration.md\`"
echo "- модуль X → \`docs/modules/X.md\`"
echo "- фронтенд / монитор → \`docs/modules/monitor.md\`"
echo

# ============================================================
#                   ПОЛЕЗНЫЕ КОМАНДЫ
# ============================================================

echo "## 🔧 Полезные команды"
echo
echo '```bash'
echo "# Health"
echo "curl -s http://localhost:${DEV_PORT}/health/detailed | jq ."
echo "curl -s http://localhost:${PROD_PORT}/health/detailed | jq ."
echo
echo "# DEV"
echo "./sh_dev/health_dev.sh"
echo "./sh_dev/restart_dev.sh"
echo "./sh_dev/test_monitor_v2.sh"
echo
echo "# Деплой"
echo "./deploy.sh"
echo
echo "# Git"
echo "git log --oneline -10"
echo "git status"
echo '```'
echo

# ============================================================
#                   ИТОГ
# ============================================================

echo "---"
echo
echo "**Скопируй этот вывод в чат + приложи \`docs/README.md\` и \`docs/pitfalls.md\`.**"