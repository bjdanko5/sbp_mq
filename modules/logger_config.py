# logger_config.py
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import inspect
from typing import List, Optional, Tuple, Union, TypeAlias
from config import DEBUG_VERBOSE


# ============================================================
#                     ОСНОВНОЙ ЛОГГЕР
# ============================================================

def setup_logger():
    """
    Настройка основного логгера.
    
    Пишет в: logs/{LOG_NAME}.log
    Ротация: 1 МБ × 2 файла
    """
    logger = logging.getLogger(__name__)
    if DEBUG_VERBOSE:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    logger.propagate = False
    
    if logger.handlers:
        logger.handlers.clear()
    
    log_name = os.getenv('LOG_NAME', 'sbp')
    log_dir = os.getenv('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{log_name}.log")
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ✅ РОТАЦИЯ: 1 МБ × 2 файла
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,   # 1 МБ
        backupCount=2,          # 2 файла
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


# ============================================================
#                     ЛОГГЕР ОШИБОК
# ============================================================

def setup_error_logger():
    """
    Настройка логгера для ошибок.
    
    Пишет в: logs/{LOG_NAME}_errors.log
    Ротация: 1 МБ × 2 файла
    """
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    error_logger.propagate = False
    
    if error_logger.handlers:
        error_logger.handlers.clear()
    
    log_name = os.getenv('LOG_NAME', 'sbp')
    log_dir = os.getenv('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    error_log_file = os.path.join(log_dir, f"{log_name}_errors.log")
    
    error_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ✅ РОТАЦИЯ: 1 МБ × 2 файла
    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=1024 * 1024,   # 1 МБ
        backupCount=2,          # 2 файла
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(error_formatter)
    error_logger.addHandler(error_file_handler)
    
    if DEBUG_VERBOSE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        error_logger.addHandler(console_handler)
    
    return error_logger


# ============================================================
#                     АГРЕГИРОВАННЫЙ ЛОГГЕР
# ============================================================

def setup_aggregated_logger():
    """
    Настройка агрегированного логгера.
    
    Пишет в: logs/all.log
    Ротация: 1 МБ × 2 файла
    
    Все Worker'ы и сервер пишут СЮДА ключевые события:
    - Старт/стоп Worker'а
    - Взял Job
    - Завершил Job
    - Ошибки
    
    В каждой записи указывается, где смотреть детали.
    """
    agg_logger = logging.getLogger("aggregated")
    agg_logger.setLevel(logging.INFO)
    agg_logger.propagate = False
    
    if agg_logger.handlers:
        agg_logger.handlers.clear()
    
    log_dir = os.getenv('LOG_DIR', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    agg_log_file = os.path.join(log_dir, "all.log")
    
    agg_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # ✅ РОТАЦИЯ: 1 МБ × 2 файла
    agg_handler = RotatingFileHandler(
        agg_log_file,
        maxBytes=1024 * 1024,   # 1 МБ
        backupCount=2,          # 2 файла
        encoding='utf-8'
    )
    agg_handler.setLevel(logging.INFO)
    agg_handler.setFormatter(agg_formatter)
    agg_logger.addHandler(agg_handler)
    
    return agg_logger


# ============================================================
#                     УТИЛИТЫ
# ============================================================

def configure_third_party_loggers():
    """Настройка логгеров сторонних библиотек"""
    for lib in ['zeep', 'httpcore', 'urllib3', 'httpx']:
        lib_logger = logging.getLogger(lib)
        lib_logger.setLevel(logging.WARNING)
        lib_logger.propagate = False


def get_function_names() -> Tuple[Optional[str], Optional[str]]:
    """Возвращает имя функции, вызвавшей эту функцию, и имя её вызывающей функции."""
    frame = inspect.currentframe()
    if frame is None:
        return None, None
    
    outer_frame = frame.f_back
    if outer_frame is None:
        return None, None
    
    current_function_name = outer_frame.f_code.co_name
    
    caller_frame = outer_frame.f_back
    if caller_frame is not None:
        caller_function_name = caller_frame.f_code.co_name
    else:
        caller_function_name = None
    
    return current_function_name, caller_function_name


def get_function_stack(depth: int = 3) -> str:
    """Возвращает стек вызовов в формате func1->func2->func3."""
    stack = inspect.stack()
    result = []
    
    for frame in stack[1:depth+1]:
        func_name = frame.function
        if func_name in ['<module>', 'wrapper', 'decorator']:
            continue
        result.append(func_name)
    
    return "->".join(result) if result else "<unknown>"


def log_error_with_context(error: Exception, context: str = "", logger_instance=None) -> None:
    """Логирует ошибку с полным стеком вызовов."""
    stack = get_function_stack()
    error_type = type(error).__name__
    error_msg = str(error)
    
    log = logger_instance or logger
    
    log.error(f"[{stack}] 🔴 {context} {error_type}: {error_msg}")
    
    error_logger.error(f"=== ERROR IN {stack} ===")
    error_logger.error(f"Context: {context}")
    error_logger.error(f"Exception: {error_type}: {error_msg}")
    error_logger.error("Full traceback:", exc_info=True)
    error_logger.error("=" * 80)


# ============================================================
#                     СОЗДАНИЕ ЭКЗЕМПЛЯРОВ
# ============================================================

logger = setup_logger()
error_logger = setup_error_logger()
aggregated_logger = setup_aggregated_logger()

configure_third_party_loggers()

# ============================================================
#                     ФИЛЬТР ACCESS-ЛОГА UVICORN
# ============================================================

class EndpointFilter(logging.Filter):
    """Отбрасывает записи access-лога uvicorn, содержащие указанные пути."""
    def __init__(self, skip_paths: Tuple[str, ...]):
        super().__init__()
        self.skip_paths = skip_paths

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in self.skip_paths)


def configure_uvicorn_access_filter(
    skip_paths: Tuple[str, ...] = ("/monitor/data", "/monitor/cards")
) -> None:
    """
    Убирает шум из access-лога uvicorn для указанных путей.

    Пример:
        configure_uvicorn_access_filter(("/monitor/data", "/monitor/cards"))
    """
    access_logger = logging.getLogger("uvicorn.access")
    # Убираем ранее добавленные фильтры этого типа, чтобы не дублировать
    access_logger.filters = [
        f for f in access_logger.filters if not isinstance(f, EndpointFilter)
    ]
    access_logger.addFilter(EndpointFilter(skip_paths))

__all__ = [
    'logger',
    'error_logger',
    'aggregated_logger',
    'setup_logger',
    'setup_error_logger',
    'setup_aggregated_logger',
    'get_function_names',
    'get_function_stack',
    'log_error_with_context',
    'configure_third_party_loggers',
    'EndpointFilter',
    'configure_uvicorn_access_filter',
]