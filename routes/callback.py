# routes/callback.py
import json
from fastapi import APIRouter, HTTPException, Body
from typing import Optional, Dict, List, Tuple, Any

import config
from modules import db, common_soap
from modules.request_storage import request_storage
from modules.mq_client import mq_client
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from modules.callback_stats import callback_stats
from models.schemas import PayloadItem

router = APIRouter()


# ============================================================
#            ПОИСК BASE И TASK_INFO ПО REQUESTID
# ============================================================

async def resolve_bases_for_requests(
    request_ids: List[str]
) -> Tuple[
    Dict[str, Optional[str]],       # request_id → base
    Dict[str, Dict[str, Any]],      # task_id → {bank, base, job_id}
    Dict[str, Optional[str]],       # request_id → task_id
]:
    """
    Находит base и task_info для каждого requestID.
    
    Логика:
    1. Redis: req:{requestID} → task_id
    2. task:{task_id} → bank, base, job_id
    3. Fallback: SQLite → base (task_info не будет)
    
    Returns:
        Tuple из трёх словарей:
        1. {requestID: base или None}
        2. {task_id: {"bank", "base", "job_id"}}
        3. {requestID: task_id или None}
    """
    stack = get_function_stack()
    
    # === Шаг 1: Redis — task_id для request_id ===
    rid_to_task_id = await request_storage.get_task_ids_for_requests(request_ids)
    
    # Уникальные task_id
    unique_task_ids = {tid for tid in rid_to_task_id.values() if tid}
    
    # === Шаг 2: Читаем task:* ===
    task_info: Dict[str, Dict[str, Any]] = {}
    for tid in unique_task_ids:
        task_data = await mq_client.get_result(tid)
        if task_data:
            task_info[tid] = {
                "bank": task_data.get("bank"),
                "base": task_data.get("base"),
                "job_id": task_data.get("job_id"),
            }
    
    # === Шаг 3: base для каждого request_id ===
    result: Dict[str, Optional[str]] = {rid: None for rid in request_ids}
    for rid, tid in rid_to_task_id.items():
        if tid and tid in task_info:
            result[rid] = task_info[tid].get("base")
    
    # === Шаг 4: Fallback — SQLite ===
    not_found = [rid for rid, base in result.items() if not base]
    
    if not_found:
        logger.debug(
            f"[{stack}] Redis не нашёл base для {len(not_found)} requestID, "
            f"пробуем SQLite: {not_found[:10]}..."
        )
        
        db_bases, db_error = db.get_bases_for_requests(not_found)
        
        if db_error:
            log_error_with_context(
                Exception(str(db_error)),
                "callback fallback get_bases_for_requests"
            )
        else:
            for rid, base in db_bases.items():
                if base:
                    result[rid] = base
                    logger.debug(f"[{stack}] Fallback SQLite: {rid} → {base}")
    
    # === Итог ===
    found = sum(1 for b in result.values() if b)
    logger.debug(
        f"[{stack}] Найдено base: {found}/{len(request_ids)}, "
        f"task_info: {len(task_info)}"
    )
    
    return result, task_info, rid_to_task_id


# ============================================================
#                     CALLBACK ENDPOINT
# ============================================================

@router.post("/callback")
async def handle_callback(payload: list[PayloadItem] = Body(..., max_length=10000)):
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Получен callback с {len(payload)} запросами")
        
        # Логируем requestID
        request_ids = [item.requestId for item in payload]
        logger.debug(f"[{stack}] Payload requestIds: {request_ids}")
        
        if config.DEBUG_VERBOSE:
            payload_json = json.dumps(
                [item.model_dump() for item in payload],
                ensure_ascii=False
            )
            logger.debug(f"[{stack}] Payload (full): {payload_json}")
        
        # === Резолвим base + task_info ===
        request_to_base, task_info, rid_to_task_id = await resolve_bases_for_requests(
            request_ids
        )
        
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
            
            # Логируем данные перед отправкой в SOAP
            soap_payload = json.dumps(items, ensure_ascii=False)
            logger.debug(f"[{stack}] Отправка в SOAP (база {base}): {soap_payload}")
            
            # Отправка в SOAP
            soap_response, soap_error = common_soap.handle_exceptions_soap_base(
                base,
                "ProcessPayload",
                context=base,
                Payload=soap_payload
            )
            
            # === Определяем request_ids этой базы ===
            items_request_ids = [item['requestId'] for item in items]
            
            # === Обновляем статистику callback'ов ===
            # Для каждого request_id находим task_info и увеличиваем счётчик
            error_msg = None
            if soap_error:
                error_msg = soap_error.get("error", "Unknown SOAP error")
            
            for rid in items_request_ids:
                tid = rid_to_task_id.get(rid)
                if tid and tid in task_info:
                    info = task_info[tid]
                    bank = info.get("bank")
                    base_name = info.get("base")
                    job_id = info.get("job_id")
                    
                    if bank and base_name and job_id is not None:
                        # ✅ Инкремент счётчика
                        await callback_stats.increment(bank, base_name, job_id)
                        
                        # ✅ Сохранение ошибки (если есть)
                        if error_msg:
                            await callback_stats.save_error(
                                bank, base_name, job_id, error_msg
                            )
            
            # === Формируем ответ ===
            if soap_error:
                responses[base] = {
                    "status": "error",
                    "error": error_msg or "SOAP ошибка",
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
            deleted_redis = await request_storage.delete_requests(items_request_ids)
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