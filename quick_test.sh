#!/bin/bash
# quick_test.sh — Быстрый тест MQ с 5 файлами

cd /var/www/html/sbp_mq

echo "🧪 БЫСТРЫЙ ТЕСТ MQ (5 файлов)"
echo "================================"
echo ""

# 1. Создаём папку и файлы
echo "📁 Создание 5 файлов..."
sudo mkdir -p /sbp/mq/ci/zkh_ursv
sudo chown -R user:user /sbp/mq/ci

for i in 7845 7846 7847 7848 7849; do
    echo "[{\"requestId\":\"${i}001\",\"amount\":100},{\"requestId\":\"${i}002\",\"amount\":200}]" > /sbp/mq/ci/zkh_ursv/${i}.json
done

echo "   ✅ Создано файлов: $(ls /sbp/mq/ci/zkh_ursv/*.json | wc -l)"

# 2. Очищаем старые Job
echo ""
echo "🗑️  Очистка старых Job..."
rm -f /sbp/mq/jobs/error/ci@zkh_ursv@999.json
rm -f /sbp/mq/jobs/ci@zkh_ursv@999.json
rm -f /sbp/mq/jobs/success/ci@zkh_ursv@999.json
redis-cli DEL "lock:job:ci:zkh_ursv:999" > /dev/null 2>&1
echo "   ✅ Очищено"

# 3. Создаём Job с 5 файлами
echo ""
echo "📝 Создание Job с 5 файлами..."

cat > /sbp/mq/jobs/ci@zkh_ursv@999.json << 'JOB_EOF'
{
  "bank": "ci",
  "base": "zkh_ursv",
  "job_id": 999,
  "job_name": "Тест 5 файлов",
  "created_at": "2026-09-10T12:00:00",
  "files": [
    {"filename": "7845.json", "count": 2, "request_ids": ["7845001", "7845002"]},
    {"filename": "7846.json", "count": 2, "request_ids": ["7846001", "7846002"]},
    {"filename": "7847.json", "count": 2, "request_ids": ["7847001", "7847002"]},
    {"filename": "7848.json", "count": 2, "request_ids": ["7848001", "7848002"]},
    {"filename": "7849.json", "count": 2, "request_ids": ["7849001", "7849002"]}
  ],
  "total_requests": 10,
  "status": "pending"
}
JOB_EOF

echo "   ✅ Job создан: $(cat /sbp/mq/jobs/ci@zkh_ursv@999.json | jq -r '.files | length') файлов"

# 4. Создаём задачу через API
echo ""
echo "🚀 Отправка задачи..."
RESPONSE=$(curl -s "http://localhost:8511/create_payload_mq/ci/zkh_ursv/999")
TASK_ID=$(echo "$RESPONSE" | jq -r '.data.task_id')

if [ -z "$TASK_ID" ] || [ "$TASK_ID" == "null" ]; then
    echo "   ❌ Ошибка создания задачи:"
    echo "$RESPONSE" | jq .
    exit 1
fi

echo "   ✅ TASK_ID: $TASK_ID"

# 5. Мониторинг прогресса
echo ""
echo "📊 МОНИТОРИНГ ПРОГРЕССА"
echo "========================"

for i in $(seq 1 30); do
    PROGRESS=$(redis-cli GET "progress:$TASK_ID" 2>/dev/null)
    RESULT=$(redis-cli GET "task:$TASK_ID" 2>/dev/null)
    
    if [ -n "$RESULT" ] && [ "$RESULT" != "(nil)" ]; then
        STATUS=$(echo "$RESULT" | jq -r '.status')
        echo "[$i] ✅ РЕЗУЛЬТАТ: $STATUS"
        break
    elif [ -n "$PROGRESS" ] && [ "$PROGRESS" != "(nil)" ]; then
        PROCESSED=$(echo "$PROGRESS" | jq -r '.processed_files')
        TOTAL=$(echo "$PROGRESS" | jq -r '.total_files')
        PERCENT=$(echo "$PROGRESS" | jq -r '.progress_percent')
        CURRENT=$(echo "$PROGRESS" | jq -r '.current_file')
        echo "[$i] 📊 ПРОГРЕСС: $PROCESSED/$TOTAL ($PERCENT%) файл: $CURRENT"
    else
        echo "[$i] ⏳ ожидание..."
    fi
    sleep 0.3
done

# 6. Финальная проверка
echo ""
echo "🔍 ФИНАЛЬНАЯ ПРОВЕРКА"
echo "========================"
echo "PROGRESS существует: $(redis-cli EXISTS "progress:$TASK_ID") (0=удалён ✅)"
echo "RESULT существует:   $(redis-cli EXISTS "task:$TASK_ID") (1=есть ✅)"

echo ""
echo "📋 РЕЗУЛЬТАТ:"
curl -s "http://localhost:8511/queue/result/$TASK_ID" | jq '.data.result | {status, summary}'

echo ""
echo "✅ Тест завершён!"
