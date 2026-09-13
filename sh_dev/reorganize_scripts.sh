#!/bin/bash
# reorganize_scripts.sh — sh_dev/ + sh_prod/ (без sh_common)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

DEV_DIR="/var/www/html/sbp_mq_dev"

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}📁 РЕОРГАНИЗАЦИЯ СКРИПТОВ (sh_dev + sh_prod)${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

cd "$DEV_DIR"

# ============================================================
# ШАГ 1: СОЗДАТЬ ПАПКИ
# ============================================================

echo -e "${YELLOW}📁 Шаг 1: Создание папок...${NC}"
mkdir -p sh_dev sh_prod
echo -e "${GREEN}   ✅ sh_dev, sh_prod созданы${NC}"
echo ""

# ============================================================
# ШАГ 2: DEV-СКРИПТЫ
# ============================================================

echo -e "${YELLOW}📦 Шаг 2: Создание dev-скриптов в sh_dev/...${NC}"

# restart_dev.sh
cat > sh_dev/restart_dev.sh << 'EOF'
#!/bin/bash
# restart_dev.sh — перезапуск dev-сервиса (порт 8512)
sudo systemctl restart sbp_mq-dev.service
echo "✅ Dev перезапущен"
sleep 5
echo -n "Health: "
timeout 5 curl -s http://localhost:8512/health | jq -c . 2>/dev/null || echo "❌"
EOF
chmod +x sh_dev/restart_dev.sh
echo "   ✅ sh_dev/restart_dev.sh"

# restart_dev_workers.sh
cat > sh_dev/restart_dev_workers.sh << 'EOF'
#!/bin/bash
# restart_dev_workers.sh — перезапуск dev-воркеров
sudo bash -c 'systemctl restart sbp_mq-dev-worker*'
echo "✅ Dev-воркеры перезапущены"
sleep 3
sudo bash -c 'systemctl status sbp_mq-dev-worker* --no-pager' | grep -E '●|Active:'
EOF
chmod +x sh_dev/restart_dev_workers.sh
echo "   ✅ sh_dev/restart_dev_workers.sh"

# status_dev.sh
cat > sh_dev/status_dev.sh << 'EOF'
#!/bin/bash
# status_dev.sh — статус dev-сервисов
echo "=== sbp_mq-dev ==="
sudo systemctl status sbp_mq-dev.service --no-pager | grep -E 'Active:|Main PID:'
echo ""
echo "=== sbp_mq-dev-worker* ==="
sudo bash -c 'systemctl status sbp_mq-dev-worker* --no-pager' | grep -E '●|Active:|Main PID:'
EOF
chmod +x sh_dev/status_dev.sh
echo "   ✅ sh_dev/status_dev.sh"

# logs_dev.sh
cat > sh_dev/logs_dev.sh << 'EOF'
#!/bin/bash
# logs_dev.sh — логи dev
sudo journalctl -u sbp_mq-dev.service -n 30 --no-pager
EOF
chmod +x sh_dev/logs_dev.sh
echo "   ✅ sh_dev/logs_dev.sh"

# logs_dev_all.sh
cat > sh_dev/logs_dev_all.sh << 'EOF'
#!/bin/bash
# logs_dev_all.sh — агрегированный лог dev
tail -f /var/www/html/sbp_mq_dev/logs/all.log
EOF
chmod +x sh_dev/logs_dev_all.sh
echo "   ✅ sh_dev/logs_dev_all.sh"

# health_dev.sh
cat > sh_dev/health_dev.sh << 'EOF'
#!/bin/bash
# health_dev.sh — healthcheck dev
echo "=== /health ==="
timeout 5 curl -s http://localhost:8512/health | jq .
echo ""
echo "=== /health/detailed ==="
timeout 10 curl -s http://localhost:8512/health/detailed | jq .
EOF
chmod +x sh_dev/health_dev.sh
echo "   ✅ sh_dev/health_dev.sh"

# reset_dev.sh
cat > sh_dev/reset_dev.sh << 'EOF'
#!/bin/bash
# reset_dev.sh — очистка dev-данных
echo "⚠️  Будет очищено:"
echo "   - Redis DB 1"
echo "   - /sbp/mq_dev/jobs/"
echo "   - /var/www/html/sbp_mq_dev/logs/"
read -p "Продолжить? (y/n): " c
if [ "$c" != "y" ]; then echo "❌ Отменено"; exit 0; fi

redis-cli -n 1 FLUSHDB > /dev/null 2>&1
echo "✅ Redis DB 1 очищен"

rm -f /sbp/mq_dev/jobs/*.json /sbp/mq_dev/jobs/success/*.json /sbp/mq_dev/jobs/error/*.json 2>/dev/null
echo "✅ Jobs очищены"

for f in /var/www/html/sbp_mq_dev/logs/*.log; do
    [ -f "$f" ] && : > "$f"
done
echo "✅ Логи очищены"
EOF
chmod +x sh_dev/reset_dev.sh
echo "   ✅ sh_dev/reset_dev.sh"

# quick_test_dev.sh
cat > sh_dev/quick_test_dev.sh << 'EOF'
#!/bin/bash
# quick_test_dev.sh — быстрый тест dev (порт 8512)
cd /var/www/html/sbp_mq_dev
BASE_URL=http://localhost:8512 ./quick_test.sh
EOF
chmod +x sh_dev/quick_test_dev.sh
echo "   ✅ sh_dev/quick_test_dev.sh"

# test_create_payload_mq_dev.sh
cat > sh_dev/test_create_payload_mq_dev.sh << 'EOF'
#!/bin/bash
# test_create_payload_mq_dev.sh — тест create_payload_mq (порт 8512)
cd /var/www/html/sbp_mq_dev
BASE_URL=http://localhost:8512 ./test_create_payload_mq.sh
EOF
chmod +x sh_dev/test_create_payload_mq_dev.sh
echo "   ✅ sh_dev/test_create_payload_mq_dev.sh"

# test_monitor_dev.sh
cat > sh_dev/test_monitor_dev.sh << 'EOF'
#!/bin/bash
# test_monitor_dev.sh — полный тест мониторинга (порт 8512)
cd /var/www/html/sbp_mq_dev
BASE_URL=http://localhost:8512 ./test_monitor_v2.sh
EOF
chmod +x sh_dev/test_monitor_dev.sh
echo "   ✅ sh_dev/test_monitor_dev.sh"

echo ""

# ============================================================
# ШАГ 3: PROD-СКРИПТЫ
# ============================================================

echo -e "${YELLOW}📦 Шаг 3: Создание prod-скриптов в sh_prod/...${NC}"

# deploy_to_prod.sh
cat > sh_prod/deploy_to_prod.sh << 'EOF'
#!/bin/bash
# deploy_to_prod.sh — merge dev → main + рестарт prod
set -e
cd /var/www/html/sbp_mq_dev
echo "📦 Push dev..."
git push origin dev

cd /var/www/html/sbp_mq
echo "🔀 Merge dev → main..."
git checkout main
git pull origin main
git merge dev
git push origin main

echo "🔄 Перезапуск prod..."
sudo systemctl restart sbp_mq-debug.service
sleep 10
echo -n "✅ PROD /health: "
timeout 5 curl -s http://localhost:8512/health | jq -c .
EOF
chmod +x sh_prod/deploy_to_prod.sh
echo "   ✅ sh_prod/deploy_to_prod.sh"

# restart_prod.sh
cat > sh_prod/restart_prod.sh << 'EOF'
#!/bin/bash
# restart_prod.sh — перезапуск prod-сервиса (порт 8512)
sudo systemctl restart sbp_mq-debug.service
echo "✅ Prod перезапущен"
sleep 5
echo -n "Health: "
timeout 5 curl -s http://localhost:8512/health | jq -c . 2>/dev/null || echo "❌"
EOF
chmod +x sh_prod/restart_prod.sh
echo "   ✅ sh_prod/restart_prod.sh"

# restart_prod_workers.sh
cat > sh_prod/restart_prod_workers.sh << 'EOF'
#!/bin/bash
# restart_prod_workers.sh — перезапуск prod-воркеров
sudo bash -c 'systemctl restart sbp_mq-worker*'
echo "✅ Prod-воркеры перезапущены"
sleep 3
sudo bash -c 'systemctl status sbp_mq-worker* --no-pager' | grep -E '●|Active:'
EOF
chmod +x sh_prod/restart_prod_workers.sh
echo "   ✅ sh_prod/restart_prod_workers.sh"

# status_prod.sh
cat > sh_prod/status_prod.sh << 'EOF'
#!/bin/bash
# status_prod.sh — статус prod-сервисов
echo "=== sbp_mq-debug ==="
sudo systemctl status sbp_mq-debug.service --no-pager | grep -E 'Active:|Main PID:'
echo ""
echo "=== sbp_mq-worker* ==="
sudo bash -c 'systemctl status sbp_mq-worker* --no-pager' | grep -E '●|Active:|Main PID:'
EOF
chmod +x sh_prod/status_prod.sh
echo "   ✅ sh_prod/status_prod.sh"

# logs_prod.sh
cat > sh_prod/logs_prod.sh << 'EOF'
#!/bin/bash
# logs_prod.sh — логи prod
sudo journalctl -u sbp_mq-debug.service -n 30 --no-pager
EOF
chmod +x sh_prod/logs_prod.sh
echo "   ✅ sh_prod/logs_prod.sh"

# health_prod.sh
cat > sh_prod/health_prod.sh << 'EOF'
#!/bin/bash
# health_prod.sh — healthcheck prod
echo "=== /health ==="
timeout 5 curl -s http://localhost:8512/health | jq .
echo ""
echo "=== /health/detailed ==="
timeout 10 curl -s http://localhost:8512/health/detailed | jq .
EOF
chmod +x sh_prod/health_prod.sh
echo "   ✅ sh_prod/health_prod.sh"

# backup_prod.sh
cat > sh_prod/backup_prod.sh << 'EOF'
#!/bin/bash
# backup_prod.sh — бэкап prod
cd /var/www/html/sbp_mq
./backup_sbp_mq.sh
EOF
chmod +x sh_prod/backup_prod.sh
echo "   ✅ sh_prod/backup_prod.sh"

echo ""

# ============================================================
# ШАГ 4: README
# ============================================================

echo -e "${YELLOW}📝 Шаг 4: README...${NC}"

cat > sh_dev/README.md << 'EOF'
# sh_dev — скрипты для DEV

Работают **только** с dev-окружением:
- Сервисы: `sbp_mq-dev.service`, `sbp_mq-dev-worker*`
- Порт: 8512
- Redis: DB 1
- Папки: `/sbp/mq_dev/`, `/var/www/html/sbp_mq_dev/`

## Скрипты

| Скрипт | Что делает |
|--------|-----------|
| `restart_dev.sh` | Перезапуск dev-сервиса |
| `restart_dev_workers.sh` | Перезапуск dev-воркеров |
| `status_dev.sh` | Статус dev-сервисов |
| `logs_dev.sh` | Логи dev (journalctl) |
| `logs_dev_all.sh` | Агрегированный лог dev |
| `health_dev.sh` | Healthcheck dev |
| `reset_dev.sh` | Очистка dev-данных |
| `quick_test_dev.sh` | Быстрый тест dev |
| `test_create_payload_mq_dev.sh` | Тест create_payload_mq dev |
| `test_monitor_dev.sh` | Полный тест мониторинга dev |
EOF

cat > sh_prod/README.md << 'EOF'
# sh_prod — скрипты для PROD

Работают **только** с prod-окружением:
- Сервисы: `sbp_mq-debug.service`, `sbp_mq-worker*`
- Порт: 8511
- Redis: DB 0
- Папки: `/sbp/mq_dev/`, `/var/www/html/sbp_mq_dev/`

## Скрипты

| Скрипт | Что делает |
|--------|-----------|
| `deploy_to_prod.sh` | Merge dev → main + рестарт prod |
| `restart_prod.sh` | Перезапуск prod-сервиса |
| `restart_prod_workers.sh` | Перезапуск prod-воркеров |
| `status_prod.sh` | Статус prod-сервисов |
| `logs_prod.sh` | Логи prod |
| `health_prod.sh` | Healthcheck prod |
| `backup_prod.sh` | Бэкап prod |

## ⚠️ ВНИМАНИЕ

Скрипты в этой папке **работают с продакшеном**! Используйте осознанно.
EOF

echo -e "${GREEN}   ✅ README для sh_dev и sh_prod${NC}"
echo ""

# ============================================================
# ИТОГ
# ============================================================

echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 РЕОРГАНИЗАЦИЯ ЗАВЕРШЕНА${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

echo "=== sh_dev/ ==="
ls -la sh_dev/
echo ""
echo "=== sh_prod/ ==="
ls -la sh_prod/
echo ""
echo "=== Корень (общие) ==="
ls -la *.sh 2>/dev/null | head -10
echo ""

echo -e "${YELLOW}📋 Структура:${NC}"
echo ""
echo "sh_dev/    — скрипты для dev (порт 8512)"
echo "sh_prod/   — скрипты для prod (порт 8512)"
echo "корень/    — run_debug.sh (параметризованный, работает в обоих)"
echo ""

echo -e "${GREEN}✅ Готово${NC}"