#!/bin/bash
# restart_prod_workers.sh — перезапуск prod-воркеров
sudo bash -c 'systemctl restart sbp_mq-worker*'
echo "✅ Prod-воркеры перезапущены"
sleep 3
sudo bash -c 'systemctl status sbp_mq-worker* --no-pager' | grep -E '●|Active:'
