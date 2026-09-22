#!/bin/bash
# test_smoke.sh — компактный smoke-тест SBP MQ
#
# Проверяет:
#   [1]  Базовый happy path (ci/zkh_ursv, 1 Job, SOAP OK)
#   [2]  Ошибка Job (amount<0 → SOAP Error)
#   [3]  Callback без Job (несущ. requestID → not_found)
#   [4]  Fallback SQLite (Redis пуст → SQLite есть)
#   [5]  Конкурентность (5 Job параллельно → нет дублей)
#   [6]  stop_payload — успех
#   [7]  stop_payload — FILE_NOT_FOUND
#   [8]  stop_payload — CONFIG_ERROR
#   [9]  /health/detailed — 7 компонентов
#   [10] /monitor/data — JSON
#
# Использование:
#   cd /var/www/html/sbp_mq_dev
#   ./sh_dev/test_smoke.sh

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck disable=SC1091
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

BASE_URL="http://localhost:${SBP_MQ_PORT}"
BANK="ci"
BASE="zkh_ursv"
SBP_ROOT="$SBP_ROOT4MQ"
JOB_DIR="$SBP_ROOT/$BANK/$BASE"
JOBS_DIR="$SBP_ROOT/jobs"
REDIS_DB="${REDIS_DB:-1}"

# ============================================================
#                   ХЕЛПЕРЫ
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
GRAY='\033[0;90m'
NC='\033[0m'

PASS=0
FAIL=0
TOTAL=0
START_TIME=$(date +%s)

# Массив для деталей упавших
declare -a FAILED_DETAILS=()

test_step() {
    local num="$1"
    local name="$2"
    TOTAL=$((TOTAL + 1))
    printf "  [%2d/10] %-40s " "$num" "$name"
}

test_pass() {
    PASS=$((PASS + 1))
    echo -e "${GREEN}✅${NC}"
}

test_fail() {
    local reason="$1"
    FAIL=$((FAIL + 1))
    echo -e "${RED}❌${NC}"
    FAILED_DETAILS+=("  [${TOTAL}] ${reason}")
}

# ============================================================
#                   ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  🧪 SMOKE TEST SBP MQ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${GRAY}   API:    ${BASE_URL}${NC}"
echo -e "${GRAY}   Bank:   ${BANK}${NC}"
echo -e "${GRAY}   Base:   ${BASE}${NC}"
echo -e "${GRAY}   Redis:  DB ${REDIS_DB}${NC}"
echo ""

# Проверка API
if ! timeout 5 curl -sf "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}❌ API не отвечает на ${BASE_URL}/health${NC}"
    exit 1
fi

# Очистка логов
> "$PROJECT_DIR/logs/sbp-dev.log" 2>/dev/null || true
> "$PROJECT_DIR/logs/sbp-dev_errors.log" 2>/dev/null || true
> "$PROJECT_DIR/logs/all.log" 2>/dev/null || true

# Создание директорий
mkdir -p "$JOB_DIR" "$JOBS_DIR" 2>/dev/null
mkdir -p "$JOB_DIR/stop" "$JOB_DIR/stoped" 2>/dev/null

echo -e "${GRAY}   Подготовка завершена${NC}"
echo ""

# ============================================================
#                   [1] БАЗОВЫЙ HAPPY PATH
# ============================================================

test_step 1 "Базовый happy path (SOAP OK)"

JOB_ID_1=77001
REQ_ID_1="77001001"
JOB_TASK_1=""

# Очистка
rm -f "$JOB_DIR/${JOB_ID_1}.json" 2>/dev/null
rm -f "$JOBS_DIR/${BANK}@${BASE}@${JOB_ID_1}.json" 2>/dev/null
rm -f "$JOBS_DIR/error/${BANK}@${BASE}@${JOB_ID_1}.json" 2>/dev/null
rm -f "$JOBS_DIR/success/${BANK}@${BASE}@${JOB_ID_1}.json" 2>/dev/null
rm -f "$JOB_DIR/processing/${JOB_ID_1}.json" 2>/dev/null
rm -f "$JOB_DIR/sended/${JOB_ID_1}.json" 2>/dev/null
# Redis — очистка следов Job (lock, task, req)
redis-cli -n "$REDIS_DB" --scan --pattern "*${JOB_ID_1}*" 2>/dev/null | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true
redis-cli -n "$REDIS_DB" --scan --pattern "lock:*${JOB_ID_1}*" 2>/dev/null | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true

# Файл с запросом (валидный)
cat > "$JOB_DIR/${JOB_ID_1}.json" << EOF
[{"requestId":"${REQ_ID_1}","amount":100}]
EOF

# Job
cat > "$JOBS_DIR/${BANK}@${BASE}@${JOB_ID_1}.json" << EOF
{
  "bank": "${BANK}", "base": "${BASE}", "job_id": ${JOB_ID_1},
  "job_name": "Smoke Test 1", "created_at": "2026-09-22T10:00:00",
  "files": [{"filename": "${JOB_ID_1}.json", "count": 1, "request_ids": ["${REQ_ID_1}"]}],
  "total_requests": 1, "status": "pending"
}
EOF

# Публикация
PUBLISH_1=$(timeout 10 curl -s "${BASE_URL}/create_payload_mq/${BANK}/${BASE}/${JOB_ID_1}")
JOB_TASK_1=$(echo "$PUBLISH_1" | jq -r '.data.task_id // empty' 2>/dev/null)

if [ -z "$JOB_TASK_1" ] || [ "$JOB_TASK_1" = "null" ]; then
    PUBLISH_ERR=$(echo "$PUBLISH_1" | jq -r '.error // .detail // "unknown"' 2>/dev/null)
    test_fail "[1] Не удалось опубликовать Job ${JOB_ID_1}: ${PUBLISH_ERR}"
else
    sleep 4
    # Проверка: Job в success/ (не error/)
    if [ -f "$JOBS_DIR/success/${BANK}@${BASE}@${JOB_ID_1}.json" ]; then
        test_pass
    elif [ -f "$JOBS_DIR/error/${BANK}@${BASE}@${JOB_ID_1}.json" ]; then
        test_fail "[1] Job ${JOB_ID_1} попал в error/ (ожидался success/)"
    else
        test_fail "[1] Job ${JOB_ID_1} не завершён за 4 сек"
    fi
fi

# ============================================================
#                   [2] ОШИБКА JOB → SOAP ERROR
# ============================================================

test_step 2 "Ошибка Job (amount<0 → SOAP)"

JOB_ID_2=77002
REQ_ID_2="77002001"

rm -f "$JOB_DIR/${JOB_ID_2}.json" 2>/dev/null
rm -f "$JOBS_DIR/${BANK}@${BASE}@${JOB_ID_2}.json" 2>/dev/null
rm -f "$JOBS_DIR/error/${BANK}@${BASE}@${JOB_ID_2}.json" 2>/dev/null
rm -f "$JOBS_DIR/success/${BANK}@${BASE}@${JOB_ID_2}.json" 2>/dev/null
rm -f "$JOB_DIR/processing/${JOB_ID_2}.json" 2>/dev/null
rm -f "$JOB_DIR/sended/${JOB_ID_2}.json" 2>/dev/null
redis-cli -n "$REDIS_DB" --scan --pattern "*${JOB_ID_2}*" 2>/dev/null | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true
redis-cli -n "$REDIS_DB" --scan --pattern "lock:*${JOB_ID_2}*" 2>/dev/null | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true

# Файл с ошибкой (amount<0 → mockapi 400)
cat > "$JOB_DIR/${JOB_ID_2}.json" << EOF
[{"requestId":"${REQ_ID_2}","amount":-100}]
EOF

cat > "$JOBS_DIR/${BANK}@${BASE}@${JOB_ID_2}.json" << EOF
{
  "bank": "${BANK}", "base": "${BASE}", "job_id": ${JOB_ID_2},
  "job_name": "Smoke Test 2", "created_at": "2026-09-22T10:00:00",
  "files": [{"filename": "${JOB_ID_2}.json", "count": 1, "request_ids": ["${REQ_ID_2}"]}],
  "total_requests": 1, "status": "pending"
}
EOF

PUBLISH_2=$(timeout 10 curl -s "${BASE_URL}/create_payload_mq/${BANK}/${BASE}/${JOB_ID_2}")
TASK_2=$(echo "$PUBLISH_2" | jq -r '.data.task_id // empty' 2>/dev/null)

if [ -z "$TASK_2" ] || [ "$TASK_2" = "null" ]; then
    PUBLISH_ERR_2=$(echo "$PUBLISH_2" | jq -r '.error // .detail // "unknown"' 2>/dev/null)
    test_fail "[2] Не удалось опубликовать Job ${JOB_ID_2}: ${PUBLISH_ERR_2}"
else
    sleep 4
    # Проверка: Job в error/ + SOAP Notify в логах
    if [ -f "$JOBS_DIR/error/${BANK}@${BASE}@${JOB_ID_2}.json" ] \
        && grep -q "SOAP Notify.*${JOB_ID_2}" "$PROJECT_DIR/logs/sbp-dev.log" 2>/dev/null; then
        test_pass
    elif [ ! -f "$JOBS_DIR/error/${BANK}@${BASE}@${JOB_ID_2}.json" ]; then
        test_fail "[2] Job ${JOB_ID_2} не в error/"
    else
        test_fail "[2] SOAP Notify не вызвался для Job ${JOB_ID_2}"
    fi
fi

# ============================================================
#                   [3] CALLBACK БЕЗ JOB
# ============================================================

test_step 3 "Callback без Job (not_found)"

CALLBACK_3=$(timeout 10 curl -s -X POST "${BASE_URL}/callback" \
    -H "Content-Type: application/json" \
    -d '[{"requestId":"nonexistent-99999","qrPayload":null,"errorMessage":null}]')

STATUS_3=$(echo "$CALLBACK_3" | jq -r '.status // empty' 2>/dev/null)
NOT_FOUND_3=$(echo "$CALLBACK_3" | jq -r '.not_found_ids | length' 2>/dev/null)

if [ "$STATUS_3" = "success" ] && [ "$NOT_FOUND_3" = "1" ]; then
    test_pass
else
    test_fail "[3] Callback вернул status='${STATUS_3}', not_found=${NOT_FOUND_3}"
fi

# ============================================================
#                   [4] FALLBACK SQLITE
# ============================================================

test_step 4 "Fallback SQLite (Redis пуст)"

# Создаём запись в SQLite напрямую (без Redis)
# ⚠️ requestId должен быть числом (требование 1С)
REQ_4="77999001"

# Через Python — запись в SQLite
python3 -c "
from modules import db
ok, err = db.save_to_db('${REQ_4}', '${BASE}')
print('OK' if ok else 'ERR')
" 2>/dev/null > /tmp/fallback_smoke.txt

SQLITE_SAVE=$(cat /tmp/fallback_smoke.txt 2>/dev/null | tail -1)

if [ "$SQLITE_SAVE" != "OK" ]; then
    test_fail "[4] Не удалось сохранить в SQLite: ${SQLITE_SAVE}"
else
    # Проверяем, что в Redis нет
    REDIS_HAS=$(redis-cli -n "$REDIS_DB" exists "req:${REQ_4}" 2>/dev/null)
    if [ "$REDIS_HAS" != "0" ]; then
        test_fail "[4] req:${REQ_4} уже есть в Redis (ожидалось пусто)"
    else
        # Callback — должен найти base через SQLite
        CALLBACK_4=$(timeout 10 curl -s -X POST "${BASE_URL}/callback" \
            -H "Content-Type: application/json" \
            -d "[{\"requestId\":\"${REQ_4}\",\"qrPayload\":null,\"errorMessage\":null}]")

        FOUND_4=$(echo "$CALLBACK_4" | jq -r --arg base "$BASE" '.[$base].status // empty' 2>/dev/null)
        if [ "$FOUND_4" = "success" ] || [ "$FOUND_4" = "error" ] || [ "$FOUND_4" = "warning" ]; then
            test_pass
        else
            NOT_FOUND_4=$(echo "$CALLBACK_4" | jq -r '._not_found.request_ids // [] | length' 2>/dev/null)
            test_fail "[4] Fallback не сработал (found='${FOUND_4}', not_found=${NOT_FOUND_4})"
        fi
    fi
fi
rm -f /tmp/fallback_smoke.txt 2>/dev/null

# ============================================================
#                   [5] КОНКУРЕНТНОСТЬ (5 JOB)
# ============================================================

test_step 5 "Конкурентность (5 Job параллельно)"

CONCURRENT_JOBS=(77101 77102 77103 77104 77105)
CONCURRENT_TASKS=()

# Создать 5 Job
for jid in "${CONCURRENT_JOBS[@]}"; do
    req_id="${jid}001"

    # Очистка файлов
    rm -f "$JOB_DIR/${jid}.json" 2>/dev/null
    rm -f "$JOBS_DIR/${BANK}@${BASE}@${jid}.json" 2>/dev/null
    rm -f "$JOBS_DIR/error/${BANK}@${BASE}@${jid}.json" 2>/dev/null
    rm -f "$JOBS_DIR/success/${BANK}@${BASE}@${jid}.json" 2>/dev/null
    rm -f "$JOB_DIR/processing/${jid}.json" 2>/dev/null
    rm -f "$JOB_DIR/sended/${jid}.json" 2>/dev/null

    # Очистка Redis (lock, req, task) — иначе JOB_ALREADY_PROCESSING
    redis-cli -n "$REDIS_DB" --scan --pattern "*${jid}*" 2>/dev/null \
        | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true
    redis-cli -n "$REDIS_DB" --scan --pattern "*${req_id}*" 2>/dev/null \
        | xargs -r redis-cli -n "$REDIS_DB" del > /dev/null 2>&1 || true

    cat > "$JOB_DIR/${jid}.json" << EOF
[{"requestId":"${req_id}","amount":100}]
EOF

    cat > "$JOBS_DIR/${BANK}@${BASE}@${jid}.json" << EOF
{
  "bank": "${BANK}", "base": "${BASE}", "job_id": ${jid},
  "job_name": "Concurrent ${jid}", "created_at": "2026-09-22T10:00:00",
  "files": [{"filename": "${jid}.json", "count": 1, "request_ids": ["${req_id}"]}],
  "total_requests": 1, "status": "pending"
}
EOF
done

# Публикация всех 5 параллельно
for jid in "${CONCURRENT_JOBS[@]}"; do
    (timeout 10 curl -s "${BASE_URL}/create_payload_mq/${BANK}/${BASE}/${jid}" > /tmp/smoke_concurrent_${jid}.json) &
done
wait

sleep 6

# Проверка: все 5 обработаны, каждый взят 1 раз
DUPLICATES=0
NOT_DONE=0
for jid in "${CONCURRENT_JOBS[@]}"; do
    # Проверка "взят 1 раз" — через grep в логах
    TAKEN_COUNT=$(grep -c "ВЗЯЛ Job ${BANK}@${BASE}@${jid}" "$PROJECT_DIR/logs/sbp-dev.log" 2>/dev/null)
    TAKEN_COUNT=${TAKEN_COUNT:-0}
    if [ "$TAKEN_COUNT" -gt "1" ]; then
        DUPLICATES=$((DUPLICATES + 1))
    fi
    # Проверка завершения
    if [ ! -f "$JOBS_DIR/success/${BANK}@${BASE}@${jid}.json" ] \
        && [ ! -f "$JOBS_DIR/error/${BANK}@${BASE}@${jid}.json" ]; then
        NOT_DONE=$((NOT_DONE + 1))
    fi
done

if [ "$DUPLICATES" = "0" ] && [ "$NOT_DONE" = "0" ]; then
    test_pass
else
    test_fail "[5] Дубликатов: ${DUPLICATES}, не завершено: ${NOT_DONE}"
fi

# Очистка временных файлов
rm -f /tmp/smoke_concurrent_*.json 2>/dev/null

# ============================================================
#                   [6] STOP_PAYLOAD УСПЕХ
# ============================================================

test_step 6 "stop_payload — успех"

STOP_JOB_ID=77201
STOP_REQ_ID="77201001"
STOP_FILE="$JOB_DIR/stop/${STOP_JOB_ID}.json"

rm -f "$STOP_FILE" 2>/dev/null
rm -f "$JOB_DIR/${STOP_JOB_ID}.json" 2>/dev/null
rm -f "$JOBS_DIR/${BANK}@${BASE}@${STOP_JOB_ID}.json" 2>/dev/null
rm -f "$JOBS_DIR/error/${BANK}@${BASE}@${STOP_JOB_ID}.json" 2>/dev/null
rm -f "$JOBS_DIR/success/${BANK}@${BASE}@${STOP_JOB_ID}.json" 2>/dev/null

# Создаём Job + req:*
cat > "$JOB_DIR/${STOP_JOB_ID}.json" << EOF
[{"requestId":"${STOP_REQ_ID}","amount":100}]
EOF

cat > "$JOBS_DIR/${BANK}@${BASE}@${STOP_JOB_ID}.json" << EOF
{
  "bank": "${BANK}", "base": "${BASE}", "job_id": ${STOP_JOB_ID},
  "job_name": "Stop test", "created_at": "2026-09-22T10:00:00",
  "files": [{"filename": "${STOP_JOB_ID}.json", "count": 1, "request_ids": ["${STOP_REQ_ID}"]}],
  "total_requests": 1, "status": "pending"
}
EOF

timeout 10 curl -s "${BASE_URL}/create_payload_mq/${BANK}/${BASE}/${STOP_JOB_ID}" > /dev/null
sleep 4

# Создаём stop-файл
mkdir -p "$JOB_DIR/stop"
cat > "$STOP_FILE" << EOF
[{"requestId":"${STOP_REQ_ID}"}]
EOF

# Вызываем stop_payload
STOP_RESULT=$(timeout 10 curl -s "${BASE_URL}/stop_payload/${BANK}/${BASE}/${STOP_JOB_ID}")
STOP_STATUS=$(echo "$STOP_RESULT" | jq -r '.status // empty' 2>/dev/null)
STOP_BLOCKED=$(echo "$STOP_RESULT" | jq -r '.data.blocked // 0' 2>/dev/null)

if [ "$STOP_STATUS" = "SUCCESS" ] && [ "$STOP_BLOCKED" -ge "1" ]; then
    test_pass
else
    test_fail "[6] stop_payload: status='${STOP_STATUS}', blocked=${STOP_BLOCKED}"
fi

# ============================================================
#                   [7] STOP_PAYLOAD FILE_NOT_FOUND
# ============================================================

test_step 7 "stop_payload — FILE_NOT_FOUND"

NOTFOUND_RESULT=$(timeout 10 curl -s "${BASE_URL}/stop_payload/${BANK}/${BASE}/99999999")
NOTFOUND_CODE=$(echo "$NOTFOUND_RESULT" | jq -r '.code // empty' 2>/dev/null)

if [ "$NOTFOUND_CODE" = "FILE_NOT_FOUND" ]; then
    test_pass
else
    test_fail "[7] Ожидался FILE_NOT_FOUND, получено code='${NOTFOUND_CODE}'"
fi

# ============================================================
#                   [8] STOP_PAYLOAD CONFIG_ERROR
# ============================================================

test_step 8 "stop_payload — CONFIG_ERROR (bad bank)"

CONFIG_RESULT=$(timeout 10 curl -s "${BASE_URL}/stop_payload/xx/${BASE}/123")
CONFIG_CODE=$(echo "$CONFIG_RESULT" | jq -r '.code // empty' 2>/dev/null)

if [ "$CONFIG_CODE" = "CONFIG_ERROR" ]; then
    test_pass
else
    test_fail "[8] Ожидался CONFIG_ERROR, получено code='${CONFIG_CODE}'"
fi

# ============================================================
#                   [9] /HEALTH/DETAILED
# ============================================================

test_step 9 "/health/detailed — 7 компонентов"

HEALTH_RESULT=$(timeout 10 curl -s "${BASE_URL}/health/detailed")
HEALTH_STATUS=$(echo "$HEALTH_RESULT" | jq -r '.status // empty' 2>/dev/null)
COMPONENTS_COUNT=$(echo "$HEALTH_RESULT" | jq -r '.components | keys | length' 2>/dev/null)

if [ "$HEALTH_STATUS" = "ok" ] && [ "$COMPONENTS_COUNT" = "7" ]; then
    test_pass
else
    test_fail "[9] /health/detailed: status='${HEALTH_STATUS}', components=${COMPONENTS_COUNT} (ожидалось 7)"
fi

# ============================================================
#                   [10] /MONITOR/DATA
# ============================================================

test_step 10 "/monitor/data — JSON с processing_count"

MONITOR_RESULT=$(timeout 10 curl -s "${BASE_URL}/monitor/data")
MONITOR_PROCESSING=$(echo "$MONITOR_RESULT" | jq -r '.processing_count // "null"' 2>/dev/null)
MONITOR_COMPLETED=$(echo "$MONITOR_RESULT" | jq -r '.completed_count // "null"' 2>/dev/null)

if [ "$MONITOR_PROCESSING" != "null" ] && [ "$MONITOR_COMPLETED" != "null" ]; then
    test_pass
else
    test_fail "[10] /monitor/data не содержит processing_count или completed_count"
fi

# ============================================================
#                   ИТОГИ
# ============================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}════════════════════════════════════════════════${NC}"

if [ "$FAIL" = "0" ]; then
    echo -e "${GREEN}  🎉 ВСЕ ${TOTAL} ТЕСТОВ ПРОЙДЕНЫ (${ELAPSED} сек)${NC}"
else
    echo -e "${RED}  ❌ ПРОВАЛЕНО ${FAIL} из ${TOTAL} (${ELAPSED} сек)${NC}"
    echo ""
    echo -e "${YELLOW}  Детали:${NC}"
    for detail in "${FAILED_DETAILS[@]}"; do
        echo -e "${RED}${detail}${NC}"
    done
fi

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo ""

exit $FAIL
