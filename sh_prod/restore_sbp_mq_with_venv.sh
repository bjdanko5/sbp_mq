#!/bin/bash
# restore_sbp_mq_with_venv.sh — Восстановление SBP MQ с ПЕРЕСОЗДАНИЕМ venv
# Используйте ТОЛЬКО если venv сломался или нужно обновить Python

# ============================================================
# НАСТРОЙКИ
# ============================================================

PROJECT_DIR="/var/www/html/sbp_mq"
BACKUP_DIR="/var/www/html/backups"
OWNER="user"
VENV_NAME=".venv"

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
    echo "   ./restore_sbp_mq_with_venv.sh sbp_mq_backup_20260912_120000.tar.gz"
    echo ""
    echo "📋 Доступные бэкапы:"
    ls -lh $BACKUP_DIR/sbp_mq_backup_*.tar.gz 2>/dev/null | tail -5 || echo "   (нет бэкапов)"
    exit 1
fi

BACKUP_FILE="$1"
DATE=$(echo $BACKUP_FILE | sed 's/sbp_mq_backup_\(.*\)\.tar\.gz/\1/')
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
echo "⚠️  ВНИМАНИЕ! Будет ПЕРЕСОЗДАН venv!"
echo "   📦 ${BACKUP_FILE}"
echo "   📅 Дата: ${DATE}"
echo "   👤 Владелец: ${OWNER}:${OWNER}"
echo "   📁 Проект: ${PROJECT_DIR}"
echo "   🐍 Будет создан новый ${VENV_NAME}"
echo ""
echo "   ⚡ Это займёт 2-5 минут (зависит от количества пакетов)"
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
sleep 3

# ============================================================
# СОЗДАНИЕ БЭКАПА ТЕКУЩЕГО СОСТОЯНИЯ
# ============================================================

CURRENT_BACKUP="sbp_mq_current_state_$(date +%Y%m%d_%H%M%S)"
if [ -d "$PROJECT_DIR" ]; then
    echo "📦 Создаем бэкап текущего состояния: ${CURRENT_BACKUP}..."
    sudo cp -r "$PROJECT_DIR" "${BACKUP_DIR}/${CURRENT_BACKUP}" 2>/dev/null || {
        echo "   ⚠️  Не удалось создать бэкап (продолжаем)"
    }
fi

# ============================================================
# УДАЛЕНИЕ СТАРОГО ПРОЕКТА
# ============================================================

echo "🗑️  Удаляем все старые файлы (включая ${VENV_NAME})..."
sudo rm -rf "$PROJECT_DIR" 2>/dev/null || true

# ============================================================
# ВОССТАНОВЛЕНИЕ ИЗ БЭКАПА
# ============================================================

echo "📂 Создаём свежую папку проекта..."
sudo mkdir -p "$PROJECT_DIR"

echo "📦 Распаковываем бэкап..."
sudo tar -xzf "${BACKUP_DIR}/${BACKUP_FILE}" -C "$PROJECT_DIR" 2>/dev/null || {
    echo "❌ Ошибка распаковки бэкапа!"
    exit 1
}

# ============================================================
# ВОССТАНОВЛЕНИЕ ПРАВ (до создания venv)
# ============================================================

echo "🔐 Устанавливаем права (${OWNER}:${OWNER})..."
sudo chown -R ${OWNER}:${OWNER} "$PROJECT_DIR"
sudo find "$PROJECT_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
sudo find "$PROJECT_DIR" -type f -exec chmod 644 {} \; 2>/dev/null || true

# ============================================================
# ВОССТАНОВЛЕНИЕ SYSTEMD-СЕРВИСОВ
# ============================================================

if [ -d "$SYSTEMD_DIR" ] && [ "$(ls -A $SYSTEMD_DIR 2>/dev/null)" ]; then
    echo "📄 Восстанавливаем systemd-сервисы..."
    for svc_file in "$SYSTEMD_DIR"/*.service; do
        if [ -f "$svc_file" ]; then
            svc_name=$(basename "$svc_file")
            echo "   📄 $svc_name"
            sudo cp "$svc_file" "/etc/systemd/system/$svc_name"
        fi
    done
    sudo systemctl daemon-reload
    echo "   ✅ Сервисы восстановлены"
fi

# ============================================================
# СОЗДАНИЕ НОВОГО VENV
# ============================================================

echo ""
echo "🐍 Создаем новое виртуальное окружение (${VENV_NAME})..."
cd "$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 не найден!"
    echo "   Установите: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

python3 -m venv "${VENV_NAME}" 2>/dev/null || {
    echo "❌ Ошибка создания ${VENV_NAME}!"
    exit 1
}

sudo chown -R ${OWNER}:${OWNER} "${PROJECT_DIR}/${VENV_NAME}"
sudo chmod -R 755 "${PROJECT_DIR}/${VENV_NAME}"
sudo find "${PROJECT_DIR}/${VENV_NAME}/bin" -type f -exec chmod 755 {} \; 2>/dev/null || true

echo "   ✅ ${VENV_NAME} создан"

# ============================================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================

echo ""
echo "📦 Устанавливаем зависимости..."

install_requirements() {
    local req_file="$1"
    if [ -f "$req_file" ]; then
        echo "   Используем: $req_file"
        source "${VENV_NAME}/bin/activate"
        pip install --upgrade pip -q 2>/dev/null || true
        pip install -r "$req_file" 2>/dev/null || {
            echo "   ⚠️  Ошибка установки некоторых пакетов"
            deactivate 2>/dev/null || true
            return 1
        }
        deactivate 2>/dev/null || true
        return 0
    fi
    return 1
}

if [ -f "$REQUIREMENTS_FILE" ]; then
    install_requirements "$REQUIREMENTS_FILE" || {
        echo "   ⚠️  Пробуем requirements.txt..."
        install_requirements "$PROJECT_DIR/requirements.txt" || {
            echo "   ⚠️  requirements.txt не найден"
        }
    }
elif [ -f "$PROJECT_DIR/requirements.txt" ]; then
    install_requirements "$PROJECT_DIR/requirements.txt" || {
        echo "   ⚠️  Ошибка установки зависимостей"
    }
else
    echo "   ⚠️  Файл с зависимостями не найден!"
fi

# ============================================================
# ВОССТАНОВЛЕНИЕ .env
# ============================================================

if [ -f "$ENV_FILE" ]; then
    echo "🔐 Восстанавливаем .env..."
    cp "$ENV_FILE" "$PROJECT_DIR/.env" 2>/dev/null || true
    sudo chown ${OWNER}:${OWNER} "$PROJECT_DIR/.env" 2>/dev/null || true
fi

# ============================================================
# СОЗДАНИЕ ПАПКИ ЛОГОВ
# ============================================================

mkdir -p "$PROJECT_DIR/logs"
sudo chown -R ${OWNER}:${OWNER} "$PROJECT_DIR/logs"

# ============================================================
# ВОССТАНОВЛЕНИЕ ПРАВ (повторно)
# ============================================================

echo "🔐 Обновляем права..."
sudo chown -R ${OWNER}:${OWNER} "$PROJECT_DIR"
sudo find "$PROJECT_DIR" -type d -exec chmod 755 {} \; 2>/dev/null || true
sudo find "$PROJECT_DIR" -type f -exec chmod 644 {} \; 2>/dev/null || true

if [ -d "$PROJECT_DIR/${VENV_NAME}" ]; then
    sudo chown -R ${OWNER}:${OWNER} "$PROJECT_DIR/${VENV_NAME}"
    sudo chmod -R 755 "$PROJECT_DIR/${VENV_NAME}"
    sudo find "$PROJECT_DIR/${VENV_NAME}/bin" -type f -exec chmod 755 {} \; 2>/dev/null || true
fi

# ============================================================
# ОЧИСТКА КЭША
# ============================================================

echo "🧹 Очищаем кэш Python..."
find "$PROJECT_DIR" -type d -name "__pycache__" -not -path "./${VENV_NAME}/*" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_DIR" -name "*.pyc" -not -path "./${VENV_NAME}/*" -delete 2>/dev/null || true

# ============================================================
# ПРОВЕРКА СТРУКТУРЫ
# ============================================================

echo ""
echo "📁 Проверка структуры проекта:"
ls -la "$PROJECT_DIR" 2>/dev/null | head -15 || echo "   ⚠️  Не удалось прочитать папку"

echo ""
echo "🐍 Проверка Python:"
if [ -f "$PROJECT_DIR/${VENV_NAME}/bin/python" ]; then
    $PROJECT_DIR/${VENV_NAME}/bin/python --version 2>/dev/null || echo "   ⚠️  Не удалось проверить версию"
else
    echo "   ⚠️  ${VENV_NAME}/bin/python не найден"
fi

# ============================================================
# ЗАПУСК СЕРВИСОВ
# ============================================================

echo ""
echo "▶️  Запускаем сервисы..."
for svc in "${ALL_SERVICES[@]}"; do
    if systemctl list-units --full -all 2>/dev/null | grep -q "${svc}.service"; then
        sudo systemctl start "$svc" 2>/dev/null && echo "   ▶️  $svc запущен" || echo "   ⚠️  $svc — ошибка"
    else
        echo "   ⚠️  $svc — не найден в systemd"
    fi
done

sleep 8

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
echo "🌐 Проверка HTTP (порт 8511)..."
sleep 5
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8511/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ HTTP: $HTTP_CODE"
else
    echo "   ⚠️  HTTP: $HTTP_CODE (сервер ещё запускается или ошибка)"
fi

# ============================================================
# РЕЗУЛЬТАТЫ
# ============================================================

echo ""
echo "✅ Восстановление с новым ${VENV_NAME} завершено!"
echo ""
echo "📁 Проект: $PROJECT_DIR"
echo "👤 Владелец: ${OWNER}:${OWNER}"
echo "🐍 venv: ${PROJECT_DIR}/${VENV_NAME}"

if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "📋 Зависимости: $REQUIREMENTS_FILE"
fi

echo ""
echo "🚀 Для ручного запуска:"
echo "   cd $PROJECT_DIR && source ${VENV_NAME}/bin/activate"
echo "   uvicorn sbp:app --host 0.0.0.0 --port 8511"
echo ""
echo "🔧 Для отладки:"
echo "   cd $PROJECT_DIR && ./run_debug.sh"
echo ""
echo "📋 Логи:"
echo "   tail -f $PROJECT_DIR/logs/sbp.log"
echo "   tail -f $PROJECT_DIR/logs/all.log"