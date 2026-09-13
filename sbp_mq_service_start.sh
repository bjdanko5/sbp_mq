#!/bin/bash
# sbp_mq_service_start.sh
# Запуск/перезапуск sbp_mq-debug.service с ожиданием полного старта.
#
# Ждёт:
#   1. Сервис перейдёт в active (running)
#   2. HTTP-сервер ответит на порту из .env
#
# Показывает ошибки, если:
#   - Сервис упал (failed)
#   - Таймаут ожидания
#   - HTTP не отвечает

set -o pipefail

PROJECT_DIR="/var/www/html/sbp_mq"
SERVICE_NAME="sbp_mq-debug.service"

# Таймауты (секунды)
START_TIMEOUT=60        # ожидание active (running)
HTTP_TIMEOUT=30         # ожидание HTTP-ответа
CHECK_INTERVAL=1        # интервал между проверками

# ============================================================
# ЦВЕТА
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================
# ПЕРЕХОД В ПРОЕКТ
# ============================================================

cd "$PROJECT_DIR" || {
    echo -e "${RED}❌ Не удалось перейти в $PROJECT_DIR${NC}"
    exit 1
}

# ============================================================
# АКТИВАЦИЯ VENV
# ============================================================

if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo -e "${GREEN}✅ venv активирован${NC}"
else
    echo -e "${YELLOW}⚠️  .venv/bin/activate не найден, продолжаем без venv${NC}"
fi

# ============================================================
# ЗАГРУЗКА .env (для SBP_MQ_PORT)
# ============================================================

if [ -f ".env" ]; then
    # shellcheck disable=SC1091
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ .env загружен${NC}"
else
    echo -e "${YELLOW}⚠️  .env не найден${NC}"
fi

# Порт по умолчанию
SBP_MQ_PORT="${SBP_MQ_PORT:-8511}"

# ============================================================
# ФУНКЦИИ
# ============================================================

# Показывает последние 30 строк логов сервиса
show_logs() {
    echo ""
    echo -e "${YELLOW}📋 Последние 30 строк логов сервиса:${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    sudo journalctl -u "$SERVICE_NAME" -n 30 --no-pager 2>/dev/null || \
        echo -e "${RED}   Не удалось получить логи${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
}

# Показывает статус сервиса
show_status() {
    echo ""
    echo -e "${YELLOW}📊 Статус сервиса:${NC}"
    systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null | head -20 || true
}

# Ждёт, пока сервис станет active (running)
# Возвращает:
#   0 — успех
#   1 — упал с ошибкой
#   2 — таймаут
wait_for_active() {
    local elapsed=0
    local last_state=""

    echo ""
    echo -e "${BLUE}⏳ Ожидание active (running)...${NC}"

    while [ "$elapsed" -lt "$START_TIMEOUT" ]; do
        local state
        state=$(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo "unknown")

        # Показываем изменение состояния
        if [ "$state" != "$last_state" ]; then
            echo -e "   [${elapsed}s] Состояние: ${YELLOW}${state}${NC}"
            last_state="$state"
        fi

        case "$state" in
            active)
                echo -e "   [${elapsed}s] ${GREEN}✅ Сервис активен${NC}"
                return 0
                ;;
            failed)
                echo -e "   [${elapsed}s] ${RED}❌ Сервис упал (failed)${NC}"
                return 1
                ;;
            activating)
                # продолжаем ждать
                ;;
            deactivating)
                # странно, но ждём
                ;;
            inactive)
                # может быть, ещё не начал стартовать
                ;;
        esac

        sleep "$CHECK_INTERVAL"
        elapsed=$((elapsed + CHECK_INTERVAL))
    done

    echo -e "   ${RED}❌ Таймаут ожидания (${START_TIMEOUT}s)${NC}"
    return 2
}

# Ждёт HTTP-ответа
# Возвращает:
#   0 — успех
#   1 — таймаут
wait_for_http() {
    local elapsed=0
    local url="http://localhost:${SBP_MQ_PORT}/"

    echo ""
    echo -e "${BLUE}⏳ Ожидание HTTP на ${url}...${NC}"

    while [ "$elapsed" -lt "$HTTP_TIMEOUT" ]; do
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time 2 "$url" 2>/dev/null || echo "000")

        if [ "$http_code" = "200" ]; then
            echo -e "   [${elapsed}s] ${GREEN}✅ HTTP 200 OK${NC}"
            return 0
        fi

        # Показываем код только при изменении
        echo -e "   [${elapsed}s] HTTP: ${http_code}"

        sleep "$CHECK_INTERVAL"
        elapsed=$((elapsed + CHECK_INTERVAL))
    done

    echo -e "   ${RED}❌ HTTP не ответил за ${HTTP_TIMEOUT}s${NC}"
    return 1
}

# ============================================================
# ПЕРЕЗАПУСК СЕРВИСА
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 Перезапуск ${SERVICE_NAME}${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"

# Перезапускаем
sudo systemctl restart "$SERVICE_NAME"

# Проверяем, что команда restart не упала
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Ошибка команды systemctl restart${NC}"
    show_status
    show_logs
    exit 1
fi

# ============================================================
# ОЖИДАНИЕ ACTIVE (RUNNING)
# ============================================================

wait_for_active
ACTIVE_RESULT=$?

if [ "$ACTIVE_RESULT" -eq 1 ]; then
    # Сервис упал
    echo ""
    echo -e "${RED}════════════════════════════════════════${NC}"
    echo -e "${RED}❌ СЕРВИС УПАЛ ПРИ СТАРТЕ${NC}"
    echo -e "${RED}════════════════════════════════════════${NC}"
    show_status
    show_logs
    exit 1

elif [ "$ACTIVE_RESULT" -eq 2 ]; then
    # Таймаут
    echo ""
    echo -e "${RED}════════════════════════════════════════${NC}"
    echo -e "${RED}❌ ТАЙМАУТ ОЖИДАНИЯ СТАРТА${NC}"
    echo -e "${RED}════════════════════════════════════════${NC}"
    show_status
    show_logs
    exit 2
fi

# ============================================================
# ОЖИДАНИЕ HTTP
# ============================================================

wait_for_http
HTTP_RESULT=$?

if [ "$HTTP_RESULT" -ne 0 ]; then
    echo ""
    echo -e "${RED}════════════════════════════════════════${NC}"
    echo -e "${RED}❌ HTTP-СЕРВЕР НЕ ОТВЕЧАЕТ${NC}"
    echo -e "${RED}════════════════════════════════════════${NC}"
    echo -e "${YELLOW}   Порт: ${SBP_MQ_PORT}${NC}"
    echo -e "${YELLOW}   Возможно, приложение падает при инициализации${NC}"
    show_status
    show_logs
    exit 3
fi

# ============================================================
# УСПЕХ
# ============================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ СЕРВИС УСПЕШНО ЗАПУЩЕН${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "   Сервис:     ${GREEN}${SERVICE_NAME}${NC}"
echo -e "   HTTP:       ${GREEN}http://localhost:${SBP_MQ_PORT}${NC}"
echo -e "   Мониторинг: ${GREEN}http://localhost:${SBP_MQ_PORT}/monitor${NC}"
echo ""

# Показываем последние строки логов для подтверждения
echo -e "${YELLOW}📋 Последние 10 строк логов:${NC}"
sudo journalctl -u "$SERVICE_NAME" -n 10 --no-pager 2>/dev/null || true
echo ""

exit 0