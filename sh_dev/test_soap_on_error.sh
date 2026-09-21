#!/bin/bash
# test_soap_on_error.sh — проверка SOAP при ошибке Job (успешный ответ 1С)

cd /var/www/html/sbp_mq_dev

# ⚠️ База zkh_ursv СУЩЕСТВУЕТ на SOAP → ожидаем ✅
BANK="ci"
BASE="zkh_ursv"
JOB_ID=88806
REQ_ID="88806001"

echo "=== Подготовка ==="
echo "Bank: $BANK, Base: $BASE, Job: $JOB_ID, Req: $REQ_ID"

# Очистка файлов
rm -f "/sbp/mq_dev/$BANK/$BASE/$JOB_ID.json" 2>/dev/null
rm -f "/sbp/mq_dev/jobs/$BANK@$BASE@$JOB_ID.json" 2>/dev/null
rm -f "/sbp/mq_dev/jobs/error/$BANK@$BASE@$JOB_ID.json" 2>/dev/null
rm -f "/sbp/mq_dev/jobs/success/$BANK@$BASE@$JOB_ID.json" 2>/dev/null

# Очистка Redis-следов
for pattern in "*${JOB_ID}*" "*${REQ_ID}*"; do
    redis-cli -n 1 --scan --pattern "$pattern" 2>/dev/null | while read key; do
        redis-cli -n 1 del "$key" > /dev/null
    done
done

# Truncate логов
> logs/sbp-dev.log
> logs/sbp-dev_errors.log
> logs/all.log

# Создать папку
mkdir -p "/sbp/mq_dev/$BANK/$BASE"

echo ""
echo "=== Создание файлов ==="

# Валидный JSON, amount < 0 → 400 от mockapi
cat > "/sbp/mq_dev/$BANK/$BASE/$JOB_ID.json" << EOF
[{"requestId":"$REQ_ID","amount":-100}]
EOF

# Валидный Job
cat > "/sbp/mq_dev/jobs/$BANK@$BASE@$JOB_ID.json" << EOF
{
  "bank": "$BANK", "base": "$BASE", "job_id": $JOB_ID,
  "job_name": "SOAP OK Test (zkh_ursv)", "created_at": "2026-09-21T15:50:00",
  "files": [{"filename": "$JOB_ID.json", "count": 1, "request_ids": ["$REQ_ID"]}],
  "total_requests": 1, "status": "pending"
}
EOF

echo "  ✅ $JOB_ID.json"
echo "  ✅ $BANK@$BASE@$JOB_ID.json"

echo ""
echo "=== Публикация Job ==="
PUBLISH_RESULT=$(curl -s "http://localhost:8512/create_payload_mq/$BANK/$BASE/$JOB_ID")
echo "$PUBLISH_RESULT" | jq '.data | {task_id, job_id, status_url}'

TASK_ID=$(echo "$PUBLISH_RESULT" | jq -r '.data.task_id')
if [ "$TASK_ID" = "null" ] || [ -z "$TASK_ID" ]; then
    echo ""
    echo "❌ Публикация НЕ удалась:"
    echo "$PUBLISH_RESULT" | jq .
    exit 1
fi

echo ""
echo "=== Ожидание обработки (5 сек) ==="
sleep 5

echo ""
echo "=== Статус Job через API ==="
curl -s "http://localhost:8512/create_payload_mq/$BANK/$BASE/$JOB_ID/status" | jq '.data | {status, message}'

echo ""
echo "=== Job в error/ ==="
if [ -f "/sbp/mq_dev/jobs/error/$BANK@$BASE@$JOB_ID.json" ]; then
    echo "✅ Job в error/"
else
    echo "❌ Job НЕ в error/"
fi

echo ""
echo "=== task:* в Redis ==="
redis-cli -n 1 get "task:$TASK_ID" | jq '{status, error, summary}' 2>/dev/null || echo "(нет данных)"

echo ""
echo "════════════════════════════════════════"
echo "🔥 SOAP Notify в логах:"
echo "════════════════════════════════════════"
grep "SOAP Notify" logs/sbp-dev.log

echo ""
echo "════════════════════════════════════════"
echo "📋 Полный лог Job $JOB_ID:"
echo "════════════════════════════════════════"
grep "$JOB_ID" logs/sbp-dev.log

echo ""
echo "════════════════════════════════════════"
echo "📋 Логи worker'а:"
echo "════════════════════════════════════════"
grep "ОШИБКА Job\|ВЗЯЛ Job" logs/sbp-dev.log | tail -10