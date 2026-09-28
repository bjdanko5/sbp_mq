#!/bin/bash
# logs_dev_all.sh — агрегированный лог dev

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

tail -f "$LOG_DIR/all.log"
