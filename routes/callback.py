# routes/callback.py
import json
from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, List

import config
from modules import db, common_soap
from modules.request_storage import request_storage
from modules.mq_client import mq_client
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from models.schemas import PayloadItem

router = APIRouter()


# ============================================================
#            ПОИСК BASE ПО REQUESTID (Redis + fallback SQLite)
# ============================================================

async def resolve_bases_for_requests(
    request_ids: List[str]
) -> Dict[str, Optional[str]]:
    """
    Находит base для каждого requestID.
    
    Логика:
    1. Пробуем Redis: req:{requestID} → task_id → task:{task_id} → base
    2. Fallback: SQLite (db.get_bases_for_requests)
    
    Args:
        request_ids: Список requestID
    
    Returns:
        Dict[str, Optional[str]]: {requestID: base или None}
    """
    stack = get_function_stack()
    result: Dict[str, Optional[str]] = {rid: None for rid in request_ids}
    
    # === Шаг 1: Redis ===
    task_ids = await request_storage.get_task_ids_for_requests(request_ids)
    
    # Собираем уникальные task_id
    unique_task_ids = set(tid for tid in task_ids.values() if tid)
    
    # Читаем task:{task_id} для каждого уникального task_id
    task_to_base: Dict[str, Optional[str]] = {}
    for tid in unique_task_ids:
        task_data = await mq_client.get_result(tid)
        if task_data:
            task_to_base[tid] = task_data.get('base')
    
    # Проставляем base из Redis
    for rid, tid in task_ids.items():
        if tid and tid in task_to_base:
            result[rid] = task_to_base[tid]
    
    # === Шаг 2: Fallback — SQLite ===
    not_found = [rid for rid, base in result.items() if not base]
    
    if not_found:
        logger.debug(
            f"[{stack}] Redis не нашёл base для {len(not_found)} requestID, "
            f"пробуем SQLite: {not_found[:10]}..."
        )
        
        # ✅ Используем существующий db.get_bases_for_requests (batch)
        db_bases, db_error = db.get_bases_for_requests(not_found)
        
        if db_error:
            log_error_with_context(
                Exception(str(db_error)),
                f"callback fallback get_bases_for_requests"
            )
        else:
            for rid, base in db_bases.items():
                if base:
                    result[rid] = base
                    logger.debug(
                        f"[{stack}] Fallback SQLite: {rid} → {base}"
                    )
    
    # === Итог ===
    found = sum(1 for b in result.values() if b)
    logger.debug(
        f"[{stack}] Найдено base: {found}/{len(request_ids)} "
        f"(Redis + SQLite)"
    )
    
    return result


# ============================================================
#                     CALLBACK ENDPOINT
# ============================================================

@router.post("/callback")
async def handle_callback(payload: list[PayloadItem] = Body(..., max_length=10000)):
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Получен callback с {len(payload)} запросами")
        
        # ✅ Логируем requestID
        request_ids = [item.requestId for item in payload]
        logger.debug(f"[{stack}] Payload requestIds: {request_ids}")
        
        if config.DEBUG_VERBOSE:
            payload_json = json.dumps(
                [item.model_dump() for item in payload],
                ensure_ascii=False
            )
            logger.debug(f"[{stack}] Payload (full): {payload_json}")
        
        # === Резолвим base для каждого requestID ===
        request_to_base = await resolve_bases_for_requests(request_ids)
        
        # === Группируем по базам ===
        base_to_payload: Dict[str, List[dict]] = {}
        not_found_ids: List[str] = []
        
        for item in payload:
            base = request_to_base.get(item.requestId)
            if base:
                base_to_payload.setdefault(base, []).append(item.model_dump())
            else:
                not_found_ids.append(item.requestId)
        
        if not base_to_payload:
            logger.warning(
                f"[{stack}] Не найдена база ни для одного requestId. "
                f"Не найдено: {not_found_ids}"
            )
            return {
                "status": "success",
                "detail": "Не найдена база для ни одного requestId из payload.",
                "not_found_ids": not_found_ids
            }
        
        # === Обрабатываем по базам ===
        responses = {}
        for base, items in base_to_payload.items():
            logger.debug(f"[{stack}] Обработка базы {base}: {len(items)} запросов")
            
            if not items:
                responses[base] = {"status": "skipped", "message": "Нет запросов"}
                continue
            
            # ✅ Логируем данные перед отправкой в SOAP
            soap_payload = json.dumps(items, ensure_ascii=False)
            logger.debug(f"[{stack}] Отправка в SOAP (база {base}): {soap_payload}")
            
            # Отправка в SOAP
            soap_response, soap_error = common_soap.handle_exceptions_soap_base(
                base,
                "ProcessPayload",
                context=base,
                Payload=soap_payload
            )
            
            if soap_error:
                responses[base] = {
                    "status": "error",
                    "error": soap_error.get("error", "SOAP ошибка"),
                    "base": base
                }
                continue
            
            if not soap_response:
                responses[base] = {
                    "status": "warning",
                    "message": "SOAP вернул пустой ответ",
                    "response": soap_response
                }
            else:
                responses[base] = {"status": "success", "response": soap_response}
            
            # === Удаляем requestID ===
            items_request_ids = [item['requestId'] for item in items]
            
            # Из Redis
            deleted_redis = await request_storage.delete_requests(items_request_ids)
            
            # Из SQLite (fallback — на случай, если там что-то осталось)
            deleted_db, delete_error = db.clear_multiple_db(items_request_ids)
            
            if delete_error:
                log_error_with_context(
                    Exception(str(delete_error)),
                    f"clear_multiple_db {base}"
                )
                responses[base]["delete_status"] = "error"
                responses[base]["delete_error"] = delete_error
            else:
                logger.debug(
                    f"[{stack}] Удалено: Redis={deleted_redis}, "
                    f"SQLite={deleted_db} для базы {base}"
                )
                responses[base]["deleted_redis"] = deleted_redis
                responses[base]["deleted_db"] = deleted_db
        
        # === Информация о ненайденных ===
        if not_found_ids:
            responses["_not_found"] = {
                "status": "warning",
                "message": f"Не найдена база для {len(not_found_ids)} requestID",
                "request_ids": not_found_ids
            }
        
        logger.debug(f"[{stack}] Callback завершён")
        return responses
        
    except Exception as e:
        log_error_with_context(e, "handle_callback")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")