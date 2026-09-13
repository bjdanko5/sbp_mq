#!/bin/bash
# logs_prod.sh — логи prod
sudo journalctl -u sbp_mq-debug.service -n 30 --no-pager
