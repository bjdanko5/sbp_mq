#!/bin/bash
# restart_dev.sh — перезапуск dev-сервиса

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

echo "🔄 Перезапуск sbp_mq_dev (порт $SBP_MQ_PORT)"
echo ""

sudo systemctl restart sbp_mq-dev.service
echo "✅ Перезапущено"
sleep 5

echo -n "Health: "
timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/health" | jq -c . 2>/dev/null || echo "❌"
echo ""
