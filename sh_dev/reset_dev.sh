#!/bin/bash
# reset_dev.sh — очистка dev-данных
echo "⚠️  Будет очищено:"
echo "   - Redis DB 1"
echo "   - /sbp/mq_dev/jobs/"
echo "   - /var/www/html/sbp_mq_dev/logs/"
read -p "Продолжить? (y/n): " c
if [ "$c" != "y" ]; then echo "❌ Отменено"; exit 0; fi

redis-cli -n 1 FLUSHDB > /dev/null 2>&1
echo "✅ Redis DB 1 очищен"

rm -f /sbp/mq_dev/jobs/*.json /sbp/mq_dev/jobs/success/*.json /sbp/mq_dev/jobs/error/*.json 2>/dev/null
echo "✅ Jobs очищены"

for f in /var/www/html/sbp_mq_dev/logs/*.log; do
    [ -f "$f" ] && : > "$f"
done
echo "✅ Логи очищены"
