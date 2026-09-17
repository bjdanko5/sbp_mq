#!/bin/bash
# deploy_to_prod.sh — деплой dev → prod
#
# Логика портов:
#   - DEV  .env → $SBP_MQ_PORT (8512) — для проверки DEV (не используется здесь)
#   - PROD .env → $SBP_MQ_PORT (8511) — для проверки PROD и healthcheck
#
# ⚠️ ВАЖНО: после загрузки DEV .env делаем load_env "$PROD_DIR",
#    чтобы $SBP_MQ_PORT указывал на PROD (8511).

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

# Запоминаем DEV-порт (только для лога)
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

cd "$PROD_DIR"
echo ""
echo -e "${YELLOW}🔀 Merge dev → main в PROD${NC}"

git checkout main
git pull origin main
git merge dev
git push origin main

echo -e "${GREEN}✅ Merge выполнен${NC}"

# ============================================================
# ПЕРЕЗАПУСК PROD
# ============================================================

echo ""
echo -e "${YELLOW}🔄 Перезапуск sbp_mq-debug.service${NC}"
sudo systemctl restart sbp_mq-debug.service
sleep 10

# ============================================================
# HEALTHCHECK
# ============================================================

echo ""
echo -e "${GREEN}🎉 ДЕПЛОЙ ЗАВЕРШЁН${NC}"
echo ""
echo -n "PROD (:$PROD_PORT) /health: "
timeout 5 curl -s "http://localhost:${PROD_PORT}/health" | jq -c . 2>/dev/null || echo "❌"
echo ""
