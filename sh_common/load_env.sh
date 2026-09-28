#!/bin/bash
# load_env.sh — загрузка переменных из .env
#
# Философия: .env — единственный источник правды.
# Никаких фоллбэков. Если переменной нет — ошибка.
#
# Использование:
#   PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
#   source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR"

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

    # Список обязательных переменных (зависят от окружения)
    local required_vars=(
        SBP_MQ_PORT
        SBP_MQ_DEBUG_PORT
        DEV_DIR
        PROD_DIR
        REDIS_DB
        RABBITMQ_QUEUE
        TEST_MODE
    )

    # Проверяем, что все заданы
    local missing=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing+=("$var")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        echo "❌ load_env: в $env_file не заданы:" >&2
        for var in "${missing[@]}"; do
            echo "   - $var" >&2
        done
        return 1
    fi

    # Экспортируем (без фоллбэков — значения уже проверены)
    export SBP_MQ_PORT
    export SBP_MQ_DEBUG_PORT
    export DEV_DIR
    export PROD_DIR
    export REDIS_DB
    export RABBITMQ_QUEUE
    export TEST_MODE
    export PROJECT_DIR="$project_dir"

    return 0
}

if [ -n "$1" ]; then
    load_env "$1"
fi