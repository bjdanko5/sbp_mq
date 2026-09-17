#!/bin/bash
# deploy_to_prod.sh — деплой dev → prod

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"

# Загружаем .env из DEV
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 ДЕПЛОЙ DEV → PROD${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo "   DEV_DIR:  $DEV_DIR"
echo "   PROD_DIR: $PROD_DIR"
echo "   Порт:     $SBP_MQ_PORT"
echo ""

# Проверка окружения
CURRENT_DIR="$(pwd)"
if [ "$CURRENT_DIR" != "$DEV_DIR" ]; then
    echo -e "${RED}❌ Запустите из $DEV_DIR${NC}"
    exit 1
fi

# Проверка git status
cd "$DEV_DIR"
if [ -n "$(git status --short)" ]; then
    echo -e "${RED}❌ В dev есть незакоммиченные изменения:${NC}"
    git status --short
    exit 1
fi
echo -e "${GREEN}✅ Dev чист${NC}"

# Проверка prod — не обрабатывает
PROCESSING=$(timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/monitor/data" 2>/dev/null | jq -r '.processing_count // 0' 2>/dev/null || echo "0")
if [ "$PROCESSING" != "0" ] && [ "$PROCESSING" != "" ]; then
    echo -e "${RED}❌ Prod обрабатывает $PROCESSING заданий!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Prod свободен${NC}"

# Push dev
git push origin dev
echo -e "${GREEN}✅ Dev запушен${NC}"

# Merge в prod
cd "$PROD_DIR"
git checkout main
git pull origin main
git merge dev
git push origin main
echo -e "${GREEN}✅ Merge выполнен${NC}"

# Перезапуск prod
sudo systemctl restart sbp_mq-debug.service
sleep 10

echo ""
echo -e "${GREEN}🎉 ДЕПЛОЙ ЗАВЕРШЁН${NC}"
echo ""
echo -n "PROD /health: "
timeout 5 curl -s "http://localhost:${SBP_MQ_PORT}/health" | jq -c . 2>/dev/null || echo "❌"
echo ""
