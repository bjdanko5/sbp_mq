#!/bin/bash
# restart_dev.sh — перезапуск dev-сервиса (порт 8512)
sudo systemctl restart sbp_mq-dev.service
echo "✅ Dev перезапущен"
sleep 5
echo -n "Health: "
timeout 5 curl -s http://localhost:8512/health | jq -c . 2>/dev/null || echo "❌"
