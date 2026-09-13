#!/bin/bash
# deploy_to_prod.sh — деплой из dev в prod
#
# ВАЖНО: запускать из sbp_mq_dev (или через ../deploy.sh)
#
# Что делает:
#   1. Проверка: dev чист (всё закоммичено)
#   2. Проверка: prod не обрабатывает задания
#   3. Push dev → GitHub
#   4. Merge dev → main
#   5. Push main → GitHub
#   6. Перезапуск prod
#   7. Healthcheck
#   8. Итог

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEV_DIR="/var/www/html/sbp_mq_dev"
PROD_DIR="/var/www/html/sbp_mq"

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🚀 ДЕПЛОЙ DEV → PROD${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# ============================================================
# ШАГ 1: ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================

echo -e "${YELLOW}🔍 Шаг 1: Проверка окружения...${NC}"

CURRENT_DIR="$(pwd)"
if [ "$CURRENT_DIR" != "$DEV_DIR" ]; then
    echo -e "${RED}   ❌ Скрипт запущен не из $DEV_DIR${NC}"
    echo -e "${YELLOW}   Текущая папка: $CURRENT_DIR${NC}"
    echo -e "${YELLOW}   Запустите: cd $DEV_DIR && ./deploy.sh${NC}"
    exit 1
fi
echo -e "${GREEN}   ✅ Мы в dev-папке${NC}"
echo ""

# ============================================================
# ШАГ 2: ПРОВЕРКА DEV (git status)
# ============================================================

echo -e "${YELLOW}🔍 Шаг 2: Проверка dev (git status)...${NC}"

cd "$DEV_DIR"

if [ -n "$(git status --short)" ]; then
    echo -e "${RED}   ❌ В dev есть незакоммиченные изменения:${NC}"
    git status --short
    echo ""
    echo -e "${YELLOW}   Закоммитьте их перед деплоем:${NC}"
    echo "   git add -A"
    echo "   git commit -m '...'"
    exit 1
fi
echo -e "${GREEN}   ✅ Dev — working tree clean${NC}"

CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "dev" ]; then
    echo -e "${RED}   ❌ Текущая ветка: $CURRENT_BRANCH (ожидается dev)${NC}"
    exit 1
fi
echo -e "${GREEN}   ✅ Ветка: dev${NC}"

UNPUSHED=$(git log origin/dev..dev --oneline 2>/dev/null | wc -l)
if [ "$UNPUSHED" -gt 0 ]; then
    echo -e "${GREEN}   ✅ Есть $UNPUSHED коммитов для деплоя${NC}"
    echo "   Коммиты:"
    git log origin/dev..dev --oneline | head -10 | sed 's/^/      /'
else
    echo -e "${YELLOW}   ⚠️  Нет новых коммитов (dev = origin/dev)${NC}"
fi
echo ""

# ============================================================
# ШАГ 3: ПРОВЕРКА PROD (processing)
# ============================================================

echo -e "${YELLOW}🔍 Шаг 3: Проверка prod (processing)...${NC}"

PROCESSING=$(timeout 5 curl -s http://localhost:8511/monitor/data 2>/dev/null | jq -r '.processing_count // 0' 2>/dev/null || echo "0")

if [ "$PROCESSING" != "0" ] && [ "$PROCESSING" != "" ]; then
    echo -e "${RED}   ❌ Prod обрабатывает $PROCESSING заданий!${NC}"
    echo -e "${YELLOW}   Дождитесь завершения или остановите вручную${NC}"
    exit 1
fi
echo -e "${GREEN}   ✅ Prod свободен${NC}"
echo ""

# ============================================================
# ШАГ 4: PUSH DEV В GITHUB
# ============================================================

echo -e "${YELLOW}📤 Шаг 4: Push dev в GitHub...${NC}"

cd "$DEV_DIR"
git push origin dev
echo -e "${GREEN}   ✅ Dev запушен в GitHub${NC}"
echo ""

# ============================================================
# ШАГ 5: MERGE DEV → MAIN
# ============================================================

echo -e "${YELLOW}🔀 Шаг 5: Merge dev → main...${NC}"

cd "$PROD_DIR"

git checkout main
git pull origin main

if git merge dev; then
    echo -e "${GREEN}   ✅ Merge выполнен${NC}"
else
    echo -e "${RED}   ❌ Конфликт merge! Разрешите вручную.${NC}"
    exit 1
fi

git push origin main
echo -e "${GREEN}   ✅ Main запушен в GitHub${NC}"
echo ""

# ============================================================
# ШАГ 6: ПЕРЕЗАПУСК PROD
# ============================================================

echo -e "${YELLOW}🔄 Шаг 6: Перезапуск prod...${NC}"

sudo systemctl restart sbp_mq-debug.service
echo "   Перезапуск API..."
sleep 20
echo -e "${GREEN}   ✅ Prod перезапущен${NC}"
echo ""

# ============================================================
# ШАГ 7: HEALTHCHECK
# ============================================================

echo -e "${YELLOW}🏥 Шаг 7: Healthcheck...${NC}"
echo ""

echo -n "   PROD /health:  "
timeout 5 curl -s http://localhost:8511/health | jq -c . 2>/dev/null || echo "❌"
echo ""

echo "   PROD /health/detailed:"
timeout 10 curl -s http://localhost:8511/health/detailed 2>/dev/null | jq -c '{status, queue: .components.rabbitmq.queue, db: .components.redis.db, workers: .components.workers.active}' 2>/dev/null || echo "   ❌"
echo ""

# ============================================================
# ШАГ 8: ИТОГ
# ============================================================

echo -e "${YELLOW}🧪 Шаг 8: Итог...${NC}"
echo ""

echo "   Git:"
cd "$PROD_DIR"
echo "      PROD: $(git branch --show-current) @ $(git --no-pager log --oneline -1)"
cd "$DEV_DIR"
echo "      DEV:  $(git branch --show-current) @ $(git --no-pager log --oneline -1)"
echo ""

echo "   Изоляция:"
echo "      PROD DB 0: $(redis-cli -n 0 DBSIZE) ключей"
echo "      DEV  DB 1: $(redis-cli -n 1 DBSIZE) ключей"
echo ""

echo "   Сервисы:"
echo -n "      PROD: "
sudo systemctl is-active sbp_mq-debug.service
echo -n "      DEV:  "
sudo systemctl is-active sbp_mq-dev.service
echo ""

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 ДЕПЛОЙ ЗАВЕРШЁН${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo "✅ Dev → GitHub → main → Prod"
echo ""
echo "📋 Проверка:"
echo "   - PROD /health:  http://192.168.10.130:8511/health"
echo "   - PROD /monitor: http://192.168.10.130:8511/monitor"
echo ""