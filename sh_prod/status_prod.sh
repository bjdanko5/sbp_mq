#!/bin/bash
# status_prod.sh — статус prod-сервисов

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

echo "📊 PROD статус (порт $SBP_MQ_PORT)"
echo "   PROD_DIR: $PROD_DIR"
echo ""

echo "=== sbp_mq-debug ==="
sudo systemctl status sbp_mq-debug.service --no-pager | grep -E 'Active:|Main PID:'
echo ""
echo "=== sbp_mq-worker* ==="
sudo bash -c 'systemctl status sbp_mq-worker* --no-pager' | grep -E '●|Active:|Main PID:'
echo ""
