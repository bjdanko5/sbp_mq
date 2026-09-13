#!/bin/bash
# test_create_payload_mq.sh — Полный тест MQ с автосозданием файлов

BASE_URL="http://localhost:8512"
BANK="ci"
BASE="zkh_ursv"
JOB_ID=999

echo "🧪 ТЕСТ create_payload_mq"
echo "=========================="
echo ""

# ============================================================
# ПОДГОТОВКА: создаём тестовые файлы
# ============================================================
echo "📁 Подготовка тестовых файлов..."

# 1. Создаём папку для данных банка
sudo mkdir -p /sbp/mq_dev/ci/zkh_ursv
sudo chown -R user:user /sbp/mq_dev/ci

# 2. Создаём файл 7845.json
cat > /sbp/mq_dev/ci/zkh_ursv/7845.json << 'EOF'
[
  {"requestId": "754316", "amount": 100},
  {"requestId": "754318", "amount": 200}
]
EOF

# 3. Удаляем старый Job-файл
rm -f /sbp/mq_dev/jobs/error/ci@zkh_ursv@999.json
rm -f /sbp/mq_dev/jobs/ci@zkh_ursv@999.json

# 4. Создаём Job-файл
cat > /sbp/mq_dev/jobs/ci@zkh_ursv@999.json << 'EOF'
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
EOF

# 5. Удаляем блокировку
redis-cli -n 1 DEL "lock:job:ci:zkh_ursv:999" > /dev/null 2>&1

# 6. Проверяем файлы
echo "   ✅ Файл 7845.json: $(ls -la /sbp/mq_dev/ci/zkh_ursv/7845.json | awk '{print $5}') байт"
echo "   ✅ Job-файл: $(ls -la /sbp/mq_dev/jobs/ci@zkh_ursv@999.json | awk '{print $5}') байт"
echo ""

# ============================================================
# ТЕСТЫ
# ============================================================

# 1. Статус Job
echo "1. Статус Job:"
curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID/status" | jq .
echo ""

# 2. Создание Job
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

# 3. Статус задачи (ждём 2 секунды для обработки Worker'ом)
echo "3. Статус задачи (через 5 сек):"
sleep 5
curl -s "$BASE_URL/queue/status/$TASK_ID" | jq .
echo ""

# 4. Результат задачи
echo "4. Результат задачи:"
curl -s "$BASE_URL/queue/result/$TASK_ID" | jq .
echo ""

# 5. Повторное создание (блокировка)
echo "5. Повторное создание (блокировка):"
curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID" | jq .
echo ""

echo "✅ Тесты завершены!"