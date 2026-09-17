#!/bin/bash
# load_env.sh — загрузка переменных из .env
#
# Использование:
#   SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
#   PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
#   source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR"
#
# После вызова доступны:
#   $SBP_MQ_PORT, $SBP_MQ_DEBUG_PORT, $REDIS_DB, $RABBITMQ_QUEUE, $TEST_MODE
#   $DEV_DIR, $PROD_DIR, $PROJECT_DIR

load_env() {
    local project_dir="$1"
    local env_file="$project_dir/.env"

    if [ -z "$project_dir" ]; then
        echo "❌ load_env: не указан project_dir" >&2
        return 1
    fi

    if [ ! -f "$env_file" ]; then
        echo "❌ load_env: .env не найден: $env_file" >&2
        return 1
    fi

    # Загружаем .env
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    # Проверяем критичные переменные
    for var in SBP_MQ_PORT DEV_DIR PROD_DIR; do
        if [ -z "${!var}" ]; then
            echo "❌ load_env: $var не задан в $env_file" >&2
            return 1
        fi
    done

    # Экспортируем
    export SBP_MQ_PORT
    export SBP_MQ_DEBUG_PORT="${SBP_MQ_DEBUG_PORT:-5679}"
    export REDIS_DB="${REDIS_DB:-0}"
    export RABBITMQ_QUEUE="${RABBITMQ_QUEUE:-sbp_mq_queue}"
    export TEST_MODE="${TEST_MODE:-false}"
    export DEV_DIR
    export PROD_DIR
    export PROJECT_DIR="$project_dir"

    return 0
}

if [ -n "$1" ]; then
    load_env "$1"
fi
