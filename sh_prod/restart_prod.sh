#!/bin/bash
# restart_prod.sh — перезапуск prod-сервиса

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1
source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR"

echo "🔄 Перезапуск sbp_mq (порт $SBP_MQ_PORT)"
echo "   PROD_DIR: $PROD_DIR"
echo ""

sudo systemctl restart sbp_mq-debug.service
echo "✅ Перезапущено"
sleep 5

echo -n "Health: "
timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/health" | jq -c . 2>/dev/null || echo "❌"
echo ""
