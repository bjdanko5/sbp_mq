#!/bin/bash
# restart_dev_workers.sh — перезапуск dev-воркеров
sudo bash -c 'systemctl restart sbp_mq-dev-worker*'
echo "✅ Dev-воркеры перезапущены"
sleep 3
sudo bash -c 'systemctl status sbp_mq-dev-worker* --no-pager' | grep -E '●|Active:'
