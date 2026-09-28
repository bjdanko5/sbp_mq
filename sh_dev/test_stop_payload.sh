#!/bin/bash
# test_stop_payload.sh — smoke-тест stop_payload (legacy + новый эндпоинт)
#
# Проверяет:
#   1. Legacy /stop_payload/{base} — NO_FILES
#   2. Legacy /stop_payload/{base} — успех (PATCH через legacy api_bank)
#   3. New /stop_payload/{bank}/{base}/{job_id} — CONFIG_ERROR (неизвестный bank)
#   4. New /stop_payload/{bank}/{base}/{job_id} — FILE_NOT_FOUND
#   5. New /stop_payload/{bank}/{base}/{job_id} — успех (PATCH через factory)
#
# Использование:
#   ./sh_dev/test_stop_payload.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck disable=SC1091
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

BASE_URL="http://localhost:${SBP_MQ_PORT}"
BANK="ci"
BASE="zkh_ursv"

# Тестовые Job ID (уникальные, не пересекаются с test_monitor_v2)
JOB_ID_LEGACY=88001
JOB_ID_NEW=88002
REQ_LEGACY_1="88001001"
REQ_LEGACY_2="88001002"
REQ_NEW_1="88002001"
REQ_NEW_2="88002002"

SBP_ROOT="$SBP_ROOT4MQ"
JOB_DIR="$SBP_ROOT/$BANK/$BASE"
STOP_DIR="$JOB_DIR/stop"
STOPED_DIR="$JOB_DIR/stoped"
JOBS_DIR="$SBP_ROOT/jobs"

# ============================================================
#                   ХЕЛПЕРЫ
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; exit 1; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }

assert_eq() {
    local actual="$1"
    local expected="$2"
    local msg="$3"
    if [ "$actual" = "$expected" ]; then
        pass "$msg: $actual"
    else
        fail "$msg: ожидалось '$expected', получено '$actual'"
    fi
}

# ============================================================
#                   ПОДГОТОВКА
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}🧪 ТЕСТ STOP_PAYLOAD${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo "   API:       $BASE_URL"
echo "   Bank:      $BANK"
echo "   Base:      $BASE"
echo "   Legacy ID: $JOB_ID_LEGACY"
echo "   New ID:    $JOB_ID_NEW"
echo ""

# 1. Проверка API
info "Проверка API..."
health_code=$(timeout 5 curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" || echo "000")
if [ "$health_code" != "200" ]; then
    fail "API не отвечает (HTTP $health_code)"
fi
pass "API OK"

# 2. Очистка от прошлых прогонов
info "Очистка старых файлов..."
rm -f "$STOP_DIR/$JOB_ID_LEGACY.json" 2>/dev/null
rm -f "$STOP_DIR/$JOB_ID_NEW.json" 2>/dev/null
rm -f "$STOPED_DIR/$JOB_ID_LEGACY.json" 2>/dev/null
rm -f "$STOPED_DIR/$JOB_ID_NEW.json" 2>/dev/null
rm -f "$JOBS_DIR/$BANK@$BASE@$JOB_ID_LEGACY.json" 2>/dev/null
rm -f "$JOBS_DIR/$BANK@$BASE@$JOB_ID_NEW.json" 2>/dev/null
sudo rm -f "$JOB_DIR/$JOB_ID_LEGACY.json" 2>/dev/null
sudo rm -f "$JOB_DIR/$JOB_ID_NEW.json" 2>/dev/null
pass "Очищено"

# 3. Создание директорий
mkdir -p "$STOP_DIR" "$STOPED_DIR" "$JOBS_DIR"
pass "Директории готовы"

# ============================================================
#                   ТЕСТ 1: Legacy — NO_FILES
# ============================================================

echo ""
echo -e "${YELLOW}[1] Legacy /stop_payload/{base} — NO_FILES${NC}"

resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/$BASE")
code=$(echo "$resp" | jq -r '.code')
assert_eq "$code" "NO_FILES" "Legacy NO_FILES"

# ============================================================
#                   ТЕСТ 2: Legacy — успех
# ============================================================

echo ""
echo -e "${YELLOW}[2] Legacy /stop_payload/{base} — с файлом${NC}"

# Создаём файл с запросами
cat > "$JOB_DIR/$JOB_ID_LEGACY.json" <<EOF
[{"requestId":"$REQ_LEGACY_1","amount":100},{"requestId":"$REQ_LEGACY_2","amount":200}]
EOF

# Создаём Job
cat > "$JOBS_DIR/$BANK@$BASE@$JOB_ID_LEGACY.json" <<EOF
{
  "bank": "$BANK", "base": "$BASE", "job_id": $JOB_ID_LEGACY,
  "job_name": "Legacy Stop Test", "created_at": "2026-09-21T12:00:00",
  "files": [{"filename": "$JOB_ID_LEGACY.json", "count": 2, "request_ids": ["$REQ_LEGACY_1", "$REQ_LEGACY_2"]}],
  "total_requests": 2, "status": "pending"
}
EOF

# Публикуем Job (создаёт req:* в Redis)
info "Публикация Job $JOB_ID_LEGACY..."
timeout 10 curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID_LEGACY" > /dev/null
sleep 5

# Проверяем req:*
redis_count=$(redis-cli -n "$REDIS_DB" keys "req:${REQ_LEGACY_1}*" | wc -l)
assert_eq "$redis_count" "1" "req:$REQ_LEGACY_1 в Redis"

# Создаём stop-файл
cat > "$STOP_DIR/$JOB_ID_LEGACY.json" <<EOF
[{"requestId": "$REQ_LEGACY_1"}, {"requestId": "$REQ_LEGACY_2"}]
EOF

# Вызываем legacy
resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/$BASE")
status=$(echo "$resp" | jq -r '.status')
blocked=$(echo "$resp" | jq -r '.data.results[0].data.blocked // 0')
assert_eq "$status" "SUCCESS" "Legacy stop_payload"
assert_eq "$blocked" "2" "Legacy blocked"

# Проверяем перемещение
if [ -f "$STOPED_DIR/$JOB_ID_LEGACY.json" ]; then
    pass "Файл $JOB_ID_LEGACY.json перемещён в stoped/"
else
    fail "Файл $JOB_ID_LEGACY.json НЕ перемещён"
fi

# ============================================================
#                   ТЕСТ 3: New — CONFIG_ERROR
# ============================================================

echo ""
echo -e "${YELLOW}[3] New /stop_payload/{bank}/{base}/{job_id} — CONFIG_ERROR${NC}"

resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/xx/$BASE/123")
code=$(echo "$resp" | jq -r '.code')
assert_eq "$code" "CONFIG_ERROR" "Неизвестный bank"

# ============================================================
#                   ТЕСТ 4: New — FILE_NOT_FOUND
# ============================================================

echo ""
echo -e "${YELLOW}[4] New /stop_payload/{bank}/{base}/{job_id} — FILE_NOT_FOUND${NC}"

resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/$BANK/$BASE/99999999")
code=$(echo "$resp" | jq -r '.code')
assert_eq "$code" "FILE_NOT_FOUND" "Файла нет"

# ============================================================
#                   ТЕСТ 5: New — успех
# ============================================================

echo ""
echo -e "${YELLOW}[5] New /stop_payload/{bank}/{base}/{job_id} — успех${NC}"

# Создаём файл с запросами
cat > "$JOB_DIR/$JOB_ID_NEW.json" <<EOF
[{"requestId":"$REQ_NEW_1","amount":100},{"requestId":"$REQ_NEW_2","amount":200}]
EOF

# Создаём Job
cat > "$JOBS_DIR/$BANK@$BASE@$JOB_ID_NEW.json" <<EOF
{
  "bank": "$BANK", "base": "$BASE", "job_id": $JOB_ID_NEW,
  "job_name": "MQ Stop Test", "created_at": "2026-09-21T12:00:00",
  "files": [{"filename": "$JOB_ID_NEW.json", "count": 2, "request_ids": ["$REQ_NEW_1", "$REQ_NEW_2"]}],
  "total_requests": 2, "status": "pending"
}
EOF

# Публикуем Job
info "Публикация Job $JOB_ID_NEW..."
timeout 10 curl -s "$BASE_URL/create_payload_mq/$BANK/$BASE/$JOB_ID_NEW" > /dev/null
sleep 5

# Создаём stop-файл
cat > "$STOP_DIR/$JOB_ID_NEW.json" <<EOF
[{"requestId": "$REQ_NEW_1"}, {"requestId": "$REQ_NEW_2"}]
EOF

# Вызываем новый
resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/$BANK/$BASE/$JOB_ID_NEW")
status=$(echo "$resp" | jq -r '.status')
blocked=$(echo "$resp" | jq -r '.data.blocked // 0')
status_code=$(echo "$resp" | jq -r '.data.status_code // 0')
assert_eq "$status" "SUCCESS" "New stop_payload"
assert_eq "$blocked" "2" "New blocked"
assert_eq "$status_code" "202" "New status_code"

# Проверяем перемещение
if [ -f "$STOPED_DIR/$JOB_ID_NEW.json" ]; then
    pass "Файл $JOB_ID_NEW.json перемещён в stoped/"
else
    fail "Файл $JOB_ID_NEW.json НЕ перемещён"
fi

# ============================================================
#                   ТЕСТ 6: New — уже в stoped
# ============================================================

echo ""
echo -e "${YELLOW}[6] New — повторный вызов (файл уже в stoped/)${NC}"

resp=$(timeout 10 curl -s "$BASE_URL/stop_payload/$BANK/$BASE/$JOB_ID_NEW")
code=$(echo "$resp" | jq -r '.code')
assert_eq "$code" "FILE_NOT_FOUND" "Уже обработан"

# ============================================================
#                   ИТОГИ
# ============================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo "   ✅ Legacy /stop_payload/{base}"
echo "   ✅ New /stop_payload/{bank}/{base}/{job_id}"
echo "   ✅ CONFIG_ERROR (неизвестный bank)"
echo "   ✅ FILE_NOT_FOUND (файла нет)"
echo "   ✅ FILE_NOT_FOUND (уже в stoped/)"
echo ""

# Финальная очистка (опционально)
# info "Финальная очистка..."
# rm -f "$STOPED_DIR/$JOB_ID_LEGACY.json" "$STOPED_DIR/$JOB_ID_NEW.json" 2>/dev/null