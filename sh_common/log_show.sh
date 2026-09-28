#!/bin/bash
# log_show.sh — просмотр логов PROD-сервиса в реальном времени

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1
source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR" || exit 1

sudo journalctl -u sbp_mq-debug.service -f
