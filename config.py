# config.py
import os
from pathlib import Path
from typing import Dict, Optional, Union, Any

# ============================================================
#                   ИМПОРТ SBPRoot ИЗ МОДУЛЯ
# ============================================================

from modules.sbp_root import SBPRoot, SBPPath, create_sbp_root


# ============================================================
#                   ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ============================================================
# Философия: .env — единственный источник правды.
# Все переменные обязательны. Нет переменной → падаем.
# Переменные приходят из:
#   - systemd EnvironmentFile=/path/.env (для сервисов)
#   - source .env (в run_debug.sh)
#   - dotenv в conftest.py (для тестов)
# ============================================================

# ============================================================
#          УТИЛИТЫ ДЛЯ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ (обязательные)
# ============================================================

def _require_env(var_name: str) -> str:
    """
    Возвращает переменную окружения или падает с понятной ошибкой.

    Философия: .env — единственный источник правды.
    Не должно быть тихих дефолтов, которые маскируют ошибки конфигурации.
    """
    value = os.getenv(var_name)
    if value is None or value.strip() == '':
        raise ValueError(
            f"❌ Переменная окружения '{var_name}' не задана. "
            f"Проверь .env — он должен загружаться через "
            f"systemd EnvironmentFile или run_debug.sh (source .env)."
        )
    return value.strip()


def parse_bool_env(var_name: str) -> bool:
    """
    Парсит обязательную булеву переменную окружения.

    Поддерживает:
    - true, True, TRUE, 1, yes, on, y, t → True
    - false, False, FALSE, 0, no, off, n, f → False
    """
    value = _require_env(var_name).lower()
    if value in ('true', '1', 'yes', 'on', 'y', 't'):
        return True
    if value in ('false', '0', 'no', 'off', 'n', 'f'):
        return False
    raise ValueError(
        f"❌ {var_name}='{value}' не распознано как bool. "
        f"Ожидается: true/false, 1/0, yes/no, on/off"
    )


def parse_int_env(var_name: str) -> int:
    """Парсит обязательную целочисленную переменную окружения."""
    value = _require_env(var_name)
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"❌ {var_name}='{value}' не является целым числом")


def parse_float_env(var_name: str) -> float:
    """Парсит обязательную дробную переменную окружения."""
    value = _require_env(var_name)
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"❌ {var_name}='{value}' не является числом")


def parse_str_env(var_name: str) -> str:
    """Парсит обязательную строковую переменную окружения."""
    return _require_env(var_name)


# ============================================================
#                     ПУТИ
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
#                     ОПРЕДЕЛЕНИЕ ОКРУЖЕНИЯ
# ============================================================
# Определяем режим по имени папки:
#   - sbp_mq_dev → DEV
#   - sbp_mq     → PROD
#
# Используется в:
#   - sbp.py             (лог о воркерах)
#   - routes/health.py   (проверка активных воркеров)

PROJECT_NAME = os.path.basename(BASE_DIR)
IS_DEV = "_dev" in PROJECT_NAME
IS_PROD = not IS_DEV

# Префикс для systemd-сервисов
SERVICE_PREFIX = "sbp_mq-dev" if IS_DEV else "sbp_mq"

# Паттерн для воркеров (для grep systemctl)
WORKER_PATTERN = f"{SERVICE_PREFIX}-worker"

# Полное имя серверного сервиса
SERVER_SERVICE = f"{SERVICE_PREFIX}.service"


# ============================================================
#                     НАСТРОЙКИ ПОРТА
# ============================================================

SBP_MQ_PORT = parse_int_env('SBP_MQ_PORT')
SBP_MQ_DEBUG_PORT = parse_int_env('SBP_MQ_DEBUG_PORT')

# Путь к БД
DB_FILE = os.path.join(BASE_DIR, "requests.db")

# Корневой путь для всей SBP системы
SBP_ROOT4MQ = parse_str_env('SBP_ROOT4MQ')

# Путь для Job-файлов
SBP_ROOT4JOBS = os.path.join(SBP_ROOT4MQ, "jobs")

# Пути для логов и данных (обязательны в .env)
LOG_DIR = parse_str_env('LOG_DIR')
DATA_DIR = parse_str_env('DATA_DIR')


# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР SBP_ROOT
# ============================================================

# Создаём глобальный экземпляр из модуля sbp_root
SBP_ROOT = create_sbp_root(SBP_ROOT4MQ, default_bank="ci")

# Для обратной совместимости — строка-представление
SBP_ROOT_STR = str(SBP_ROOT)


# ============================================================
#                     API НАСТРОЙКИ
# ============================================================

TEST_MODE = parse_bool_env('TEST_MODE')

# Базовые URL для банков
BANK_URLS = {
    "ci": (
        f"http://localhost:{SBP_MQ_PORT}/mockapi/qr-code"
        if TEST_MODE
        else "https://10.0.245.20:443/ivolga-api/qr-code"
    ),
    "sb": "https://sb.api.sberbank.ru/...",   # TODO: уточнить
    "vtb": "https://api.vtb.ru/..."           # TODO: уточнить
}

# Callback URL для банков
CALLBACK_URLS = {
    "ci": "/callback",
    "sb": "/callback_sb",
    "vtb": "/callback_vtb"
}

DEBUG_VERBOSE = parse_bool_env('DEBUG_VERBOSE')
REQUEST_TIMEOUT = parse_float_env('REQUEST_TIMEOUT')
DELAY_BETWEEN_REQUESTS = parse_int_env('DELAY_BETWEEN_REQUESTS')
VERIFY_SSL = parse_bool_env('VERIFY_SSL')
DEFAULT_HEADERS = {"Content-Type": "application/json"}


# ============================================================
#                     НАСТРОЙКИ БАНКОВ
# ============================================================

BANK_CONFIG = {
    "ci": {
        "name": "Центринвест",
        "url": BANK_URLS["ci"],
        "sbp_root": SBP_ROOT["ci"],
        "callback_url": CALLBACK_URLS["ci"],
        "verify_ssl": False,
        "api_class": "BankCI"
    },
    "sb": {
        "name": "Сбербанк",
        "url": BANK_URLS["sb"],
        "sbp_root": SBP_ROOT["sb"],
        "callback_url": CALLBACK_URLS["sb"],
        "verify_ssl": True,
        "api_class": "BankSB"
    },
    "vtb": {
        "name": "ВТБ",
        "url": BANK_URLS["vtb"],
        "sbp_root": SBP_ROOT["vtb"],
        "callback_url": CALLBACK_URLS["vtb"],
        "verify_ssl": True,
        "api_class": "BankVTB"
    }
}


# ============================================================
#                     НАСТРОЙКИ SOAP
# ============================================================

SOAP_CONFIG = {
    "default": {
        "url": "http://192.168.10.128/zkh_lk1/ws/WebLK?wsdl",
        "username": "Администратор",
        "password": ""
    },
    "base": {
        "url_template": "http://192.168.10.238/{base}/ws/WebLK?wsdl",
        "username": "Администратор",
        "password": "71243339"
    }
}

SOAP_TIMEOUT = parse_float_env('SOAP_TIMEOUT')
SOAP_OPERATION_TIMEOUT = parse_float_env('SOAP_OPERATION_TIMEOUT')
SOAP_MAX_RETRIES = parse_int_env('SOAP_MAX_RETRIES')
SOAP_RETRY_DELAY = parse_float_env('SOAP_RETRY_DELAY')


# ============================================================
#                     НАСТРОЙКИ MQ
# ============================================================

RABBITMQ_HOST = parse_str_env('RABBITMQ_HOST')
RABBITMQ_PORT = parse_int_env('RABBITMQ_PORT')
RABBITMQ_USER = parse_str_env('RABBITMQ_USER')
RABBITMQ_PASSWORD = parse_str_env('RABBITMQ_PASSWORD')
RABBITMQ_QUEUE = parse_str_env('RABBITMQ_QUEUE')


# ============================================================
#                     НАСТРОЙКИ REDIS
# ============================================================

REDIS_HOST = parse_str_env('REDIS_HOST')
REDIS_PORT = parse_int_env('REDIS_PORT')
REDIS_DB = parse_int_env('REDIS_DB')
REDIS_TTL = parse_int_env('REDIS_TTL')


# ============================================================
#                     REQUEST STORAGE
# ============================================================

# TTL для связки requestID → task_id (в секундах)
# Callback обычно приходит в течение 1-5 минут
# 1 час — с запасом
REQUEST_TTL = parse_int_env('REQUEST_TTL')


# ============================================================
#                     СТАТУСЫ
# ============================================================

STATUS = {
    "SUCCESS": "SUCCESS",
    "NO_FILES": "NO_FILES",
    "FILE_ERROR": "FILE_ERROR",
    "FILE_MOVE_TO_PROCESSING_ERROR": "FILE_MOVE_TO_PROCESSING_ERROR",
    "FILE_MOVE_TO_SENDED_ERROR": "FILE_MOVE_TO_SENDED_ERROR",
    "FILE_MOVE_TO_GETED_ERROR": "FILE_MOVE_TO_GETED_ERROR",
    "FILE_MOVE_TO_STOPED_ERROR": "FILE_MOVE_TO_STOPED_ERROR",
    "DIRECTORY_ERROR": "DIRECTORY_ERROR",
    "FILE_NOT_FOUND": "FILE_NOT_FOUND",
    "JSON_ERROR": "JSON_ERROR",
    "JSON_READ_ERROR": "JSON_READ_ERROR",
    "JSON_EMPTY": "JSON_EMPTY",
    "DB_ERROR": "DB_ERROR",
    "DB_SAVE_ERROR": "DB_SAVE_ERROR",
    "DB_CLEAR_ERROR": "DB_CLEAR_ERROR",
    "API_ERROR": "API_ERROR",
    "API_SOAP_ERROR": "API_SOAP_ERROR",
    "API_TIMEOUT": "API_TIMEOUT",
    "API_CONNECTION_ERROR": "API_CONNECTION_ERROR",
    "API_OK_FILE_ERROR": "API_OK_FILE_ERROR",
    "PARTIAL_SUCCESS": "PARTIAL_SUCCESS",
    "SOAP_ERROR": "SOAP_ERROR",
    "SOAP_CONNECTION_ERROR": "SOAP_CONNECTION_ERROR",
    "SOAP_AUTH_ERROR": "SOAP_AUTH_ERROR",
    "UNKNOWN_ERROR": "UNKNOWN_ERROR",
    "VALIDATION_ERROR": "VALIDATION_ERROR",
    "CONFIG_ERROR": "CONFIG_ERROR",
    "JOB_ALREADY_PROCESSING": "JOB_ALREADY_PROCESSING",
    "JOB_ALREADY_COMPLETED": "JOB_ALREADY_COMPLETED",
    "JOB_NOT_FOUND": "JOB_NOT_FOUND"
}


# ============================================================
#                     ГРУППЫ СТАТУСОВ
# ============================================================

STATUS_GROUPS = {
    "SUCCESS": [
        STATUS["SUCCESS"],
        STATUS["NO_FILES"],
        STATUS["PARTIAL_SUCCESS"],
    ],
    "ERROR": [
        STATUS["FILE_ERROR"],
        STATUS["FILE_MOVE_TO_PROCESSING_ERROR"],
        STATUS["FILE_MOVE_TO_SENDED_ERROR"],
        STATUS["FILE_MOVE_TO_GETED_ERROR"],
        STATUS["FILE_MOVE_TO_STOPED_ERROR"],
        STATUS["DIRECTORY_ERROR"],
        STATUS["FILE_NOT_FOUND"],
        STATUS["JSON_ERROR"],
        STATUS["JSON_READ_ERROR"],
        STATUS["JSON_EMPTY"],
        STATUS["DB_ERROR"],
        STATUS["DB_SAVE_ERROR"],
        STATUS["DB_CLEAR_ERROR"],
        STATUS["API_ERROR"],
        STATUS["API_SOAP_ERROR"],
        STATUS["API_TIMEOUT"],
        STATUS["API_CONNECTION_ERROR"],
        STATUS["SOAP_ERROR"],
        STATUS["SOAP_CONNECTION_ERROR"],
        STATUS["SOAP_AUTH_ERROR"],
        STATUS["UNKNOWN_ERROR"],
        STATUS["VALIDATION_ERROR"],
        STATUS["CONFIG_ERROR"],
        STATUS["JOB_ALREADY_PROCESSING"],
        STATUS["JOB_ALREADY_COMPLETED"],
        STATUS["JOB_NOT_FOUND"],
    ],
    "WARNING": [
        STATUS["API_OK_FILE_ERROR"],
    ]
}


# ============================================================
#                     ФУНКЦИИ ДЛЯ РАБОТЫ СО СТАТУСАМИ
# ============================================================

def is_success(status: str) -> bool:
    """Проверяет, является ли статус успешным."""
    return status in STATUS_GROUPS.get("SUCCESS", [])


def is_error(status: str) -> bool:
    """Проверяет, является ли статус ошибкой."""
    return status in STATUS_GROUPS.get("ERROR", [])


def is_warning(status: str) -> bool:
    """Проверяет, является ли статус предупреждением."""
    return status in STATUS_GROUPS.get("WARNING", [])


def get_status_group(status: str) -> str:
    """Возвращает группу статуса."""
    if is_success(status):
        return "SUCCESS"
    if is_error(status):
        return "ERROR"
    if is_warning(status):
        return "WARNING"
    return "UNKNOWN"


def get_response_status(status: str) -> str:
    """Возвращает статус для HTTP ответа."""
    if is_success(status):
        return "SUCCESS"
    if is_error(status):
        return "ERROR"
    if is_warning(status):
        return "WARNING"
    return "UNKNOWN"