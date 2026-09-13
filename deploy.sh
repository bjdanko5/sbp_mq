#!/bin/bash
# deploy.sh — деплой из dev в prod
#
# Обёртка для sh_prod/deploy_to_prod.sh
#
# Использование:
#   cd /var/www/html/sbp_mq_dev
#   ./deploy.sh
#
# Что делает:
#   1. Проверяет, что dev чист
#   2. Проверяет, что prod свободен
#   3. Push dev в GitHub
#   4. Merge dev → main
#   5. Push main в GitHub
#   6. Перезапускает prod
#   7. Healthcheck

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec ./sh_prod/deploy_to_prod.sh "$@"