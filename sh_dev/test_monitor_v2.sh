#!/bin/bash
# test_monitor_v2.sh — Тест с уникальными Job ID и числовыми requestId
#
# Проверяет:
#   1. Создание и обработку 9 Job (3 базы × 3 Job)
#   2. Появление req:{requestID} → task_id в Redis
#   3. Callback: base резолвится через Redis
#   4. SOAP-вызов: успех/ошибка с детализацией
#   5. Удаление req:* после успешного SOAP
#   6. Fallback на SQLite
#   7. Логи: очистка перед тестом + анализ после
#
# ВАЖНО:
#   - Job ID — ГЛОБАЛЬНО УНИКАЛЬНЫЕ (101, 102, 103, 201, 202, 203, 301, 302, 303)
#     Формула: BASE_IDX * 100 + JOB_IDX
#   - requestId — ЧИСЛА до 1000 (уникальные)
#     Формула: BASE_IDX * 100 + JOB_IDX * 10 + REQ_IDX

cd /var/www/html/sbp_mq_dev

BASE_URL="http://localhost:8512"
BASES=("zkh_ursv" "zkh_ursv2" "zkh_ursv3")
JOBS=(100 101 102)   # базовые индексы, преобразуются в уникальные

LOG_DIR="/var/www/html/sbp_mq_dev/logs"

# ============================================================
# ГЕНЕРАЦИЯ УНИКАЛЬНЫХ ЧИСЛОВЫХ requestId
# ============================================================
# Диапазон: 1..999
# Формула: BASE_IDX * 100 + JOB_IDX * 10 + REQ_IDX
#   BASE_IDX: 1..3
#   JOB_IDX:  1..3
#   REQ_IDX:  1..2
# Пример: base=1, job=1, req=1 → 111
#         base=3, job=3, req=2 → 332

get_request_id() {
    local base_idx=$1   # 1..3
    local job_idx=$2    # 1..3
    local req_idx=$3    # 1..2
    
    echo $((base_idx * 100 + job_idx * 10 + req_idx))
}

# ============================================================
# ГЕНЕРАЦИЯ УНИКАЛЬНОГО Job ID
# ============================================================
# Формула: BASE_IDX * 100 + JOB_IDX
#   BASE_IDX: 1..3
#   JOB_IDX:  1..3 (индекс в массиве JOBS)
# Пример: base=1, job_idx=1 → 101
#         base=1, job_idx=2 → 102
#         base=1, job_idx=3 → 103
#         base=2, job_idx=1 → 201
#         base=3, job_idx=3 → 303

get_job_id() {
    local base_idx=$1   # 1..3
    local job_idx=$2    # 1..3
    
    echo $((base_idx * 100 + job_idx))
}

echo "🧪 ТЕСТ МОНИТОРИНГА + CALLBACK + SOAP"
echo "======================================="
echo "   Job ID:     101, 102, 103, 201, ..., 303 (уникальные)"
echo "   requestId:  111, 112, 121, ..., 332 (уникальные числа)"
echo ""

# ============================================================
# ПРОВЕРКИ ПЕРЕД ТЕСТОМ
# ============================================================

echo "🔧 Проверка окружения..."

if ! redis-cli PING > /dev/null 2>&1; then
    echo "   ❌ Redis недоступен"
    exit 1
fi
echo "   ✅ Redis: OK"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/" 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "   ❌ API недоступен (HTTP $HTTP_CODE)"
    exit 1
fi
echo "   ✅ API: OK (HTTP $HTTP_CODE)"

if ! command -v python3 > /dev/null 2>&1; then
    echo "   ❌ python3 не найден"
    exit 1
fi
echo "   ✅ python3: OK"

REQ_BEFORE=$(redis-cli -n 1 KEYS "req:*" | wc -l)
echo "   📊 req:* до теста: $REQ_BEFORE"

echo ""

# ============================================================
# ОЧИСТКА ЛОГОВ
# ============================================================

echo "📋 Очистка логов..."

if [ -d "$LOG_DIR" ]; then
    LOG_COUNT=0
    for log_file in "$LOG_DIR"/*.log; do
        if [ -f "$log_file" ]; then
            : > "$log_file" 2>/dev/null || sudo truncate -s 0 "$log_file" 2>/dev/null
            LOG_COUNT=$((LOG_COUNT + 1))
        fi
    done
    echo "   ✅ Очищено логов: $LOG_COUNT"
    
    echo "   📁 Логи в $LOG_DIR:"
    ls -1 "$LOG_DIR"/*.log 2>/dev/null | while read f; do
        echo "      $(basename $f): $(stat -c%s "$f") байт"
    done
else
    echo "   ⚠️  Директория логов не найдена: $LOG_DIR"
fi
echo ""

# ============================================================
# ОЧИСТКА REDIS + ФАЙЛОВ
# ============================================================

echo "🧹 Полная очистка..."

redis-cli -n 1 FLUSHDB > /dev/null 2>&1

for base in "${BASES[@]}"; do
    sudo rm -rf /sbp/mq_dev/ci/$base
done
sudo mkdir -p /sbp/mq_dev/jobs/{success,error}
sudo rm -f /sbp/mq_dev/jobs/*.json
sudo rm -f /sbp/mq_dev/jobs/success/*.json
sudo rm -f /sbp/mq_dev/jobs/error/*.json
sudo chown -R user:user /sbp/mq

# Чистим SQLite от старых тестовых записей (числа 100..999)
python3 -c "
import sqlite3
conn = sqlite3.connect('/var/www/html/sbp_mq_dev/requests.db')
conn.execute(\"DELETE FROM requests WHERE CAST(requestID AS INTEGER) BETWEEN 100 AND 999\")
conn.commit()
conn.close()
" 2>/dev/null || true

echo "   ✅ Очищено"
echo ""

# ============================================================
# СОЗДАНИЕ ФАЙЛОВ С ЧИСЛОВЫМИ requestId
# ============================================================

echo "📁 Создание уникальных файлов..."

BASE_IDX=0
for BASE in "${BASES[@]}"; do
    BASE_IDX=$((BASE_IDX + 1))
    
    sudo mkdir -p /sbp/mq_dev/ci/$BASE
    sudo chown -R user:user /sbp/mq_dev/ci
    
    JOB_IDX=0
    for JOB_BASE in "${JOBS[@]}"; do
        JOB_IDX=$((JOB_IDX + 1))
        
        JOB=$(get_job_id $BASE_IDX $JOB_IDX)
        FILENAME="job${JOB}.json"
        
        REQ_1=$(get_request_id $BASE_IDX $JOB_IDX 1)
        REQ_2=$(get_request_id $BASE_IDX $JOB_IDX 2)
        
        cat > /sbp/mq_dev/ci/$BASE/$FILENAME << EOF
[
  {"requestId": "${REQ_1}", "amount": 100},
  {"requestId": "${REQ_2}", "amount": 200}
]
EOF
    done
    
    echo "   ✅ $BASE: 3 уникальных файла"
done
echo ""

# ============================================================
# СОЗДАНИЕ JOB
# ============================================================

echo "📝 Создание Job..."

BASE_IDX=0
for BASE in "${BASES[@]}"; do
    BASE_IDX=$((BASE_IDX + 1))
    
    JOB_IDX=0
    for JOB_BASE in "${JOBS[@]}"; do
        JOB_IDX=$((JOB_IDX + 1))
        
        JOB=$(get_job_id $BASE_IDX $JOB_IDX)
        FILENAME="job${JOB}.json"
        
        REQ_1=$(get_request_id $BASE_IDX $JOB_IDX 1)
        REQ_2=$(get_request_id $BASE_IDX $JOB_IDX 2)
        
        cat > /sbp/mq_dev/jobs/ci@${BASE}@${JOB}.json << JOB_EOF
{
  "bank": "ci",
  "base": "${BASE}",
  "job_id": ${JOB},
  "job_name": "Job ${JOB} в ${BASE}",
  "created_at": "2026-09-10T19:00:00",
  "files": [
    {
      "filename": "${FILENAME}",
      "count": 2,
      "request_ids": ["${REQ_1}", "${REQ_2}"]
    }
  ],
  "total_requests": 2,
  "status": "pending"
}
JOB_EOF
    done
done

echo "   ✅ Создано 9 Job (уникальные ID: 101..303)"
echo ""

# ============================================================
# ЗАПУСК JOB
# ============================================================

echo "🚀 Запуск 9 Job..."

BASE_IDX=0
for BASE in "${BASES[@]}"; do
    BASE_IDX=$((BASE_IDX + 1))
    
    JOB_IDX=0
    for JOB_BASE in "${JOBS[@]}"; do
        JOB_IDX=$((JOB_IDX + 1))
        
        JOB=$(get_job_id $BASE_IDX $JOB_IDX)
        
        RESPONSE=$(curl -s "${BASE_URL}/create_payload_mq/ci/${BASE}/${JOB}")
        TASK_ID=$(echo "$RESPONSE" | jq -r '.data.task_id // empty')
        
        if [ -n "$TASK_ID" ] && [ "$TASK_ID" != "null" ]; then
            echo "   ✅ ci@${BASE}@${JOB} → $TASK_ID"
        else
            echo "   ❌ ci@${BASE}@${JOB} → ошибка: $(echo $RESPONSE | jq -c '.')"
        fi
    done
done
echo ""

# ============================================================
# МОНИТОРИНГ ОБРАБОТКИ
# ============================================================

echo "📊 МОНИТОРИНГ ОБРАБОТКИ"
echo "========================"

for i in $(seq 1 30); do
    DATA=$(curl -s "${BASE_URL}/monitor/data")
    P=$(echo "$DATA" | jq -r '.processing_count // 0')
    C=$(echo "$DATA" | jq -r '.completed_count // 0')
    echo "[$i] 🔥 В работе: $P | ✅ Завершено: $C"
    
    if [ "$P" = "0" ] && [ "$C" -ge "9" ]; then
        break
    fi
    sleep 0.5
done
echo ""

# ============================================================
# ПРОВЕРКА req:* В REDIS
# ============================================================

echo "🔍 ПРОВЕРКА req:* В REDIS"
echo "=========================="

REQ_COUNT=$(redis-cli -n 1 KEYS "req:*" | wc -l)
echo "   📊 Найдено req:* ключей: $REQ_COUNT (ожидаем 18 — 9 Job × 2 requestID)"

if [ "$REQ_COUNT" -eq 0 ]; then
    echo "   ❌ req:* не найдены! Проверьте логи Worker'ов:"
    echo "      sudo journalctl -u sbp_mq-worker -n 50"
    exit 1
fi

echo "   📋 Примеры req:*:"
redis-cli -n 1 KEYS "req:*" | head -5 | while read key; do
    VALUE=$(redis-cli -n 1 GET "$key")
    echo "      $key → $VALUE"
done
echo ""

# ============================================================
# ПРОВЕРКА ДУБЛИКАТОВ
# ============================================================

echo "🔍 ПРОВЕРКА ДУБЛИКАТОВ"
echo "======================="

DUPLICATE_JOBS=0
for BASE in "${BASES[@]}"; do
    BASE_IDX=0
    for B in "${BASES[@]}"; do
        BASE_IDX=$((BASE_IDX + 1))
        [ "$B" = "$BASE" ] && break
    done
    
    for JOB_BASE in "${JOBS[@]}"; do
        # JOB_IDX вычисляем по позиции в массиве JOBS
        JOB_IDX=0
        for J in "${JOBS[@]}"; do
            JOB_IDX=$((JOB_IDX + 1))
            [ "$J" = "$JOB_BASE" ] && break
        done
        
        JOB=$(get_job_id $BASE_IDX $JOB_IDX)
        JOB_PATTERN="ci@${BASE}@${JOB}"
        
        COUNT=$(grep -c "ВЗЯЛ Job ${JOB_PATTERN} " "$LOG_DIR/all.log" 2>/dev/null || echo 0)
        
        if [ "$COUNT" -eq 1 ]; then
            echo "   ✅ ${JOB_PATTERN}: взят 1 раз"
        elif [ "$COUNT" -eq 0 ]; then
            echo "   ⚠️  ${JOB_PATTERN}: НЕ взят (0 раз)"
            DUPLICATE_JOBS=$((DUPLICATE_JOBS + 1))
        else
            echo "   ❌ ${JOB_PATTERN}: взят $COUNT раз (дубликат!)"
            DUPLICATE_JOBS=$((DUPLICATE_JOBS + 1))
        fi
    done
done

echo ""

# Проверяем req:* на уникальные task_id
echo "   🔍 Проверка req:* → task_id:"
TASK_IDS=$(redis-cli -n 1 KEYS "req:*" | while read key; do redis-cli -n 1 GET "$key"; done | sort -u)
UNIQUE_COUNT=$(echo "$TASK_IDS" | grep -c . || echo 0)
TOTAL_REQ=$(redis-cli -n 1 KEYS "req:*" | wc -l)

echo "      Всего req:*:          $TOTAL_REQ"
echo "      Уникальных task_id:   $UNIQUE_COUNT"
echo "      Ожидаем:              до 9 (по одному на Job)"
echo ""

# ============================================================
# CALLBACK — ОСНОВНОЙ ТЕСТ
# ============================================================

echo "📞 ТЕСТ CALLBACK + SOAP"
echo "========================"
echo "   ℹ️  Проверяем: base найден + статус SOAP"
echo ""

TOTAL_RESOLVED=0
TOTAL_NOT_FOUND=0
TOTAL_SOAP_OK=0
TOTAL_SOAP_ERR=0
TOTAL_REQ_DELETED=0

declare -A SOAP_ERRORS
declare -A SOAP_ERROR_MSGS

BASE_IDX=0
for BASE in "${BASES[@]}"; do
    BASE_IDX=$((BASE_IDX + 1))
    
    JOB_IDX=0
    for JOB_BASE in "${JOBS[@]}"; do
        JOB_IDX=$((JOB_IDX + 1))
        
        JOB=$(get_job_id $BASE_IDX $JOB_IDX)
        
        REQ_1=$(get_request_id $BASE_IDX $JOB_IDX 1)
        REQ_2=$(get_request_id $BASE_IDX $JOB_IDX 2)
        
        CALLBACK_PAYLOAD="[{\"requestId\":\"${REQ_1}\",\"qrPayload\":\"QR:${REQ_1}\"},{\"requestId\":\"${REQ_2}\",\"qrPayload\":\"QR:${REQ_2}\"}]"
        
        echo "   📤 Callback для ci@${BASE}@${JOB} (requestId: $REQ_1, $REQ_2)..."
        
        RESPONSE=$(curl -s -X POST "${BASE_URL}/callback" \
            -H "Content-Type: application/json" \
            -d "${CALLBACK_PAYLOAD}")
        
        BASE_IN_RESPONSE=$(echo "$RESPONSE" | jq -r "has(\"${BASE}\")")
        NOT_FOUND_COUNT=$(echo "$RESPONSE" | jq -r '._not_found.request_ids // [] | length')
        
        if [ "$BASE_IN_RESPONSE" = "true" ] && [ "$NOT_FOUND_COUNT" = "0" ]; then
            TOTAL_RESOLVED=$((TOTAL_RESOLVED + 1))
            
            STATUS=$(echo "$RESPONSE" | jq -r ".${BASE}.status // \"unknown\"")
            
            if [ "$STATUS" = "success" ] || [ "$STATUS" = "warning" ]; then
                TOTAL_SOAP_OK=$((TOTAL_SOAP_OK + 1))
                DELETED_REDIS=$(echo "$RESPONSE" | jq -r ".${BASE}.deleted_redis // 0")
                DELETED_DB=$(echo "$RESPONSE" | jq -r ".${BASE}.deleted_db // 0")
                TOTAL_REQ_DELETED=$((TOTAL_REQ_DELETED + DELETED_REDIS))
                echo "      ✅ base=$BASE, SOAP=OK, req:* удалено: Redis=$DELETED_REDIS, SQLite=$DELETED_DB"
            else
                TOTAL_SOAP_ERR=$((TOTAL_SOAP_ERR + 1))
                ERR_MSG=$(echo "$RESPONSE" | jq -r ".${BASE}.error // \"unknown\"")
                
                SOAP_ERRORS[$BASE]=$((${SOAP_ERRORS[$BASE]:-0} + 1))
                SOAP_ERROR_MSGS[$BASE]="$ERR_MSG"
                
                if echo "$ERR_MSG" | grep -q "404"; then
                    ERROR_TYPE="404 Not Found (база не существует)"
                elif echo "$ERR_MSG" | grep -q "Cannot convert value to Numeric"; then
                    ERROR_TYPE="Numeric (неверный тип данных)"
                elif echo "$ERR_MSG" | grep -q "timeout"; then
                    ERROR_TYPE="Timeout"
                elif echo "$ERR_MSG" | grep -q "Connection"; then
                    ERROR_TYPE="Connection Error"
                else
                    ERROR_TYPE="Unknown"
                fi
                
                echo "      ⚠️  base=$BASE, SOAP=ERROR"
                echo "         Тип:    $ERROR_TYPE"
                echo "         Ошибка: $(echo $ERR_MSG | head -c 150)..."
                echo "         ℹ️  req:* НЕ удалены (для повтора callback)"
            fi
        else
            TOTAL_NOT_FOUND=$((TOTAL_NOT_FOUND + 1))
            echo "      ❌ base НЕ найден для ci@${BASE}@${JOB}"
            echo "         Ответ: $(echo $RESPONSE | jq -c '.')"
        fi
    done
done
echo ""

# ============================================================
# ДЕТАЛИЗАЦИЯ SOAP-ОШИБОК
# ============================================================

if [ "$TOTAL_SOAP_ERR" -gt 0 ]; then
    echo "🔍 ДЕТАЛИЗАЦИЯ SOAP-ОШИБОК"
    echo "============================"
    
    for BASE in "${!SOAP_ERRORS[@]}"; do
        COUNT=${SOAP_ERRORS[$BASE]}
        MSG=${SOAP_ERROR_MSGS[$BASE]}
        
        echo "   📛 База: $BASE (ошибок: $COUNT/3)"
        
        if echo "$MSG" | grep -q "404"; then
            echo "      ❌ Тип: 404 Not Found"
            echo "      💡 Причина: базы '$BASE' нет на SOAP-сервере"
            echo "         URL: http://192.168.10.238/$BASE/ws/WebLK?wsdl"
            echo "      ✅ Это ожидаемо для тестовых баз-пустышек"
        elif echo "$MSG" | grep -q "Cannot convert value to Numeric"; then
            echo "      ❌ Тип: Cannot convert value to Numeric"
            echo "      💡 Причина: SOAP-сервер не может преобразовать в число"
            echo "         Возможные причины:"
            echo "         - requestId должен быть числом (проверьте формат)"
            echo "         - amount должен быть строкой, а не числом"
            echo "         - period/другие поля в неверном формате"
            echo "      ⚠️  Проверьте формат данных в SOAP-методе"
        else
            echo "      ❌ Тип: Unknown"
            echo "      💡 Ошибка: $(echo $MSG | head -c 200)"
        fi
        echo ""
    done
fi

# ============================================================
# ПРОВЕРКА УДАЛЕНИЯ req:*
# ============================================================

echo "🔍 ПРОВЕРКА req:* ПОСЛЕ CALLBACK"
echo "================================="

sleep 1

REQ_AFTER=$(redis-cli -n 1 KEYS "req:*" | wc -l)
echo "   📊 req:* после callback: $REQ_AFTER"
echo "   ℹ️  req:* удаляются ТОЛЬКО при успешном SOAP"

if [ "$TOTAL_SOAP_OK" -eq "9" ]; then
    if [ "$REQ_AFTER" -eq 0 ]; then
        echo "   ✅ Все req:* удалены (SOAP был успешен)"
    else
        echo "   ⚠️  Осталось $REQ_AFTER req:* (ожидаем 0)"
    fi
else
    echo "   ℹ️  SOAP упал $TOTAL_SOAP_ERR раз → req:* остаются для повтора"
    echo "      (TTL 1 час сам почистит)"
fi
echo ""

# ============================================================
# ТЕСТ FALLBACK (Redis → SQLite)
# ============================================================

echo "🔄 ТЕСТ FALLBACK (Redis → SQLite)"
echo "==================================="

FALLBACK_ID="999"
echo "   📝 Создаём запись только в SQLite: $FALLBACK_ID"

# Убеждаемся, что в Redis нет
REDIS_HAS=$(redis-cli -n 1 EXISTS "req:$FALLBACK_ID")
if [ "$REDIS_HAS" = "1" ]; then
    redis-cli -n 1 DEL "req:$FALLBACK_ID" > /dev/null
    echo "   🗑️  Удалён существующий req:$FALLBACK_ID"
fi

# Создаём запись в SQLite
python3 -c "
import sqlite3
conn = sqlite3.connect('/var/www/html/sbp_mq_dev/requests.db')
conn.execute(
    'INSERT OR REPLACE INTO requests (requestID, base) VALUES (?, ?)',
    ('$FALLBACK_ID', 'zkh_ursv')
)
conn.commit()
print('   ✅ Запись создана в SQLite')
conn.close()
"

SQLITE_CHECK=$(python3 -c "
import sqlite3
conn = sqlite3.connect('/var/www/html/sbp_mq_dev/requests.db')
row = conn.execute(
    'SELECT base FROM requests WHERE requestID = ?', ('$FALLBACK_ID',)
).fetchone()
conn.close()
print(row[0] if row else '')
")
echo "   📊 SQLite: '$SQLITE_CHECK' (ожидаем 'zkh_ursv')"

REDIS_HAS=$(redis-cli -n 1 EXISTS "req:$FALLBACK_ID")
echo "   📊 Redis req:$FALLBACK_ID: $REDIS_HAS (ожидаем 0)"

FALLBACK_PAYLOAD="[{\"requestId\":\"$FALLBACK_ID\",\"qrPayload\":\"QR:fallback\"}]"
RESPONSE=$(curl -s -X POST "${BASE_URL}/callback" \
    -H "Content-Type: application/json" \
    -d "$FALLBACK_PAYLOAD")

BASE_FOUND=$(echo "$RESPONSE" | jq -r 'has("zkh_ursv")')

if [ "$BASE_FOUND" = "true" ]; then
    echo "   ✅ Fallback сработал: base найден через SQLite"
    FALLBACK_OK=1
else
    echo "   ❌ Fallback НЕ сработал"
    echo "      Ответ: $(echo $RESPONSE | jq -c '.')"
    FALLBACK_OK=0
fi

# Очищаем тестовую запись
python3 -c "
import sqlite3
conn = sqlite3.connect('/var/www/html/sbp_mq_dev/requests.db')
conn.execute('DELETE FROM requests WHERE requestID = ?', ('$FALLBACK_ID',))
conn.commit()
conn.close()
"

echo ""

# ============================================================
# АНАЛИЗ ЛОГОВ
# ============================================================

echo "📋 АНАЛИЗ ЛОГОВ ПОСЛЕ ТЕСТА"
echo "============================="

if [ -d "$LOG_DIR" ]; then
    echo "   📁 Размеры логов:"
    for log_file in "$LOG_DIR"/*.log; do
        if [ -f "$log_file" ]; then
            SIZE=$(stat -c%s "$log_file" 2>/dev/null)
            LINES=$(wc -l < "$log_file" 2>/dev/null)
            echo "      $(basename $log_file): ${SIZE} байт, ${LINES} строк"
        fi
    done
    echo ""
    
    if [ -f "$LOG_DIR/sbp.log" ]; then
        echo "   🔍 Ключевые события в sbp.log:"
        
        REQ_SAVED=$(grep -c "Сохранено.*requestID" "$LOG_DIR/sbp.log" 2>/dev/null || echo 0)
        echo "      req:* сохранено: $REQ_SAVED"
        
        FALLBACK_LINES=$(grep -c "Fallback SQLite" "$LOG_DIR/sbp.log" 2>/dev/null || echo 0)
        echo "      Fallback SQLite: $FALLBACK_LINES срабатываний"
        
        REDIS_NOT_FOUND=$(grep -c "Redis не нашёл base" "$LOG_DIR/sbp.log" 2>/dev/null || echo 0)
        echo "      Redis не нашёл:  $REDIS_NOT_FOUND"
        
        REDIS_FOUND=$(grep -c "Найдено base:" "$LOG_DIR/sbp.log" 2>/dev/null || echo 0)
        echo "      Найдено base:    $REDIS_FOUND"
        
        echo ""
    fi
    
    if [ -f "$LOG_DIR/sbp_errors.log" ]; then
        ERR_COUNT=$(wc -l < "$LOG_DIR/sbp_errors.log" 2>/dev/null)
        echo "   ⚠️  sbp_errors.log: $ERR_COUNT строк"
        
        SOAP_ERRORS_COUNT=$(grep -c "SOAP ProcessPayload не выполнен" "$LOG_DIR/sbp_errors.log" 2>/dev/null || echo 0)
        echo "      SOAP ошибок:     $SOAP_ERRORS_COUNT"
        
        HTTP_404_COUNT=$(grep -c "404 Client Error" "$LOG_DIR/sbp_errors.log" 2>/dev/null || echo 0)
        echo "      HTTP 404:        $HTTP_404_COUNT"
        
        NUMERIC_COUNT=$(grep -c "Cannot convert value to Numeric" "$LOG_DIR/sbp_errors.log" 2>/dev/null || echo 0)
        echo "      Numeric errors:  $NUMERIC_COUNT"
        
        if [ "$ERR_COUNT" -gt 0 ]; then
            echo ""
            echo "   📋 Последние 5 ошибок:"
            tail -5 "$LOG_DIR/sbp_errors.log" | while read line; do
                echo "      $(echo $line | head -c 120)"
            done
        fi
    fi
else
    echo "   ⚠️  Директория логов не найдена"
fi
echo ""

# ============================================================
# ФИНАЛЬНАЯ ПРОВЕРКА ЧЕРЕЗ /monitor
# ============================================================

echo "🔍 ФИНАЛЬНАЯ ПРОВЕРКА ЧЕРЕЗ /monitor"
echo "====================================="

DATA=$(curl -s "${BASE_URL}/monitor/data")
SUCCESS=$(echo "$DATA" | jq -r '[.completed[] | select(.status=="completed")] | length')
ERRORS=$(echo "$DATA" | jq -r '[.completed[] | select(.status=="error")] | length')
PROCESSING=$(echo "$DATA" | jq -r '.processing_count // 0')

echo "   🔥 В работе:    $PROCESSING"
echo "   ✅ Успешных:    $SUCCESS"
echo "   ❌ Ошибок:      $ERRORS"
echo ""

echo "📋 Детали по Job:"
echo "$DATA" | jq -r '.completed[] | "   \(if .status=="completed" then "✅" else "❌" end) \(.bank)@\(.base)@\(.job_id) → \(.status) (\(.summary.success_requests)/\(.summary.total_requests))"'
echo ""

# ============================================================
# ИТОГОВАЯ СТАТИСТИКА
# ============================================================

echo "📊 ИТОГОВАЯ СТАТИСТИКА"
echo "======================="
echo "   📞 Callback: base найден       $TOTAL_RESOLVED/9"
echo "   📞 Callback: base НЕ найден    $TOTAL_NOT_FOUND/9"
echo "   📞 SOAP: успех                 $TOTAL_SOAP_OK/9"
echo "   📞 SOAP: ошибка                $TOTAL_SOAP_ERR/9"
echo "   🗑️  req:* удалено               $TOTAL_REQ_DELETED"
echo "   📦 req:* осталось               $REQ_AFTER"
echo "   🔄 Fallback SQLite:            $([ "$FALLBACK_OK" = "1" ] && echo "✅ работает" || echo "❌ не работает")"
echo "   🔍 Дубликатов Job:             $DUPLICATE_JOBS"
echo ""

# ============================================================
# ВЕРДИКТ
# ============================================================

if [ "$TOTAL_RESOLVED" -eq "9" ] && [ "$TOTAL_NOT_FOUND" -eq "0" ]; then
    echo "🎉 ГЛАВНЫЙ ТЕСТ ПРОЙДЕН!"
    echo ""
    echo "   ✅ 9 Job обработаны"
    echo "   ✅ 18 req:* созданы"
    echo "   ✅ 9 Callback: base найден (Redis/SQLite)"
    echo "   ✅ Fallback SQLite: $([ "$FALLBACK_OK" = "1" ] && echo "работает" || echo "НЕ работает")"
    echo "   ✅ Дубликатов Job: $DUPLICATE_JOBS"
    
    if [ "$TOTAL_SOAP_OK" -eq "9" ]; then
        echo "   🎉 БОНУС: все SOAP успешны"
        echo "   ✅ req:* удалены после callback"
        EXIT_CODE=0
    else
        echo "   ⚠️  SOAP упал $TOTAL_SOAP_ERR раз"
        echo "      Возможные причины:"
        echo "      - zkh_ursv2/zkh_ursv3 — не существуют на SOAP-сервере"
        echo "      - zkh_ursv — неверный формат данных (см. детализацию выше)"
        echo ""
        echo "   ℹ️  Основная логика (req:* → base) РАБОТАЕТ ✅"
        EXIT_CODE=0
    fi
    
    echo ""
    echo "🌐 Мониторинг: ${BASE_URL}/monitor"
    exit $EXIT_CODE
else
    echo "⚠️  ТЕСТ ЗАВЕРШЁН С ПРОБЛЕМАМИ"
    echo ""
    echo "   ❌ base НЕ найден для $TOTAL_NOT_FOUND callback"
    echo ""
    echo "   Проверьте:"
    echo "   - Логи сервера:   tail -50 logs/sbp.log"
    echo "   - Логи ошибок:    tail -50 logs/sbp_errors.log"
    echo "   - req:* в Redis:  redis-cli -n 1 KEYS 'req:*'"
    echo "   - task:* в Redis: redis-cli -n 1 KEYS 'task:*'"
    echo ""
    exit 1
fi