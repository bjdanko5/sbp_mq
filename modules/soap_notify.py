# modules/soap_notify.py
"""
SOAP-уведомления 1С об ошибке Job.

Особенности:
- Вызывается worker'ом ТОЛЬКО при ошибке Job.
- Метод ProcessPayload (тот же, что для callback).
- Формат: JSON внутри Payload.
- Структура: jobId + bank + base + errorMessage + jobName.
- 1С различает: jobId → Job Error; requestId → Callback.

Пример payload:
    [
      {
        "jobId": "123",
        "bank": "ci",
        "base": "zkh_ursv",
        "errorMessage": "VPN timeout | 7845.json: API 500",
        "jobName": "Печать квитанций"
      }
    ]
"""

import asyncio
import json
from typing import Optional, Dict, Any

import config
from modules.logger_config import logger
from modules import common_soap
from modules.response_utils import create_response


# ============================================================
#                   НАСТРОЙКИ
# ============================================================

MAX_ERROR_LENGTH = 500
ERROR_SEPARATOR = " | "
FALLBACK_ERROR = "Job failed"


# ============================================================
#                   СБОР ОШИБОК
# ============================================================

def _collect_errors(result: Dict[str, Any]) -> str:
    """
    Собирает ошибки из результата Job.
    
    Логика (вариант C):
    1. Общая ошибка Job (result["error"]) — если есть
    2. Ошибки файлов (files[].error) — с именем файла
    3. Фоллбэк "Job failed" — если ничего нет
    """
    errors = []
    
    # 1. Общая ошибка Job
    general_error = result.get("error")
    if general_error:
        errors.append(str(general_error))
    
    # 2. Ошибки файлов
    for file_info in result.get("files", []):
        file_error = file_info.get("error")
        if file_error:
            filename = file_info.get("filename", "unknown")
            errors.append(f"{filename}: {file_error}")
    
    # 3. Фоллбэк
    if not errors:
        return FALLBACK_ERROR
    
    text = ERROR_SEPARATOR.join(errors)
    
    if len(text) > MAX_ERROR_LENGTH:
        text = text[:MAX_ERROR_LENGTH - 3] + "..."
    
    return text


# ============================================================
#                   ОТПРАВКА УВЕДОМЛЕНИЯ
# ============================================================

async def notify_job_error(
    bank: str,
    base: str,
    job_id: int,
    result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Отправить SOAP-уведомление 1С об ошибке Job.
    
    Args:
        bank: Имя банка (ci, sb, vtb)
        base: Имя базы (zkh_ursv)
        job_id: ID Job
        result: Результат обработки Job (из job_processor)
    
    Returns:
        Optional[Dict]: Ответ 1С или error_response
    """
    error_text = _collect_errors(result)
    job_name = result.get("job_name", "")
    
    payload_item = {
        "jobId": str(job_id),
        "bank": bank,
        "base": base,
        "errorMessage": error_text,
    }
    
    if job_name:
        payload_item["jobName"] = job_name
    
    payload_json = json.dumps([payload_item], ensure_ascii=False)
    context = f"job_error_{bank}@{base}@{job_id}"
    
    logger.info(
        f"[SOAP Notify] Отправка уведомления об ошибке: "
        f"{bank}@{base}@{job_id} — {error_text[:100]}"
    )
    
    try:
        response, soap_error = await asyncio.to_thread(
            common_soap.handle_exceptions_soap_base,
            base,
            "ProcessPayload",
            context,
            Payload=payload_json,
        )
        
        if soap_error:
            logger.error(
                f"[SOAP Notify] ❌ Ошибка уведомления {context}: "
                f"{soap_error.get('error', 'unknown')}"
            )
            return soap_error
        
        # Логируем ответ 1С
        if response is not None:
            try:
                response_str = str(response)
                if len(response_str) > 500:
                    response_str = response_str[:497] + "..."
                logger.info(f"[SOAP Notify] Ответ 1С: {response_str}")
            except Exception:
                pass
        
        logger.info(f"[SOAP Notify] ✅ Уведомление {context} отправлено")
        return response
        
    except Exception as e:
        logger.error(
            f"[SOAP Notify] ❌ Критическая ошибка {context}: {e}",
            exc_info=True,
        )
        return create_response(
            status=config.STATUS["SOAP_ERROR"],
            error=str(e),
            context=context,
        )
