#!/bin/bash
# restart_prod.sh — перезапуск prod-сервиса (порт 8511)
sudo systemctl restart sbp_mq-debug.service
echo "✅ Prod перезапущен"
sleep 5
echo -n "Health: "
timeout 5 curl -s http://localhost:8511/health | jq -c . 2>/dev/null || echo "❌"
