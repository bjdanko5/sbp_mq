#!/bin/bash
# backup_sbp_mq.sh — Создание бэкапа проекта SBP MQ
# ⚠️ Сервисы НЕ ОСТАНАВЛИВАЮТСЯ — бэкап делается на лету

# ============================================================
#                     НАСТРОЙКИ
# ============================================================

PROJECT_DIR="/var/www/html/sbp_mq"
BACKUP_DIR="/var/www/html/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="sbp_mq_backup_${DATE}.tar.gz"
SERVICE_NAME="sbp_mq-debug"      # ← для проверки статуса
OWNER="user"

# Список всех сервисов для проверки
ALL_SERVICES=(
    "sbp_mq-debug"
    "sbp_mq-worker"
    "sbp_mq-worker@1"
    "sbp_mq-worker@2"
    "sbp_mq-worker@3"
)

# ============================================================
# ПОИСК VENV
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

# ============================================================
# ПРОВЕРКИ
# ============================================================

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Проект не найден: $PROJECT_DIR"
    exit 1
fi

mkdir -p $BACKUP_DIR

VENV_PATH=$(find_venv "$PROJECT_DIR")
if [ -n "$VENV_PATH" ] && [ -d "$VENV_PATH" ]; then
    echo "🐍 Найден venv: $VENV_PATH"
    SKIP_REQUIREMENTS=false
else
    echo "⚠️  venv не найден"
    SKIP_REQUIREMENTS=true
fi

# ============================================================
# ИНФОРМАЦИЯ О СЕРВИСАХ
# ============================================================

echo ""
echo "📊 Проверка статуса сервисов:"
for svc in "${ALL_SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "   ✅ $svc — запущен"
    else
        echo "   ⚠️  $svc — не запущен"
    fi
done
echo ""

# ============================================================
# СОХРАНЕНИЕ ПРАВ
# ============================================================

echo "💾 Сохраняем информацию о правах (стандартные)..."
cd $PROJECT_DIR

echo "OWNER=${OWNER}" > "${BACKUP_DIR}/sbp_mq_permissions_${DATE}.info"
echo "GROUP=${OWNER}" >> "${BACKUP_DIR}/sbp_mq_permissions_${DATE}.info"
echo "TYPE=standard" >> "${BACKUP_DIR}/sbp_mq_permissions_${DATE}.info"

# Сохраняем список файлов (без .venv, logs, __pycache__)
find . -type f \
    -not -path "./.venv/*" \
    -not -path "./venv/*" \
    -not -path "./logs/*" \
    -not -path "./__pycache__/*" \
    -exec ls -la {} \; 2>/dev/null > "${BACKUP_DIR}/sbp_mq_file_list_${DATE}.txt" || true

echo "   ✅ Права: ${OWNER}:${OWNER}"

# ============================================================
# СОХРАНЕНИЕ ЗАВИСИМОСТЕЙ
# ============================================================

if [ "$SKIP_REQUIREMENTS" = false ] && [ -n "$VENV_PATH" ]; then
    echo "📋 Сохраняем зависимости из ${VENV_PATH}..."
    
    source "${VENV_PATH}/bin/activate" 2>/dev/null || {
        echo "⚠️  Не удалось активировать ${VENV_PATH}"
        SKIP_REQUIREMENTS=true
    }
    
    if [ "$SKIP_REQUIREMENTS" = false ]; then
        pip freeze > "${BACKUP_DIR}/sbp_mq_requirements_${DATE}.txt" 2>/dev/null || {
            echo "⚠️  Ошибка сохранения зависимостей"
        }
        deactivate 2>/dev/null || true
    fi
fi

if [ "$SKIP_REQUIREMENTS" = true ]; then
    echo "⚠️  Пропускаем сохранение зависимостей"
fi

# ============================================================
# СОХРАНЕНИЕ КОНФИГОВ
# ============================================================

if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "${BACKUP_DIR}/sbp_mq_env_${DATE}.backup"
    echo "🔐 Сохранён .env"
fi

if [ -f "$PROJECT_DIR/config.py" ]; then
    cp "$PROJECT_DIR/config.py" "${BACKUP_DIR}/sbp_mq_config_${DATE}.backup"
    echo "⚙️  Сохранён config.py"
fi

# Сохраняем systemd-сервисы
echo "📄 Сохраняем systemd-сервисы..."
mkdir -p "${BACKUP_DIR}/sbp_mq_systemd_${DATE}"
for svc in /etc/systemd/system/sbp_mq*.service; do
    if [ -f "$svc" ]; then
        sudo cp "$svc" "${BACKUP_DIR}/sbp_mq_systemd_${DATE}/" 2>/dev/null || true
    fi
done
echo "   ✅ Сохранено: $(ls ${BACKUP_DIR}/sbp_mq_systemd_${DATE}/ 2>/dev/null | wc -l) сервисов"

# Сохраняем информацию о версии
if [ -d "$PROJECT_DIR/.git" ]; then
    cd $PROJECT_DIR
    GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
    echo "GIT_COMMIT=${GIT_COMMIT}" > "${BACKUP_DIR}/sbp_mq_version_${DATE}.info"
    echo "GIT_BRANCH=${GIT_BRANCH}" >> "${BACKUP_DIR}/sbp_mq_version_${DATE}.info"
    echo "BACKUP_DATE=${DATE}" >> "${BACKUP_DIR}/sbp_mq_version_${DATE}.info"
    echo "VENV_PATH=${VENV_PATH}" >> "${BACKUP_DIR}/sbp_mq_version_${DATE}.info"
    echo "OWNER=${OWNER}" >> "${BACKUP_DIR}/sbp_mq_version_${DATE}.info"
    echo "📌 Версия: ${GIT_BRANCH}@${GIT_COMMIT}"
fi

# ============================================================
# СОЗДАНИЕ АРХИВА
# ============================================================

echo "📦 Создаем архив..."
cd $PROJECT_DIR

sudo tar -czf "${BACKUP_DIR}/${BACKUP_NAME}" \
    --exclude=".venv" \
    --exclude="venv" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".git" \
    --exclude="logs" \
    --exclude="*.log" \
    --exclude="*.log.*" \
    --exclude=".env" \
    --exclude="node_modules" \
    --exclude=".pytest_cache" \
    --exclude=".mypy_cache" \
    --exclude=".vscode" \
    --exclude=".idea" \
    --exclude="requests.db" \
    --exclude="*.db-shm" \
    --exclude="*.db-wal" \
    . 2>/dev/null || {
    echo "❌ Ошибка создания архива!"
    exit 1
}

# ============================================================
# РЕЗУЛЬТАТЫ
# ============================================================

echo ""
echo "✅ Бэкап создан: ${BACKUP_DIR}/${BACKUP_NAME}"
echo "📦 Размер: $(du -h ${BACKUP_DIR}/${BACKUP_NAME} 2>/dev/null | cut -f1 || echo 'неизвестно')"
echo "👤 Владелец: ${OWNER}:${OWNER}"

if [ "$SKIP_REQUIREMENTS" = false ] && [ -f "${BACKUP_DIR}/sbp_mq_requirements_${DATE}.txt" ]; then
    echo "📋 Зависимости: ${BACKUP_DIR}/sbp_mq_requirements_${DATE}.txt"
fi
if [ -f "${BACKUP_DIR}/sbp_mq_env_${DATE}.backup" ]; then
    echo "🔐 .env сохранён: ${BACKUP_DIR}/sbp_mq_env_${DATE}.backup"
fi
if [ -f "${BACKUP_DIR}/sbp_mq_config_${DATE}.backup" ]; then
    echo "⚙️  config.py сохранён: ${BACKUP_DIR}/sbp_mq_config_${DATE}.backup"
fi
if [ -d "${BACKUP_DIR}/sbp_mq_systemd_${DATE}" ]; then
    echo "📄 systemd: ${BACKUP_DIR}/sbp_mq_systemd_${DATE}/"
fi
if [ -f "${BACKUP_DIR}/sbp_mq_version_${DATE}.info" ]; then
    echo "📌 Версия: $(cat ${BACKUP_DIR}/sbp_mq_version_${DATE}.info | tr '\n' ' ')"
fi

# ============================================================
# ПРОВЕРКА СЕРВИСОВ
# ============================================================

echo ""
echo "📊 Статус сервисов после бэкапа:"
for svc in "${ALL_SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "   ✅ $svc — работает"
    else
        echo "   ⚠️  $svc — не запущен"
    fi
done

# ============================================================
# ОЧИСТКА СТАРЫХ БЭКАПОВ
# ============================================================

echo ""
echo "🗑️  Очищаем старые бэкапы (оставляем 10)..."
cd $BACKUP_DIR
ls -t sbp_mq_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm 2>/dev/null
ls -t sbp_mq_requirements_*.txt 2>/dev/null | tail -n +11 | xargs -r rm 2>/dev/null
ls -t sbp_mq_permissions_*.info 2>/dev/null | tail -n +11 | xargs -r rm 2>/dev/null
ls -t sbp_mq_version_*.info 2>/dev/null | tail -n +11 | xargs -r rm 2>/dev/null
echo "✅ Готово!"

echo ""
echo "📋 Список текущих бэкапов:"
ls -lh $BACKUP_DIR/sbp_mq_backup_*.tar.gz 2>/dev/null | tail -5 || echo "   (нет бэкапов)"