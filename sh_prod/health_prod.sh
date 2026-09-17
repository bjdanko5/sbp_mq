#!/bin/bash
# health_prod.sh — healthcheck prod

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

# Загружаем .env из DEV (там указан PROD_DIR)
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

# ✅ Подменяем PROJECT_DIR на PROD_DIR для правильного порта
if [ -f "$PROD_DIR/.env" ]; then
    source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR"
fi

echo "🔍 PROD healthcheck (порт $SBP_MQ_PORT)"
echo "   PROD_DIR: $PROD_DIR"
echo ""

echo "=== /health ==="
timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/health" | jq .
echo ""

echo "=== /health/detailed ==="
timeout 10 curl -s "http://localhost:${SBP_MQ_PORT}/health/detailed" | jq .
