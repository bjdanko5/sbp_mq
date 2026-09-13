#!/bin/bash
cd /var/www/html/sbp_mq
source .venv/bin/activate

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
echo "🔧 РЕЖИМЫ ЗАПУСКА:"
echo "   SBP_MQ_PORT:       $SBP_MQ_PORT"
echo "   SBP_MQ_DEBUG_PORT: $SBP_MQ_DEBUG_PORT"
echo "   TEST_MODE:         $TEST_MODE"
echo "   DEBUG_VERBOSE:     $DEBUG_VERBOSE"
echo "========================================"

# ============================================================
#                   ПЕРЕЗАПУСК WORKER'ОВ (ЧЕРЕЗ SYSTEMD)
# ============================================================

echo ""
echo "🔄 Перезапуск Worker'ов через systemd..."

# Проверяем, какие Worker-сервисы существуют и активны
WORKER_SERVICES=$(systemctl list-units --type=service --all 2>/dev/null | grep -E "sbp_mq-worker" | awk '{print $1}')

if [ -n "$WORKER_SERVICES" ]; then
    for svc in $WORKER_SERVICES; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo "   🔄 Перезапуск: $svc"
            sudo systemctl restart "$svc" 2>/dev/null || echo "   ⚠️  Не удалось перезапустить $svc"
        else
            echo "   ⏸️  Пропущен (не активен): $svc"
        fi
    done
    echo "   ✅ Worker'ы перезапущены"
else
    echo "   ⚠️  Worker-сервисы не найдены"
fi

# ============================================================
#                   ЗАПУСК СЕРВЕРА
# ============================================================

echo ""
echo "🚀 Запуск SBP MQ сервера..."
echo "   HTTP:  http://localhost:${SBP_MQ_PORT}"
echo "   Debug: 0.0.0.0:${SBP_MQ_DEBUG_PORT}"
echo ""

python -B -m debugpy --listen 0.0.0.0:${SBP_MQ_DEBUG_PORT} \
    -m uvicorn sbp:app --reload --host 0.0.0.0 --port ${SBP_MQ_PORT} &
SERVER_PID=$!
echo "   Сервер PID: $SERVER_PID"

# ============================================================
#                   ИТОГ
# ============================================================

echo ""
echo "========================================"
echo "✅ Всё запущено!"
echo "   Сервер:     http://localhost:${SBP_MQ_PORT}"
echo "   Debug:      0.0.0.0:${SBP_MQ_DEBUG_PORT}"
echo "   Мониторинг: http://localhost:${SBP_MQ_PORT}/monitor"
echo "   Worker'ы:   через systemd (см. логи выше)"
echo "========================================"
echo ""
echo "⏳ Сервер работает в фоне. Ctrl+C для выхода."

wait $SERVER_PID