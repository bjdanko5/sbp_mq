#!/bin/bash
# test_soap_on_error.sh — проверка SOAP при ошибке Job (успешный ответ 1С)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

cd "$PROJECT_DIR" || exit 1

# ⚠️ База zkh_ursv СУЩЕСТВУЕТ на SOAP → ожидаем ✅
BANK="ci"
BASE="zkh_ursv"
JOB_ID=88806
REQ_ID="88806001"

echo "=== Подготовка ==="
echo "Bank: $BANK, Base: $BASE, Job: $JOB_ID, Req: $REQ_ID"
echo "PROJECT_DIR: $PROJECT_DIR"
echo "SBP_ROOT4MQ: $SBP_ROOT4MQ"
echo "SBP_MQ_PORT: $SBP_MQ_PORT"
echo "REDIS_DB:    $REDIS_DB"

# Очистка файлов
rm -f "$SBP_ROOT4MQ/$BANK/$BASE/$JOB_ID.json" 2>/dev/null
rm -f "$SBP_ROOT4MQ/jobs/$BANK@$BASE@$JOB_ID.json" 2>/dev/null
rm -f "$SBP_ROOT4MQ/jobs/error/$BANK@$BASE@$JOB_ID.json" 2>/dev/null
rm -f "$SBP_ROOT4MQ/jobs/success/$BANK@$BASE@$JOB_ID.json" 2>/dev/null

# Очистка Redis-следов
for pattern in "*${JOB_ID}*" "*${REQ_ID}*"; do
    redis-cli -n "$REDIS_DB" --scan --pattern "$pattern" 2>/dev/null | while read key; do
        redis-cli -n "$REDIS_DB" del "$key" > /dev/null
    done
done

# Truncate логов
> "$LOG_DIR/${LOG_NAME}.log"
> "$LOG_DIR/${LOG_NAME}_errors.log"
> "$LOG_DIR/all.log"

# Создать папку
mkdir -p "$SBP_ROOT4MQ/$BANK/$BASE"

echo ""
echo "=== Создание файлов ==="

cat > "$SBP_ROOT4MQ/$BANK/$BASE/$JOB_ID.json" << EOF
[{"requestId":"$REQ_ID","amount":-100}]
EOF

cat > "$SBP_ROOT4MQ/jobs/$BANK@$BASE@$JOB_ID.json" << EOF
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
PUBLISH_RESULT=$(curl -s "http://localhost:${SBP_MQ_PORT}/create_payload_mq/$BANK/$BASE/$JOB_ID")
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
curl -s "http://localhost:${SBP_MQ_PORT}/create_payload_mq/$BANK/$BASE/$JOB_ID/status" | jq '.data | {status, message}'

echo ""
echo "=== Job в error/ ==="
if [ -f "$SBP_ROOT4MQ/jobs/error/$BANK@$BASE@$JOB_ID.json" ]; then
    echo "✅ Job в error/"
else
    echo "❌ Job НЕ в error/"
fi

echo ""
echo "=== task:* в Redis ==="
redis-cli -n "$REDIS_DB" get "task:$TASK_ID" | jq '{status, error, summary}' 2>/dev/null || echo "(нет данных)"

echo ""
echo "════════════════════════════════════════"
echo "🔥 SOAP Notify в логах:"
echo "════════════════════════════════════════"
grep "SOAP Notify" "$LOG_DIR/${LOG_NAME}.log"

echo ""
echo "════════════════════════════════════════"
echo "📋 Полный лог Job $JOB_ID:"
echo "════════════════════════════════════════"
grep "$JOB_ID" "$LOG_DIR/${LOG_NAME}.log"

echo ""
echo "════════════════════════════════════════"
echo "📋 Логи worker'а:"
echo "════════════════════════════════════════"
grep "ОШИБКА Job\|ВЗЯЛ Job" "$LOG_DIR/${LOG_NAME}.log" | tail -10