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

os.environ.setdefault('PYTHONUNBUFFERED', '1')
os.environ.setdefault('PYDEVD_USE_FRAME_EVAL', 'NO')


# ============================================================
#                     УТИЛИТЫ ДЛЯ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================================

def parse_bool_env(var_name: str, default: bool = False) -> bool:
    """
    Безопасный парсинг булевых переменных окружения.
    
    Поддерживает:
    - true, True, TRUE, 1, yes, on → True
    - false, False, FALSE, 0, no, off → False
    
    Args:
        var_name: Имя переменной
        default: Значение по умолчанию
    
    Returns:
        bool: Распарсенное значение
    """
    value = os.getenv(var_name)
    if value is None:
        return default
    
    value_lower = value.lower().strip()
    
    # True значения
    if value_lower in ('true', '1', 'yes', 'on', 'y', 't'):
        return True
    
    # False значения
    if value_lower in ('false', '0', 'no', 'off', 'n', 'f'):
        return False
    
    # Если значение не распознано, возвращаем default
    return default


def parse_int_env(var_name: str, default: int) -> int:
    """Парсит целочисленную переменную окружения."""
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_float_env(var_name: str, default: float) -> float:
    """Парсит дробную переменную окружения."""
    value = os.getenv(var_name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_str_env(var_name: str, default: str) -> str:
    """Парсит строковую переменную окружения."""
    return os.getenv(var_name, default)


# ============================================================
#                     ПУТИ
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
#                     НАСТРОЙКИ ПОРТА
# ============================================================

SBP_MQ_PORT = parse_int_env('SBP_MQ_PORT', 8511)
SBP_MQ_DEBUG_PORT = parse_int_env('SBP_MQ_DEBUG_PORT', 5679)

# Путь к БД
DB_FILE = os.path.join(BASE_DIR, "requests.db")

# Корневой путь для всей SBP системы
SBP_ROOT4MQ = "/sbp/mq"

# Путь для Job-файлов
SBP_ROOT4JOBS = os.path.join(SBP_ROOT4MQ, "jobs")

# ✅ Пути для логов и данных (из .env, fallback на BASE_DIR)
LOG_DIR = parse_str_env('LOG_DIR', os.path.join(BASE_DIR, "logs"))
DATA_DIR = parse_str_env('DATA_DIR', os.path.join(BASE_DIR, "data"))

# ============================================================
#                     ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР SBP_ROOT
# ============================================================

# ✅ Создаём глобальный экземпляр из модуля sbp_root
SBP_ROOT = create_sbp_root(SBP_ROOT4MQ, default_bank="ci")

# Для обратной совместимости — строка-представление
SBP_ROOT_STR = str(SBP_ROOT)


# ============================================================
#                     API НАСТРОЙКИ
# ============================================================

# ⚠️ ВНИМАНИЕ: 
# - Для разработки: export TEST_MODE=true
# - Для продакшена: export TEST_MODE=false или не устанавливать (по умолчанию false)
TEST_MODE = parse_bool_env('TEST_MODE', default=True)

# Базовые URL для банков
BANK_URLS = {
    "ci": "https://10.0.245.20:443/ivolga-api/qr-code" if not TEST_MODE else f"http://localhost:{SBP_MQ_PORT}/mockapi/qr-code",
    "sb": "https://sb.api.sberbank.ru/...",   # TODO: уточнить
    "vtb": "https://api.vtb.ru/..."           # TODO: уточнить
}

# Callback URL для банков
CALLBACK_URLS = {
    "ci": "/callback",
    "sb": "/callback_sb",
    "vtb": "/callback_vtb"
}

DEBUG_VERBOSE = parse_bool_env('DEBUG_VERBOSE', default=True)
REQUEST_TIMEOUT = parse_float_env('REQUEST_TIMEOUT', 30.0)
DELAY_BETWEEN_REQUESTS = parse_int_env('DELAY_BETWEEN_REQUESTS', 1)
VERIFY_SSL = parse_bool_env('VERIFY_SSL', default=False)
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

SOAP_TIMEOUT = parse_float_env('SOAP_TIMEOUT', 60)
SOAP_OPERATION_TIMEOUT = parse_float_env('SOAP_OPERATION_TIMEOUT', 30)
SOAP_MAX_RETRIES = parse_int_env('SOAP_MAX_RETRIES', 3)
SOAP_RETRY_DELAY = parse_float_env('SOAP_RETRY_DELAY', 1)


# ============================================================
#                     НАСТРОЙКИ MQ
# ============================================================

RABBITMQ_HOST = parse_str_env('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = parse_int_env('RABBITMQ_PORT', 5672)
RABBITMQ_USER = parse_str_env('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = parse_str_env('RABBITMQ_PASSWORD', 'guest')
RABBITMQ_QUEUE = parse_str_env('RABBITMQ_QUEUE', 'sbp_mq_queue')

# ============================================================
#                     НАСТРОЙКИ REDIS
# ============================================================

REDIS_HOST = parse_str_env('REDIS_HOST', 'localhost')
REDIS_PORT = parse_int_env('REDIS_PORT', 6379)
REDIS_DB = parse_int_env('REDIS_DB', 0)
REDIS_TTL = parse_int_env('REDIS_TTL', 3600)
# ============================================================
#                     REQUEST STORAGE
# ============================================================

# TTL для связки requestID → task_id (в секундах)
# Callback обычно приходит в течение 1-5 минут
# 1 час — с запасом
REQUEST_TTL = parse_int_env('REQUEST_TTL', 3600)

# ============================================================
#                     НАСТРОЙКИ СТАТИСТИКИ
# ============================================================

STATS_LOG_FILE = "sbp.log"


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