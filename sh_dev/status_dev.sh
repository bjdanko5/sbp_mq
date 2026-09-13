#!/bin/bash
# status_dev.sh — статус dev-сервисов
echo "=== sbp_mq-dev ==="
sudo systemctl status sbp_mq-dev.service --no-pager | grep -E 'Active:|Main PID:'
echo ""
echo "=== sbp_mq-dev-worker* ==="
sudo bash -c 'systemctl status sbp_mq-dev-worker* --no-pager' | grep -E '●|Active:|Main PID:'
