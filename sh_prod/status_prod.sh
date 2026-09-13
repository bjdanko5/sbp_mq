#!/bin/bash
# status_prod.sh — статус prod-сервисов
echo "=== sbp_mq-debug ==="
sudo systemctl status sbp_mq-debug.service --no-pager | grep -E 'Active:|Main PID:'
echo ""
echo "=== sbp_mq-worker* ==="
sudo bash -c 'systemctl status sbp_mq-worker* --no-pager' | grep -E '●|Active:|Main PID:'
