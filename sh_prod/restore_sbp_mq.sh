#!/bin/bash
# restore_sbp_mq.sh — Восстановление проекта SBP MQ (с сохранением venv)

# ============================================================
# НАСТРОЙКИ
# ============================================================


# Загружаем .env

# Загружаем .env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEV_DIR="$(dirname "$SCRIPT_DIR")"
source "$DEV_DIR/sh_common/load_env.sh" "$DEV_DIR" || exit 1

PROJECT_DIR="/var/www/html/sbp_mq"
BACKUP_DIR="/var/www/html/backups"
OWNER="user"

# Список всех сервисов
ALL_SERVICES=(
    "sbp_mq-debug"
    "sbp_mq-worker"
    "sbp_mq-worker@1"
    "sbp_mq-worker@2"
    "sbp_mq-worker@3"
)

# ============================================================
# ПРОВЕРКА АРГУМЕНТОВ
# ============================================================

if [ -z "$1" ]; then
    echo "❌ Укажите имя бэкапа:"
    echo "   ./restore_sbp_mq.sh sbp_mq_backup_20260912_120000.tar.gz"
    echo ""
    echo "📋 Доступные бэкапы:"
    ls -lh $BACKUP_DIR/sbp_mq_backup_*.tar.gz 2>/dev/null | tail -5 || echo "   (нет бэкапов)"
    exit 1
fi

BACKUP_FILE="$1"
DATE=$(echo $BACKUP_FILE | sed 's/sbp_mq_backup_\(.*\)\.tar\.gz/\1/')
PERMISSIONS_INFO="${BACKUP_DIR}/sbp_mq_permissions_${DATE}.info"
REQUIREMENTS_FILE="${BACKUP_DIR}/sbp_mq_requirements_${DATE}.txt"
ENV_FILE="${BACKUP_DIR}/sbp_mq_env_${DATE}.backup"
SYSTEMD_DIR="${BACKUP_DIR}/sbp_mq_systemd_${DATE}"

if [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    echo "❌ Файл бэкапа не найден: ${BACKUP_DIR}/${BACKUP_FILE}"
    exit 1
fi

# ============================================================
# ПОДТВЕРЖДЕНИЕ
# ============================================================

echo ""
echo "⚠️  ВНИМАНИЕ! Будет восстановлен проект SBP MQ:"
echo "   📦 ${BACKUP_FILE}"
echo "   📅 Дата: ${DATE}"
echo "   👤 Владелец: ${OWNER}:${OWNER}"
echo "   📁 Проект: ${PROJECT_DIR}"
echo ""
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Отменено"
    exit 1
fi

# ============================================================
# ОСТАНОВКА ВСЕХ СЕРВИСОВ
# ============================================================

echo ""
echo "⏹️  Останавливаем сервисы..."
for svc in "${ALL_SERVICES[@]}"; do
    sudo systemctl stop "$svc" 2>/dev/null && echo "   ⏹️  $svc остановлен" || true
done
sleep 2

# ============================================================
# СОХРАНЕНИЕ VENV
# ============================================================

TEMP_VENV=""
if [ -d "$PROJECT_DIR/.venv" ]; then
    TEMP_VENV="/tmp/venv_backup_${DATE}"
    echo "🐍 Сохраняем .venv → $TEMP_VENV"
    mv "$PROJECT_DIR/.venv" "$TEMP_VENV" 2>/dev/null || true
elif [ -d "$PROJECT_DIR/venv" ]; then
    TEMP_VENV="/tmp/venv_backup_${DATE}"
    echo "🐍 Сохраняем venv → $TEMP_VENV"
    mv "$PROJECT_DIR/venv" "$TEMP_VENV" 2>/dev/null || true
fi

# ============================================================
# СОХРАНЕНИЕ ТЕКУЩЕГО .env И config.py
# ============================================================

if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" /tmp/sbp_mq_env_current.bak 2>/dev/null || true
fi

# ============================================================
# ВОССТАНОВЛЕНИЕ
# ============================================================

echo "🗑️  Очищаем проект..."
sudo rm -rf $PROJECT_DIR 2>/dev/null || true
sudo mkdir -p $PROJECT_DIR

echo "📦 Распаковываем бэкап..."
sudo tar -xzf "${BACKUP_DIR}/${BACKUP_FILE}" -C $PROJECT_DIR 2>/dev/null || {
    echo "❌ Ошибка распаковки!"
    exit 1
}

# ============================================================
# ВОССТАНОВЛЕНИЕ VENV
# ============================================================

if [ -n "$TEMP_VENV" ] && [ -d "$TEMP_VENV" ]; then
    echo "🐍 Восстанавливаем venv..."
    mv "$TEMP_VENV" "$PROJECT_DIR/.venv" 2>/dev/null || {
        mv "$TEMP_VENV" "$PROJECT_DIR/venv" 2>/dev/null || true
    }
fi

# ============================================================
# ВОССТАНОВЛЕНИЕ ПРАВ
# ============================================================

echo "🔐 Устанавливаем права (${OWNER}:${OWNER})..."
sudo chown -R ${OWNER}:${OWNER} $PROJECT_DIR
sudo find $PROJECT_DIR -type d -exec chmod 755 {} \; 2>/dev/null || true
sudo find $PROJECT_DIR -type f -exec chmod 644 {} \; 2>/dev/null || true

# Права на venv
if [ -d "$PROJECT_DIR/.venv" ]; then
    sudo chown -R ${OWNER}:${OWNER} $PROJECT_DIR/.venv
    sudo chmod -R 755 $PROJECT_DIR/.venv
    sudo find $PROJECT_DIR/.venv/bin -type f -exec chmod 755 {} \; 2>/dev/null || true
elif [ -d "$PROJECT_DIR/venv" ]; then
    sudo chown -R ${OWNER}:${OWNER} $PROJECT_DIR/venv
    sudo chmod -R 755 $PROJECT_DIR/venv
    sudo find $PROJECT_DIR/venv/bin -type f -exec chmod 755 {} \; 2>/dev/null || true
fi

# ============================================================
# ВОССТАНОВЛЕНИЕ .env
# ============================================================

if [ -f "$ENV_FILE" ]; then
    echo "🔐 Восстанавливаем .env из бэкапа..."
    cp "$ENV_FILE" "$PROJECT_DIR/.env" 2>/dev/null || true
    sudo chown ${OWNER}:${OWNER} "$PROJECT_DIR/.env" 2>/dev/null || true
elif [ -f "/tmp/sbp_mq_env_current.bak" ]; then
    echo "🔐 Восстанавливаем .env из текущего состояния..."
    cp "/tmp/sbp_mq_env_current.bak" "$PROJECT_DIR/.env" 2>/dev/null || true
    sudo chown ${OWNER}:${OWNER} "$PROJECT_DIR/.env" 2>/dev/null || true
fi

# ============================================================
# ВОССТАНОВЛЕНИЕ SYSTEMD-СЕРВИСОВ
# ============================================================

if [ -d "$SYSTEMD_DIR" ] && [ "$(ls -A $SYSTEMD_DIR 2>/dev/null)" ]; then
    echo "📄 Восстанавливаем systemd-сервисы из бэкапа..."
    for svc_file in "$SYSTEMD_DIR"/*.service; do
        if [ -f "$svc_file" ]; then
            svc_name=$(basename "$svc_file")
            echo "   📄 $svc_name"
            sudo cp "$svc_file" "/etc/systemd/system/$svc_name"
        fi
    done
    sudo systemctl daemon-reload
    echo "   ✅ Сервисы восстановлены"
else
    echo "⚠️  Бэкап systemd-сервисов не найден, используются текущие"
fi

# ============================================================
# СОЗДАНИЕ ПАПКИ ЛОГОВ
# ============================================================

mkdir -p "$PROJECT_DIR/logs"
sudo chown -R ${OWNER}:${OWNER} "$PROJECT_DIR/logs"

# ============================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================

if [ -f "$REQUIREMENTS_FILE" ] && [ -d "$PROJECT_DIR/.venv" ]; then
    echo "📦 Устанавливаем зависимости..."
    cd $PROJECT_DIR
    source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null || true
    pip install -r "$REQUIREMENTS_FILE" 2>/dev/null || true
    deactivate 2>/dev/null || true
fi

# ============================================================
# ЗАПУСК СЕРВИСОВ
# ============================================================

echo ""
echo "▶️  Запускаем сервисы..."
for svc in "${ALL_SERVICES[@]}"; do
    if systemctl list-units --full -all 2>/dev/null | grep -q "${svc}.service"; then
        sudo systemctl start "$svc" 2>/dev/null && echo "   ▶️  $svc запущен" || echo "   ⚠️  $svc — не удалось запустить"
    else
        echo "   ⚠️  $svc — не найден в systemd"
    fi
done

sleep 5

# ============================================================
# ПРОВЕРКА СТАТУСА
# ============================================================

echo ""
echo "📊 Статус сервисов:"
for svc in "${ALL_SERVICES[@]}"; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "   ✅ $svc — работает"
    else
        echo "   ⚠️  $svc — не запущен"
    fi
done

# Проверка HTTP
echo ""
echo "🌐 Проверка HTTP (порт ${SBP_MQ_PORT})..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${SBP_MQ_PORT}/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ HTTP: $HTTP_CODE"
else
    echo "   ⚠️  HTTP: $HTTP_CODE (сервер ещё запускается)"
fi

# ============================================================
# РЕЗУЛЬТАТЫ
# ============================================================

echo ""
echo "✅ Восстановление завершено!"
echo "👤 Владелец: ${OWNER}:${OWNER}"
echo "📁 Проект: $PROJECT_DIR"
echo ""
echo "🔧 Если что-то не работает:"
echo "   sudo journalctl -u sbp_mq-debug -f"
echo "   cd $PROJECT_DIR && ./run_debug.sh"