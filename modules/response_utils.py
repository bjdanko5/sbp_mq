# modules/response_utils.py
from typing import Any, Dict, Optional, Union
from config import STATUS, get_status_group
from modules.logger_config import logger, log_error_with_context


def create_response(
    status: str,
    base: Optional[str] = None,
    message: Optional[Union[str, Dict[str, Any]]] = None,
    error: Optional[Union[str, Dict[str, Any]]] = None,
    data: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None,
    include_response: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Универсальная функция для создания ответов API с автоматическим логированием.
    """
    group = get_status_group(status)
    
    response: Dict[str, Any] = {"status": group, "code": status}
    
    if base is not None:
        response["base"] = base
    
    # Обработка error
    error_text: Optional[str] = None
    error_data: Optional[Dict[str, Any]] = None
    
    if isinstance(error, dict):
        error_text = error.get("error") or error.get("message") or "Произошла ошибка"
        error_data = {k: v for k, v in error.items() if k not in ["error", "message"]}
    elif isinstance(error, str):
        error_text = error
    
    if error_text is not None:
        response["error"] = error_text
    elif group == "ERROR":
        response["error"] = _get_error_message(status, context)
    
    if error_data:
        if data is None:
            data = {}
        data.update(error_data)
    
    # Обработка message
    message_text: Optional[str] = None
    
    if isinstance(message, dict):
        message_text = message.get("message") or message.get("text") or None
    elif isinstance(message, str):
        message_text = message
    
    if message_text is not None:
        response["message"] = message_text
    elif group == "SUCCESS":
        response["message"] = _get_success_message(status, context)
    elif group == "WARNING":
        response["message"] = _get_warning_message(status, context)
    elif group == "UNKNOWN":
        response["message"] = "Неизвестный статус"

    if data is not None:
        # Для успешных ответов убираем response, если явно не указано include_response
        if group == "SUCCESS" and not include_response:
            data = {k: v for k, v in data.items() if k != "response"}
        response["data"] = data
    
    for key, value in kwargs.items():
        if value is not None:
            response[key] = value
    
    # ============================================================
    #                   АВТОМАТИЧЕСКОЕ ЛОГИРОВАНИЕ
    # ============================================================
    
    log_msg = f"[{status}]"
    if base:
        log_msg += f" base={base}"
    if context:
        log_msg += f" context={context}"
    if error_text:
        log_msg += f" error={error_text}"
    
    # Добавляем статистику из data
    if data and isinstance(data, dict):
        total = data.get("total")
        success = data.get("success")
        errors = data.get("errors")
        if total is not None and success is not None and errors is not None:
            log_msg += f" total={total} success={success} errors={errors}"
    
    if group == "ERROR":
        logger.error(log_msg)
    elif group == "WARNING":
        logger.warning(log_msg)
    else:
        logger.debug(log_msg)
    
    return response


# ============================================================
#                     УДОБНЫЕ ОБЁРТКИ
# ============================================================

def create_success_response(
    status: str = STATUS["SUCCESS"],
    base: Optional[str] = None,
    message: Optional[Union[str, Dict[str, Any]]] = None,
    data: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Создаёт успешный ответ."""
    return create_response(
        status=status,
        base=base,
        message=message,
        data=data,
        context=context,
        **kwargs
    )


def create_error_response(
    status: str,
    base: Optional[str] = None,
    error: Optional[Union[str, Dict[str, Any]]] = None,
    data: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Создаёт ответ с ошибкой."""
    return create_response(
        status=status,
        base=base,
        error=error,
        data=data,
        context=context,
        **kwargs
    )


def create_warning_response(
    status: str,
    base: Optional[str] = None,
    message: Optional[Union[str, Dict[str, Any]]] = None,
    data: Optional[Dict[str, Any]] = None,
    context: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """Создаёт ответ с предупреждением."""
    return create_response(
        status=status,
        base=base,
        message=message,
        data=data,
        context=context,
        **kwargs
    )


# ============================================================
#                     СООБЩЕНИЯ ПО УМОЛЧАНИЮ
# ============================================================

def _get_success_message(status: str, context: Optional[str] = None) -> str:
    """Возвращает сообщение для успешного статуса."""
    messages = {
        STATUS["SUCCESS"]: f"Операция выполнена успешно{f': {context}' if context else ''}",
        STATUS["NO_FILES"]: f"Нет файлов для обработки{f': {context}' if context else ''}",
        STATUS["PARTIAL_SUCCESS"]: f"Операция выполнена частично{f': {context}' if context else ''}",
    }
    return messages.get(status, f"Операция выполнена{f': {context}' if context else ''}")


def _get_error_message(status: str, context: Optional[str] = None) -> str:
    """Возвращает сообщение для статуса ошибки с контекстом."""
    messages = {
        STATUS["DIRECTORY_ERROR"]: f"Ошибка доступа к директории{f': {context}' if context else ''}",
        STATUS["FILE_ERROR"]: f"Ошибка работы с файлом{f': {context}' if context else ''}",
        STATUS["FILE_MOVE_TO_PROCESSING_ERROR"]: f"Ошибка перемещения файла в processing{f': {context}' if context else ''}",
        STATUS["FILE_MOVE_TO_SENDED_ERROR"]: f"Ошибка перемещения файла в sended{f': {context}' if context else ''}",
        STATUS["FILE_MOVE_TO_GETED_ERROR"]: f"Ошибка перемещения файла в geted{f': {context}' if context else ''}",
        STATUS["FILE_MOVE_TO_STOPED_ERROR"]: f"Ошибка перемещения файла в stoped{f': {context}' if context else ''}",
        STATUS["FILE_NOT_FOUND"]: f"Файл не найден{f': {context}' if context else ''}",
        STATUS["JSON_ERROR"]: f"Ошибка JSON{f': {context}' if context else ''}",
        STATUS["JSON_READ_ERROR"]: f"Ошибка чтения JSON{f': {context}' if context else ''}",
        STATUS["JSON_EMPTY"]: f"Пустой JSON{f': {context}' if context else ''}",
        STATUS["DB_ERROR"]: f"Ошибка базы данных{f': {context}' if context else ''}",
        STATUS["DB_SAVE_ERROR"]: f"Ошибка сохранения в БД{f': {context}' if context else ''}",
        STATUS["DB_CLEAR_ERROR"]: f"Ошибка очистки БД{f': {context}' if context else ''}",
        STATUS["API_ERROR"]: f"Ошибка API запроса{f': {context}' if context else ''}",
        STATUS["API_SOAP_ERROR"]: f"Ошибка SOAP запроса{f': {context}' if context else ''}",
        STATUS["API_TIMEOUT"]: f"Превышено время ожидания API{f': {context}' if context else ''}",
        STATUS["API_CONNECTION_ERROR"]: f"Ошибка подключения к API{f': {context}' if context else ''}",
        STATUS["SOAP_ERROR"]: f"Ошибка SOAP{f': {context}' if context else ''}",
        STATUS["SOAP_CONNECTION_ERROR"]: f"Ошибка подключения к SOAP{f': {context}' if context else ''}",
        STATUS["SOAP_AUTH_ERROR"]: f"Ошибка аутентификации SOAP{f': {context}' if context else ''}",
        STATUS["VALIDATION_ERROR"]: f"Ошибка валидации{f': {context}' if context else ''}",
        STATUS["CONFIG_ERROR"]: f"Ошибка конфигурации{f': {context}' if context else ''}",
        STATUS["UNKNOWN_ERROR"]: f"Неизвестная ошибка{f': {context}' if context else ''}",
    }
    return messages.get(status, f"Произошла ошибка{f': {context}' if context else ''}")


def _get_warning_message(status: str, context: Optional[str] = None) -> str:
    """Возвращает сообщение для статуса предупреждения."""
    messages = {
        STATUS["API_OK_FILE_ERROR"]: f"API ответил успешно, но файл не был обработан{f': {context}' if context else ''}",
    }
    return messages.get(status, f"Операция выполнена с предупреждением{f': {context}' if context else ''}")