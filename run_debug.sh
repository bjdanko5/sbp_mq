#!/bin/bash
# run_debug.sh — запуск SBP MQ с отладкой
#
# Универсальный скрипт: работает и в prod (/var/www/html/sbp_mq),
# и в dev (/var/www/html/sbp_mq_dev).
#
# Определяет режим по имени папки:
#   - *_dev → dev (порт 8512, Redis DB 1, очередь sbp_mq_dev_queue, воркеры sbp_mq-dev-worker)
#   - остальное → prod (порт 8511, Redis DB 0, очередь sbp_mq_queue, воркеры sbp_mq-worker)

# ============================================================
#                   ОПРЕДЕЛЕНИЕ ОКРУЖЕНИЯ
# ============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_DIR")"

# ✅ Определяем режим по имени папки
if [[ "$PROJECT_NAME" == *"_dev" ]]; then
    MODE="DEV"
    WORKER_PATTERN="sbp_mq-dev-worker"
else
    MODE="PROD"
    WORKER_PATTERN="sbp_mq-worker"
fi

echo "========================================"
echo "🔧 SBP MQ — РЕЖИМ: $MODE"
echo "   Папка:    $PROJECT_DIR"
echo "   Воркеры:  $WORKER_PATTERN*"
echo "========================================"

cd "$PROJECT_DIR" || {
    echo "❌ Не удалось перейти в $PROJECT_DIR"
    exit 1
}

# ============================================================
#                   АКТИВАЦИЯ VENV
# ============================================================

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo "✅ venv активирован"
else
    echo "❌ .venv/bin/activate не найден!"
    exit 1
fi

# ============================================================
#                   ЗАГРУЗКА .env
# ============================================================

if [ -f .env ]; then
    echo "📄 Загружаем .env..."
    set -a
    source .env
    set +a
else
    echo "❌ .env не найден!"
    exit 1
fi

# ============================================================
#                   ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ
# ============================================================

: "${SBP_MQ_PORT:?SBP_MQ_PORT не задан в .env}"
: "${SBP_MQ_DEBUG_PORT:?SBP_MQ_DEBUG_PORT не задан в .env}"
: "${TEST_MODE:?TEST_MODE не задан в .env}"

# ============================================================
#                   ОСТАНОВКА СТАРЫХ ПРОЦЕССОВ СЕРВЕРА
# ============================================================

echo ""
echo "⏹️  Останавливаем старые процессы сервера..."

pkill -9 -f "uvicorn.*${SBP_MQ_PORT}" 2>/dev/null
pkill -9 -f "debugpy.*${SBP_MQ_DEBUG_PORT}" 2>/dev/null
sleep 2

# ============================================================
#                   ПРОВЕРКА ПОРТОВ
# ============================================================

echo "📊 Проверка портов..."

if lsof -i :${SBP_MQ_DEBUG_PORT} 2>/dev/null | grep -q LISTEN; then
    echo "   ⚠️  Порт ${SBP_MQ_DEBUG_PORT} занят, убиваем..."
    lsof -ti :${SBP_MQ_DEBUG_PORT} 2>/dev/null | xargs -r kill -9 2>/dev/null
    sleep 1
fi

if lsof -i :${SBP_MQ_PORT} 2>/dev/null | grep -q LISTEN; then
    echo "   ⚠️  Порт ${SBP_MQ_PORT} занят, убиваем..."
    lsof -ti :${SBP_MQ_PORT} 2>/dev/null | xargs -r kill -9 2>/dev/null
    sleep 1
fi

echo "   ✅ Порты свободны"

# ============================================================
#                   ОЧИСТКА КЭША PYTHON
# ============================================================

echo ""
echo "🧹 Очистка кэша Python..."

CACHE_COUNT=$(find . -type d -name "__pycache__" -not -path "./.venv/*" 2>/dev/null | wc -l)
PYC_COUNT=$(find . -name "*.pyc" -not -path "./.venv/*" 2>/dev/null | wc -l)

find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -not -path "./.venv/*" -delete 2>/dev/null
find . -name "*.pyo" -not -path "./.venv/*" -delete 2>/dev/null

echo "   ✅ Удалено: $CACHE_COUNT папок, $PYC_COUNT файлов"

export PYTHONDONTWRITEBYTECODE=1

# ============================================================
#                   ИНФОРМАЦИЯ
# ============================================================

echo "========================================"
echo "🔧 РЕЖИМЫ ЗАПУСКА ($MODE):"
echo "   SBP_MQ_PORT:       $SBP_MQ_PORT"
echo "   SBP_MQ_DEBUG_PORT: $SBP_MQ_DEBUG_PORT"
echo "   TEST_MODE:         $TEST_MODE"
echo "   DEBUG_VERBOSE:     $DEBUG_VERBOSE"
echo "   SBP_ROOT4MQ:       $SBP_ROOT4MQ"
echo "========================================"

# ============================================================
#                   ПЕРЕЗАПУСК ВОРКЕРОВ
# ============================================================

echo ""
echo "🔄 Перезапуск воркеров ($MODE, паттерн: $WORKER_PATTERN*)..."

# ✅ Ищем воркеры по паттерну для текущего окружения
WORKER_SERVICES=$(systemctl list-units --type=service --all 2>/dev/null | grep -E "$WORKER_PATTERN" | awk '{print $1}')

if [ -n "$WORKER_SERVICES" ]; then
    for svc in $WORKER_SERVICES; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo "   🔄 Перезапуск: $svc"
            sudo systemctl restart "$svc" 2>/dev/null || echo "   ⚠️  Не удалось перезапустить $svc"
        else
            echo "   ⏸️  Пропущен (не активен): $svc"
        fi
    done
    echo "   ✅ Воркеры перезапущены"
else
    echo "   ⚠️  Воркеры не найдены (паттерн: $WORKER_PATTERN)"
fi

# ============================================================
#                   ЗАПУСК СЕРВЕРА
# ============================================================

echo ""
echo "🚀 Запуск SBP MQ ($MODE) сервера..."
echo "   HTTP:  http://localhost:${SBP_MQ_PORT}"
echo "   Debug: 0.0.0.0:${SBP_MQ_DEBUG_PORT}"
echo ""

python -B -m debugpy --listen 0.0.0.0:${SBP_MQ_DEBUG_PORT} \
    -m uvicorn sbp:app  --host 0.0.0.0 --port ${SBP_MQ_PORT} &
SERVER_PID=$!
echo "   Сервер PID: $SERVER_PID"

# ============================================================
#                   ИТОГ
# ============================================================

echo ""
echo "========================================"
echo "✅ $MODE запущен!"
echo "   Сервер:     http://localhost:${SBP_MQ_PORT}"
echo "   Debug:      0.0.0.0:${SBP_MQ_DEBUG_PORT}"
echo "   Мониторинг: http://localhost:${SBP_MQ_PORT}/monitor"
echo "   Воркеры:    через systemd ($WORKER_PATTERN*)"
echo "========================================"
echo ""
echo "⏳ Сервер работает в фоне. Ctrl+C для выхода."

wait $SERVER_PID