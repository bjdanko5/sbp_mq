#!/bin/bash
# logs_dev.sh — логи dev
sudo journalctl -u sbp_mq-dev.service -n 30 --no-pager
