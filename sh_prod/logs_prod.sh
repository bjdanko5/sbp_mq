#!/bin/bash
# logs_prod.sh — логи prod

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1
source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR"

echo "📋 Логи PROD (порт $SBP_MQ_PORT)"
echo ""
sudo journalctl -u sbp_mq-debug.service -n 30 --no-pager
