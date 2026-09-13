#!/bin/bash
cd /var/www/html/sbp_mq
source .venv/bin/activate
sudo journalctl -u sbp_mq-debug.service -f