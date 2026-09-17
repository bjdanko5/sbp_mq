#!/bin/bash
# health_dev.sh — healthcheck dev

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

echo "🔍 DEV healthcheck (порт $SBP_MQ_PORT)"
echo "   DEV_DIR:  $DEV_DIR"
echo "   PROD_DIR: $PROD_DIR"
echo ""

echo "=== /health ==="
timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/health" | jq .
echo ""

echo "=== /health/detailed ==="
timeout 10 curl -s "http://localhost:${SBP_MQ_PORT}/health/detailed" | jq .
