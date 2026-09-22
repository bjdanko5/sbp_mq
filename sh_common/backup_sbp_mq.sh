#!/bin/bash
# backup_sbp_mq.sh — Создание бэкапа проекта SBP MQ (DEV или PROD)
#
# ⚠️ Сервисы НЕ ОСТАНАВЛИВАЮТСЯ — бэкап делается на лету
#
# Использование:
#   cd /var/www/html/sbp_mq_dev && ./sh_common/backup_sbp_mq.sh   → DEV-бэкап
#   cd /var/www/html/sbp_mq     && ./sh_common/backup_sbp_mq.sh   → PROD-бэкап
#
# Место хранения: /sbp/backups
# Имя:            sbp_mq_dev_backup_YYYYMMDD_HHMMSS.tar.gz
#                 sbp_mq_backup_YYYYMMDD_HHMMSS.tar.gz

set -e

# ============================================================
#                   ОПРЕДЕЛЕНИЕ ПРОЕКТА
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# shellcheck disable=SC1091
source "$PROJECT_DIR/sh_common/load_env.sh" "$PROJECT_DIR" || exit 1

# Префикс для имён файлов и сервисов (DEV: sbp_mq_dev, PROD: sbp_mq)
# Определяем по имени PROJECT_DIR (PROJECT_NAME не экспортируется из load_env.sh)
if [[ "$PROJECT_DIR" == *"_dev" ]]; then
    PREFIX="sbp_mq_dev"
    SERVICE_NAME="sbp_mq-dev"
else
    PREFIX="sbp_mq"
    SERVICE_NAME="sbp_mq-debug"
fi

# ============================================================
#                   НАСТРОЙКИ
# ============================================================

BACKUP_DIR="/sbp/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${PREFIX}_backup_${DATE}.tar.gz"
OWNER="user"
MAX_BACKUPS=10

# ============================================================
#                   ЦВЕТА
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "${GREEN}$1${NC}"; }
fail() { echo -e "${RED}$1${NC}"; }
warn() { echo -e "${YELLOW}$1${NC}"; }
info() { echo -e "${BLUE}$1${NC}"; }

# ============================================================
#                   ПРОВЕРКИ
# ============================================================

echo ""
info "════════════════════════════════════════"
info "  📦 БЭКАП SBP MQ"
info "════════════════════════════════════════"
echo "   Проект:  $PROJECT_DIR"
echo "   Префикс: $PREFIX"
echo "   Сервис:  $SERVICE_NAME"
echo "   Порт:    $SBP_MQ_PORT"
echo ""

if [ ! -d "$PROJECT_DIR" ]; then
    fail "❌ Проект не найден: $PROJECT_DIR"
    exit 1
fi

# Создаём BACKUP_DIR
if ! sudo mkdir -p "$BACKUP_DIR" 2>/dev/null; then
    fail "❌ Не удалось создать $BACKUP_DIR"
    exit 1
fi
sudo chown "$OWNER:$OWNER" "$BACKUP_DIR" 2>/dev/null || true
pass "✅ BACKUP_DIR: $BACKUP_DIR"

# ============================================================
#                   ПОИСК VENV
# ============================================================

find_venv() {
    local project_dir="$1"

    if [ -d "$project_dir/.venv" ]; then
        echo "$project_dir/.venv"
        return 0
    elif [ -d "$project_dir/venv" ]; then
        echo "$project_dir/venv"
        return 0
    elif [ -n "$VIRTUAL_ENV" ] && [ -d "$VIRTUAL_ENV" ]; then
        echo "$VIRTUAL_ENV"
        return 0
    fi

    return 1
}

VENV_PATH=$(find_venv "$PROJECT_DIR")
if [ -n "$VENV_PATH" ] && [ -d "$VENV_PATH" ]; then
    pass "🐍 Найден venv: $VENV_PATH"
    SKIP_REQUIREMENTS=false
else
    warn "⚠️  venv не найден"
    SKIP_REQUIREMENTS=true
fi

# ============================================================
#                   СТАТУС СЕРВИСА
# ============================================================

echo ""
info "📊 Проверка статуса сервиса ${SERVICE_NAME}.service..."
if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
    pass "   ✅ Сервис ${SERVICE_NAME} запущен (бэкап на лету)"
else
    warn "   ⚠️  Сервис ${SERVICE_NAME} не запущен"
fi

# ============================================================
#                   ПРАВА (информация)
# ============================================================

echo ""
info "💾 Сохраняем информацию о правах..."
cd "$PROJECT_DIR"

cat > "${BACKUP_DIR}/${PREFIX}_permissions_${DATE}.info" << EOF
OWNER=${OWNER}
GROUP=${OWNER}
TYPE=standard
PROJECT_DIR=${PROJECT_DIR}
PREFIX=${PREFIX}
EOF

find . -type f -not -path "./.venv/*" -not -path "./venv/*" \
    -exec ls -la {} \; 2>/dev/null > "${BACKUP_DIR}/${PREFIX}_file_list_${DATE}.txt" || true

pass "   ✅ Права: ${OWNER}:${OWNER}"

# ============================================================
#                   ЗАВИСИМОСТИ
# ============================================================

echo ""
if [ "$SKIP_REQUIREMENTS" = false ] && [ -n "$VENV_PATH" ]; then
    info "📋 Сохраняем зависимости из ${VENV_PATH}..."

    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate" 2>/dev/null || {
        warn "⚠️  Не удалось активировать ${VENV_PATH}"
        SKIP_REQUIREMENTS=true
    }

    if [ "$SKIP_REQUIREMENTS" = false ]; then
        pip freeze > "${BACKUP_DIR}/${PREFIX}_requirements_${DATE}.txt" 2>/dev/null || {
            warn "⚠️  Ошибка сохранения зависимостей"
        }
        deactivate 2>/dev/null || true
    fi
    pass "   ✅ Зависимости сохранены"
fi

if [ "$SKIP_REQUIREMENTS" = true ]; then
    warn "⚠️  Пропускаем сохранение зависимостей"
fi

# ============================================================
#                   КОНФИГИ
# ============================================================

echo ""
info "🔐 Сохраняем конфиги..."

if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "${BACKUP_DIR}/${PREFIX}_env_${DATE}.backup"
    pass "   ✅ .env"
fi

if [ -f "$PROJECT_DIR/config.py" ]; then
    cp "$PROJECT_DIR/config.py" "${BACKUP_DIR}/${PREFIX}_config_${DATE}.backup"
    pass "   ✅ config.py"
fi

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    cp "$PROJECT_DIR/requirements.txt" "${BACKUP_DIR}/${PREFIX}_requirements_file_${DATE}.txt"
    pass "   ✅ requirements.txt"
fi

# ============================================================
#                   ВЕРСИЯ GIT
# ============================================================

echo ""
info "📌 Сохраняем версию git..."

if [ -d "$PROJECT_DIR/.git" ] || [ -f "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR"
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

    cat > "${BACKUP_DIR}/${PREFIX}_version_${DATE}.info" << EOF
GIT_COMMIT=${GIT_COMMIT}
GIT_BRANCH=${GIT_BRANCH}
BACKUP_DATE=${DATE}
VENV_PATH=${VENV_PATH}
OWNER=${OWNER}
PROJECT_DIR=${PROJECT_DIR}
PREFIX=${PREFIX}
SBP_MQ_PORT=${SBP_MQ_PORT}
EOF
    pass "   ✅ Версия: ${GIT_BRANCH}@${GIT_COMMIT}"
else
    warn "   ⚠️  .git не найден"
fi

# ============================================================
#                   АРХИВ
# ============================================================

echo ""
info "📦 Создаём архив..."

cd "$PROJECT_DIR"

sudo tar -czf "${BACKUP_DIR}/${BACKUP_NAME}" \
    --exclude=".venv" \
    --exclude="venv" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".git" \
    --exclude="*.log" \
    --exclude=".env" \
    --exclude="node_modules" \
    --exclude=".pytest_cache" \
    --exclude=".mypy_cache" \
    --exclude=".vscode" \
    --exclude=".idea" \
    --exclude="sbp.log" \
    --exclude="sbp-dev.log" \
    --exclude="sbp_errors.log" \
    --exclude="sbp-dev_errors.log" \
    --exclude="all.log" \
    --exclude="requests.db" \
    --exclude="*.db-shm" \
    --exclude="*.db-wal" \
    --exclude="data" \
    --exclude="backups" \
    . 2>/dev/null || {
    fail "❌ Ошибка создания архива!"
    exit 1
}

# Восстанавливаем владельца
sudo chown "${OWNER}:${OWNER}" "${BACKUP_DIR}/${BACKUP_NAME}" 2>/dev/null || true

# ============================================================
#                   РЕЗУЛЬТАТЫ
# ============================================================

echo ""
info "════════════════════════════════════════"
pass "  ✅ БЭКАП СОЗДАН"
info "════════════════════════════════════════"
echo "   📦 Файл:     ${BACKUP_DIR}/${BACKUP_NAME}"
echo "   📊 Размер:   $(du -h "${BACKUP_DIR}/${BACKUP_NAME}" 2>/dev/null | cut -f1 || echo 'неизвестно')"
echo "   👤 Владелец: ${OWNER}:${OWNER}"
echo ""

if [ -f "${BACKUP_DIR}/${PREFIX}_requirements_${DATE}.txt" ]; then
    echo "   📋 Зависимости: ${PREFIX}_requirements_${DATE}.txt"
fi
if [ -f "${BACKUP_DIR}/${PREFIX}_env_${DATE}.backup" ]; then
    echo "   🔐 .env:        ${PREFIX}_env_${DATE}.backup"
fi
if [ -f "${BACKUP_DIR}/${PREFIX}_config_${DATE}.backup" ]; then
    echo "   ⚙️  config.py:   ${PREFIX}_config_${DATE}.backup"
fi
if [ -f "${BACKUP_DIR}/${PREFIX}_version_${DATE}.info" ]; then
    echo "   📌 Версия:      $(cat "${BACKUP_DIR}/${PREFIX}_version_${DATE}.info" | tr '\n' ' ')"
fi

# ============================================================
#                   ОЧИСТКА СТАРЫХ
# ============================================================

echo ""
info "🗑️  Очистка старых бэкапов (оставляем ${MAX_BACKUPS})..."

cd "$BACKUP_DIR"
for pattern in \
    "${PREFIX}_backup_*.tar.gz" \
    "${PREFIX}_requirements_*.txt" \
    "${PREFIX}_permissions_*.info" \
    "${PREFIX}_version_*.info" \
    "${PREFIX}_env_*.backup" \
    "${PREFIX}_config_*.backup" \
    "${PREFIX}_file_list_*.txt"
do
    ls -t $pattern 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm 2>/dev/null || true
done
pass "   ✅ Готово"

echo ""
info "📋 Последние ${MAX_BACKUPS} бэкапов ${PREFIX}:"
ls -lh ${PREFIX}_backup_*.tar.gz 2>/dev/null | tail -5 || echo "   (нет бэкапов)"

# ============================================================
#                   СТАТУС СЕРВИСА (финал)
# ============================================================

echo ""
info "📊 Статус сервиса ${SERVICE_NAME}:"
if systemctl is-active --quiet "${SERVICE_NAME}.service" 2>/dev/null; then
    pass "   ✅ Сервис ${SERVICE_NAME} работает"
else
    warn "   ⚠️  Сервис ${SERVICE_NAME} не запущен"
fi

echo ""