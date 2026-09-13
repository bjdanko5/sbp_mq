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
timeout 5 curl -s http://localhost:8511/health | jq -c .
