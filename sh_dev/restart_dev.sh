#!/bin/bash
# restart_dev.sh — перезапуск dev-сервиса с ожиданием старта

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

PORT="${SBP_MQ_PORT:-8512}"
SERVICE="sbp_mq-dev.service"
URL="http://localhost:${PORT}"

echo "🔄 Перезапуск ${SERVICE} (порт ${PORT})"
echo ""

# ============================================================
#                   РЕСТАРТ
# ============================================================

sudo systemctl restart "${SERVICE}" || {
    echo "❌ Не удалось выполнить systemctl restart ${SERVICE}"
    exit 1
}

# ============================================================
#                   ОЖИДАНИЕ СТАРТА (healthcheck)
# ============================================================

echo "⏳ Ожидание старта (до 30 сек)..."

READY=0
for i in $(seq 1 30); do
    CODE=$(timeout 2 curl -s -o /dev/null -w "%{http_code}" "${URL}/health" 2>/dev/null || echo "000")
    if [ "$CODE" = "200" ]; then
        echo "   ✅ Сервис поднялся за ${i} сек"
        READY=1
        break
    fi
    sleep 1
done

if [ "$READY" != "1" ]; then
    echo "   ❌ Сервис не поднялся за 30 сек"
    echo ""
    echo "📋 Последние 40 строк лога:"
    echo "─────────────────────────────────────────"
    sudo journalctl -u "${SERVICE}" -n 40 --no-pager 2>/dev/null || true
    echo "─────────────────────────────────────────"
    exit 1
fi

# ============================================================
#                   ИТОГ
# ============================================================

echo ""
echo "📊 Health:"
curl -s "${URL}/health" | jq -c . 2>/dev/null || curl -s "${URL}/health"
echo ""

echo "📊 Detailed (кратко):"
curl -s "${URL}/health/detailed" \
    | jq -c '{status, components: (.components | keys)}' 2>/dev/null \
    || echo "(не удалось получить detailed)"
echo ""

echo "📖 Документация: ${URL}/project-docs"
echo "📊 Мониторинг:   ${URL}/monitor"