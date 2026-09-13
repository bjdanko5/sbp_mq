# modules/common_soap.py
import time
import base64
import requests
from requests.auth import AuthBase
from zeep import Settings, Client
from zeep.cache import InMemoryCache
from zeep.transports import Transport
from requests import Session
from typing import Any, Optional, Tuple, Dict

import config
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response


class UTF8BasicAuth(AuthBase):
    """Basic Auth с поддержкой UTF-8 для username и password."""
    
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __call__(self, r):
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
        r.headers['Authorization'] = f'Basic {encoded}'
        return r


def get_soap_service(
    url: str,
    username: str,
    password: str,
    timeout: int = 60,
    operation_timeout: int = 30
) -> Tuple[Any, Optional[str]]:
    """
    Создаёт и возвращает SOAP-клиент.
    
    Returns:
        Tuple[Client.service, Optional[str]]: (service, error)
    """
    try:
        session = Session()
        session.encoding = "utf-8"  # type: ignore
        session.auth = UTF8BasicAuth(username, password)
        
        settings = Settings(strict=True)  # type: ignore
        cache = InMemoryCache(timeout=timeout)
        transport = Transport(
            session=session,
            timeout=timeout,
            operation_timeout=operation_timeout,
            cache=cache
        )
        
        client = Client(url, settings=settings, transport=transport)
        return client.service, None
        
    except Exception as e:
        log_error_with_context(e, f"get_soap_service url={url}")
        return None, str(e)


def call_soap_method(
    service,
    method_name: str,
    max_retries: int = 3,
    retry_delay: int = 1,
    **kwargs
) -> Tuple[Any, Optional[str]]:
    """
    Вызывает SOAP-метод с повторными попытками при ошибках.
    
    Returns:
        Tuple[Any, Optional[str]]: (response, error)
    """
    attempts = 0
    last_error = None
    
    while attempts < max_retries:
        try:
            method = getattr(service, method_name)
            response = method(**kwargs)
            # ❌ Удалить эту строку (дублируется)
            # logger.debug(f"SOAP {method_name} вызван успешно")
            return response, None
            
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            attempts += 1
            log_error_with_context(
                e,
                f"SOAP {method_name} попытка {attempts}/{max_retries}"
            )
            if attempts < max_retries:
                time.sleep(retry_delay)
                
        except Exception as e:
            last_error = str(e)
            log_error_with_context(e, f"SOAP {method_name} внутренняя ошибка")
            break
    
    error_msg = f"SOAP {method_name} не выполнен после {max_retries} попыток: {last_error}"
    logger.error(error_msg)
    return None, error_msg


def handle_exceptions_soap_base(
    base: str,
    method_name: str,
    context: Optional[str] = None,
    **kwargs
) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Вызывает SOAP-метод для указанной базы.
    
    Args:
        base: Имя базы (подставляется в URL)
        method_name: Имя SOAP-метода
        context: Контекст (имя файла) для логирования ошибок
        **kwargs: Параметры для SOAP-метода
    
    Returns:
        Tuple[Any, Optional[Dict[str, Any]]]:
            - (response, None) при успехе
            - (None, error_response) при ошибке
    """
    url = config.SOAP_CONFIG["base"]["url_template"].format(base=base)
    username = config.SOAP_CONFIG["base"]["username"]
    password = config.SOAP_CONFIG["base"]["password"]
    
    # Получение сервиса
    start = time.time()
    service, error = get_soap_service(url, username, password)
    elapsed = time.time() - start
    # ✅ Добавляем базу в лог
    logger.debug(f"SOAP get_soap_service выполнен за {elapsed:.2f} сек для базы {base}")

    if error:
        logger.error(f"Ошибка получения SOAP-сервиса для базы {base}: {error}")
        return None, create_response(
            status=config.STATUS["API_SOAP_ERROR"],
            error=error,
            context=context,
            data={"base": base, "context": context}
        )
    
    # Вызов метода
    start = time.time()
    response, error = call_soap_method(service, method_name, **kwargs)
    elapsed = time.time() - start
    # ✅ Добавляем базу в лог
    logger.debug(f"SOAP {method_name} выполнен за {elapsed:.2f} сек для базы {base}")

    if error:
        return None, create_response(
            status=config.STATUS["API_SOAP_ERROR"],
            error=error,
            context=context,
            data={"base": base, "context": context}
        )
    
    # ✅ Успешный лог с базой
    #logger.debug(f"SOAP {method_name} вызван успешно для базы {base}")
    
    return response, None