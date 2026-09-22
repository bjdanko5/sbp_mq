#!/bin/bash
# check_backup.sh — проверка содержимого бэкапа SBP MQ
#
# Использование:
#   ./sh_dev/check_backup.sh                          # последний бэкап в /sbp/backups
#   ./sh_dev/check_backup.sh <path/to/backup.tar.gz>  # конкретный файл
#
# Проверяет:
#   1. Структуру архива
#   2. Отсутствие лишних файлов (.venv, .git, .env, *.log, requests.db)
#   3. Наличие ключевых файлов (sbp.py, config.py, routes/, modules/, docs/)
#   4. Соответствие config.py и requirements.txt
#   5. Информацию о версии (version.info)

set -e

# ============================================================
#                   ОПРЕДЕЛЕНИЕ ПРОЕКТА
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck disable=SC1091
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

if [[ "$PROJECT_DIR" == *"_dev" ]]; then
    PREFIX="sbp_mq_dev"
else
    PREFIX="sbp_mq"
fi

BACKUP_DIR="/sbp/backups"

# ============================================================
#                   ЦВЕТА
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}✅ $1${NC}"; }
fail() { echo -e "${RED}❌ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
header() { echo ""; echo -e "${BLUE}═══ $1 ═══${NC}"; }

# ============================================================
#                   ВЫБОР АРХИВА
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}  🔍 ПРОВЕРКА БЭКАПА SBP MQ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo "   Проект: $PROJECT_DIR"
echo "   Префикс: $PREFIX"
echo ""

if [ -n "$1" ]; then
    BACKUP_FILE="$1"
else
    # Автоопределение — последний бэкап
    BACKUP_FILE=$(ls -t "${BACKUP_DIR}/${PREFIX}_backup_"*.tar.gz 2>/dev/null | head -1)
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    fail "Бэкап не найден: $BACKUP_FILE"
    echo ""
    echo "Доступные бэкапы:"
    ls -lt "${BACKUP_DIR}/${PREFIX}_backup_"*.tar.gz 2>/dev/null | head -10 || echo "  (нет)"
    exit 1
fi

echo "   Файл:   $BACKUP_FILE"
echo "   Размер: $(du -h "$BACKUP_FILE" | cut -f1)"
echo ""

# ============================================================
#                   1. VERSION.INFO
# ============================================================

header "1. Информация о версии"

# Найти version.info с той же датой
DATE_PART=$(basename "$BACKUP_FILE" | grep -oE '[0-9]{8}_[0-9]{6}' || echo "")
VERSION_FILE="${BACKUP_DIR}/${PREFIX}_version_${DATE_PART}.info"

if [ -n "$DATE_PART" ] && [ -f "$VERSION_FILE" ]; then
    cat "$VERSION_FILE"
    pass "version.info найден"
else
    warn "version.info не найден рядом с архивом"
fi

# ============================================================
#                   2. СТРУКТУРА АРХИВА
# ============================================================

header "2. Структура архива (первые 30)"

tar -tzf "$BACKUP_FILE" 2>/dev/null | head -30

TOTAL_FILES=$(tar -tzf "$BACKUP_FILE" 2>/dev/null | wc -l)
echo ""
pass "Всего элементов: $TOTAL_FILES"

# ============================================================
#                   3. ЛИШНИЕ ФАЙЛЫ
# ============================================================

header "3. Проверка на лишние файлы"

EXCLUDE_PATTERNS="\.venv|venv/|\.git/|\.env$|\.env\.|\.log$|requests\.db|__pycache__|\.pyc$|node_modules|\.pytest_cache|\.mypy_cache|\.vscode|\.idea|data/|backups/"

EXTRA=$(tar -tzf "$BACKUP_FILE" 2>/dev/null | grep -E "$EXCLUDE_PATTERNS" | head -20 || true)

if [ -z "$EXTRA" ]; then
    pass "Лишних файлов нет (.venv, .git, .env, *.log, requests.db и т.п.)"
else
    fail "Найдены лишние файлы:"
    echo "$EXTRA" | while read -r line; do
        echo "   ⚠️  $line"
    done
fi

# ============================================================
#                   4. КЛЮЧЕВЫЕ ФАЙЛЫ
# ============================================================

header "4. Ключевые файлы"

KEY_FILES=(
    "./config.py"
    "./sbp.py"
    "./run_worker.py"
    "./requirements.txt"
    "./docs/README.md"
    "./modules/"
    "./routes/"
)

KEY_MISSING=0
for f in "${KEY_FILES[@]}"; do
    if tar -tzf "$BACKUP_FILE" 2>/dev/null | grep -qE "^${f//./\.}"; then
        pass "$f"
    else
        fail "$f — НЕ НАЙДЕН"
        KEY_MISSING=$((KEY_MISSING + 1))
    fi
done

if [ "$KEY_MISSING" -eq 0 ]; then
    pass "Все ключевые файлы на месте"
fi

# ============================================================
#                   5. СРАВНЕНИЕ CONFIG.PY
# ============================================================

header "5. Сравнение config.py"

CONFIG_BACKUP="${BACKUP_DIR}/${PREFIX}_config_${DATE_PART}.backup"
if [ -f "$CONFIG_BACKUP" ] && [ -f "$PROJECT_DIR/config.py" ]; then
    if diff -q "$PROJECT_DIR/config.py" "$CONFIG_BACKUP" > /dev/null 2>&1; then
        pass "config.py идентичен"
    else
        warn "config.py отличается от текущего"
        echo "   Сравнение:"
        diff "$PROJECT_DIR/config.py" "$CONFIG_BACKUP" | head -20 || true
    fi
else
    warn "config.py backup не найден"
fi

# ============================================================
#                   6. СРАВНЕНИЕ REQUIREMENTS.TXT
# ============================================================

header "6. Сравнение requirements.txt"

REQ_BACKUP="${BACKUP_DIR}/${PREFIX}_requirements_file_${DATE_PART}.txt"
if [ -f "$REQ_BACKUP" ] && [ -f "$PROJECT_DIR/requirements.txt" ]; then
    if diff -q "$PROJECT_DIR/requirements.txt" "$REQ_BACKUP" > /dev/null 2>&1; then
        pass "requirements.txt идентичен"
    else
        warn "requirements.txt отличается"
        diff "$PROJECT_DIR/requirements.txt" "$REQ_BACKUP" | head -20 || true
    fi
else
    warn "requirements.txt backup не найден"
fi

# ============================================================
#                   7. PIP FREEZE
# ============================================================

header "7. Зависимости (pip freeze)"

PIP_REQ="${BACKUP_DIR}/${PREFIX}_requirements_${DATE_PART}.txt"
if [ -f "$PIP_REQ" ]; then
    REQ_COUNT=$(wc -l < "$PIP_REQ")
    pass "Зависимостей: $REQ_COUNT (${PREFIX}_requirements_${DATE_PART}.txt)"
    echo "   Топ-10:"
    head -10 "$PIP_REQ" | sed 's/^/   /'
else
    warn "pip freeze не найден"
fi

# ============================================================
#                   8. .ENV
# ============================================================

header "8. .env backup"

ENV_BACKUP="${BACKUP_DIR}/${PREFIX}_env_${DATE_PART}.backup"
if [ -f "$ENV_BACKUP" ]; then
    ENV_LINES=$(wc -l < "$ENV_BACKUP")
    pass ".env сохранён ($ENV_LINES строк)"
    # Проверить, что в .env те же ключевые переменные, что в текущем .env
    if [ -f "$PROJECT_DIR/.env" ]; then
        KEY_COUNT_CUR=$(grep -cE "^[A-Z_]+=" "$PROJECT_DIR/.env" 2>/dev/null || echo 0)
        KEY_COUNT_BCK=$(grep -cE "^[A-Z_]+=" "$ENV_BACKUP" 2>/dev/null || echo 0)
        echo "   Переменных сейчас: $KEY_COUNT_CUR, в бэкапе: $KEY_COUNT_BCK"
    fi
else
    warn ".env backup не найден"
fi

# ============================================================
#                   9. ПРОВЕРКА АРХИВА (тест целостности)
# ============================================================

header "9. Целостность архива"

if tar -tzf "$BACKUP_FILE" > /dev/null 2>&1; then
    pass "Архив валиден (tar -tzf OK)"
else
    fail "Архив повреждён!"
fi

# ============================================================
#                   10. ИТОГИ
# ============================================================

echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ ПРОВЕРКА ЗАВЕРШЕНА${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""

# Итоговый вердикт
if [ "$KEY_MISSING" -eq 0 ] && [ -z "$EXTRA" ]; then
    pass "Бэкап валиден — можно использовать для восстановления"
    exit 0
else
    warn "Бэкап требует внимания (см. разделы выше)"
    exit 1
fi