#!/bin/bash
# deploy_to_prod.sh — деплой dev → prod
#
# Логика портов:
#   - DEV  .env → $SBP_MQ_PORT (8512) — только для лога
#   - PROD .env → $SBP_MQ_PORT (8511) — для проверки PROD и healthcheck
#
# ⚠️ ВАЖНО: проекты используют git worktree (общий .git):
#   - $DEV_DIR  → worktree с веткой dev
#   - $PROD_DIR → worktree с веткой main
#   - Ветки dev и main — общие, не могут быть checked out в двух папках одновременно.
#
# Healthcheck: ретраи 30×1 сек (ждём полной инициализации uvicorn+debugpy).

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================================
# ЗАГРУЗКА DEV .env (для PROD_DIR)
# ============================================================

source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1
DEV_PORT="$SBP_MQ_PORT"

# ============================================================
# ЗАГРУЗКА PROD .env (для корректного $SBP_MQ_PORT)
# ============================================================

if [ ! -d "$PROD_DIR" ]; then
    echo -e "${RED}❌ PROD_DIR не существует: $PROD_DIR${NC}"
    exit 1
fi

if [ ! -f "$PROD_DIR/.env" ]; then
    echo -e "${RED}❌ PROD .env не найден: $PROD_DIR/.env${NC}"
    exit 1
fi

source "$DEV_DIR/sh_common/load_env.sh" "$PROD_DIR" || exit 1
PROD_PORT="$SBP_MQ_PORT"

# ============================================================
# ШАПКА
# ============================================================

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 ДЕПЛОЙ DEV → PROD${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo "   DEV_DIR:   $DEV_DIR"
echo "   PROD_DIR:  $PROD_DIR"
echo "   DEV_PORT:  $DEV_PORT"
echo "   PROD_PORT: $PROD_PORT"
echo ""

# ============================================================
# ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================

CURRENT_DIR="$(pwd)"
if [ "$CURRENT_DIR" != "$DEV_DIR" ]; then
    echo -e "${RED}❌ Запустите из $DEV_DIR${NC}"
    exit 1
fi

# ============================================================
# ПРОВЕРКА WORKTREE (DEV=dev, PROD=main)
# ============================================================

DEV_BRANCH=$(cd "$DEV_DIR" && git branch --show-current 2>/dev/null || echo "?")
PROD_BRANCH=$(cd "$PROD_DIR" && git branch --show-current 2>/dev/null || echo "?")

if [ "$DEV_BRANCH" != "dev" ]; then
    echo -e "${RED}❌ $DEV_DIR не на ветке 'dev' (текущая: $DEV_BRANCH)${NC}"
    exit 1
fi

if [ "$PROD_BRANCH" != "main" ]; then
    echo -e "${RED}❌ $PROD_DIR не на ветке 'main' (текущая: $PROD_BRANCH)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Worktree: DEV=$DEV_BRANCH, PROD=$PROD_BRANCH${NC}"

# ============================================================
# ПРОВЕРКА DEV — git status
# ============================================================

cd "$DEV_DIR"
if [ -n "$(git status --short)" ]; then
    echo -e "${RED}❌ В dev есть незакоммиченные изменения:${NC}"
    git status --short
    exit 1
fi
echo -e "${GREEN}✅ Dev чист${NC}"

# ============================================================
# ПРОВЕРКА PROD — git status
# ============================================================

cd "$PROD_DIR"
if [ -n "$(git status --short)" ]; then
    echo -e "${RED}❌ В prod есть незакоммиченные изменения:${NC}"
    git status --short
    echo -e "${YELLOW}   Откатите: cd $PROD_DIR && git checkout -- .${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Prod чист${NC}"

# ============================================================
# ПРОВЕРКА PROD — не обрабатывает задачи
# ============================================================

PROCESSING=$(timeout 5 curl -s "http://localhost:${PROD_PORT}/monitor/data" 2>/dev/null \
    | jq -r '.processing_count // 0' 2>/dev/null || echo "0")

if [ "$PROCESSING" != "0" ] && [ "$PROCESSING" != "" ]; then
    echo -e "${RED}❌ Prod обрабатывает $PROCESSING заданий!${NC}"
    echo -e "${YELLOW}   Дождитесь завершения или проверьте:${NC}"
    echo "   curl -s http://localhost:${PROD_PORT}/monitor/data | jq ."
    exit 1
fi
echo -e "${GREEN}✅ Prod свободен${NC}"

# ============================================================
# PUSH DEV → GITHUB
# ============================================================

cd "$DEV_DIR"
echo ""
echo -e "${YELLOW}📤 Push dev → origin/dev${NC}"
git push origin dev
echo -e "${GREEN}✅ Dev запушен${NC}"

# ============================================================
# MERGE DEV → MAIN В PROD
# ============================================================
# PROD привязан к ветке main через worktree — checkout не нужен.

cd "$PROD_DIR"
echo ""
echo -e "${YELLOW}🔀 Merge dev → main в PROD${NC}"

git pull origin main
git merge dev
git push origin main

echo -e "${GREEN}✅ Merge выполнен${NC}"

# ============================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ (pip install)
# ============================================================

cd "$PROD_DIR"
echo ""
echo -e "${YELLOW}📦 Установка зависимостей (requirements.txt)...${NC}"

if [ ! -d ".venv" ]; then
    echo -e "${RED}❌ .venv не найден в $PROD_DIR${NC}"
    exit 1
fi

source .venv/bin/activate
pip install -r requirements.txt --quiet 2>&1 | tail -3
deactivate
echo -e "${GREEN}✅ Зависимости установлены${NC}"

# ============================================================
# ПЕРЕЗАПУСК PROD
# ============================================================

echo ""
echo -e "${YELLOW}🔄 Перезапуск sbp_mq-debug.service${NC}"
sudo systemctl restart sbp_mq-debug.service

# ============================================================
# HEALTHCHECK С РЕТРАЯМИ
# ============================================================

echo ""
echo -e "${YELLOW}⏳ Ожидание HTTP на порту ${PROD_PORT}...${NC}"

HEALTH_OK=0
for i in $(seq 1 30); do
    code=$(timeout 2 curl -s -o /dev/null -w "%{http_code}" \
        "http://localhost:${PROD_PORT}/health" 2>/dev/null || true)
    code="${code:-000}"

    if [ "$code" = "200" ]; then
        echo -e "   [${i}/30] ${GREEN}✅ HTTP 200${NC}"
        HEALTH_OK=1
        break
    fi

    if [ "$i" -eq 1 ] || [ $((i % 5)) -eq 0 ]; then
        echo -e "   [${i}/30] HTTP: ${code}"
    fi
    sleep 1
done

# ============================================================
# РЕЗУЛЬТАТ
# ============================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 ДЕПЛОЙ ЗАВЕРШЁН${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""

if [ "$HEALTH_OK" -eq 1 ]; then
    echo -n "PROD (:$PROD_PORT) /health:     "
    timeout 5 curl -s "http://localhost:${PROD_PORT}/health" | jq -c . 2>/dev/null || echo "❌"

    echo -n "PROD (:$PROD_PORT) /health/detailed: "
    timeout 10 curl -s "http://localhost:${PROD_PORT}/health/detailed" \
        | jq -c '{status, queue: .components.rabbitmq.queue, db: .components.redis.db, workers: .components.workers.active}' 2>/dev/null || echo "❌"
else
    echo -e "${RED}❌ PROD не поднялся за 30 сек!${NC}"
    echo ""
    echo -e "${YELLOW}📋 Последние 30 строк логов:${NC}"
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    sudo journalctl -u sbp_mq-debug.service -n 30 --no-pager 2>/dev/null || true
    echo -e "${BLUE}────────────────────────────────────────${NC}"
    exit 1
fi

echo ""