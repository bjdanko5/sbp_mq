#!/bin/bash
# reset_dev.sh — очистка dev-данных

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

echo "⚠️  Будет очищено:"
echo "   - Redis DB $REDIS_DB"
echo "   - $SBP_ROOT4MQ/jobs/"
echo "   - $LOG_DIR/"
read -p "Продолжить? (y/n): " c
if [ "$c" != "y" ]; then echo "❌ Отменено"; exit 0; fi

redis-cli -n "$REDIS_DB" FLUSHDB > /dev/null 2>&1
echo "✅ Redis DB $REDIS_DB очищен"

rm -f "$SBP_ROOT4MQ/jobs/"*.json "$SBP_ROOT4MQ/jobs/success/"*.json "$SBP_ROOT4MQ/jobs/error/"*.json 2>/dev/null
echo "✅ Jobs очищены"

for f in "$LOG_DIR"/*.log; do
    [ -f "$f" ] && : > "$f"
done
echo "✅ Логи очищены"
