#!/bin/bash
# test_create_payload_mq.sh — тест create_payload_mq (dev)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

BASE_URL="http://localhost:${SBP_MQ_PORT}"
BANK="ci"
BASE="zkh_ursv"
JOB_ID=999

echo "🧪 ТЕСТ create_payload_mq (порт $SBP_MQ_PORT)"
echo "=========================="
echo ""

# ============================================================
# ПОДГОТОВКА
# ============================================================

echo "📁 Подготовка тестовых файлов..."

sudo mkdir -p $SBP_ROOT4MQ/ci/zkh_ursv
sudo chown -R user:user $SBP_ROOT4MQ/ci

cat > $SBP_ROOT4MQ/ci/zkh_ursv/7845.json << 'JSON_EOF'
[
  {"requestId": "754316", "amount": 100},
  {"requestId": "754318", "amount": 200}
]
JSON_EOF

rm -f $SBP_ROOT4MQ/jobs/error/ci@zkh_ursv@999.json
rm -f $SBP_ROOT4MQ/jobs/ci@zkh_ursv@999.json

cat > $SBP_ROOT4MQ/jobs/ci@zkh_ursv@999.json << 'JOB_EOF'
{
  "bank": "ci",
  "base": "zkh_ursv",
  "job_id": 999,
  "job_name": "Тестовый Job для проверки MQ",
  "created_at": "2026-09-08T12:00:00",
  "files": [
    {
      "filename": "7845.json",
      "count": 2,
      "request_ids": ["754316", "754318"]
    }
  ],
  "total_requests": 2,
  "status": "pending"
}
JOB_EOF

redis-cli -n "$REDIS_DB" DEL "lock:job:ci:zkh_ursv:999" > /dev/null 2>&1

echo "   ✅ Тестовые файлы созданы"
echo ""

# ============================================================
# ТЕСТЫ
# ============================================================

echo "1. Статус Job:"
curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID/status" | jq .
echo ""

echo "2. Создание Job:"
RESPONSE=$(curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID")
echo "$RESPONSE" | jq .
TASK_ID=$(echo "$RESPONSE" | jq -r '.data.task_id // empty')
if [ -n "$TASK_ID" ] && [ "$TASK_ID" != "null" ]; then
    echo "   ✅ TASK_ID: $TASK_ID"
else
    echo "   ❌ TASK_ID не получен"
    exit 1
fi
echo ""

echo "3. Статус задачи (через 5 сек):"
sleep 5
curl -s "$BASE_URL/queue/status/$TASK_ID" | jq .
echo ""

echo "4. Результат задачи:"
curl -s "$BASE_URL/queue/result/$TASK_ID" | jq .
echo ""

echo "5. Повторное создание (блокировка):"
curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID" | jq .
echo ""

echo "✅ Тесты завершены!"
