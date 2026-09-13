# routes/get_payload.py
import time
import json
import httpx
from fastapi import APIRouter
from pydantic import TypeAdapter
from typing import List

import config
from modules import db, sbp_utils, common_soap
from modules.api_bank_client import api_bank
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from models.schemas import PayloadItem

router = APIRouter()


@router.get("/get_payload/{base}")
async def get_payload(base: str):
    return create_response(
                status=config.STATUS["SUCCESS"],
                base=base,
                error="Временно отключен get_payload"
            )
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос к API ИВЦ GET из базы {base}")
        
        json_files, error_msg, sbp_paths, status = sbp_utils.get_json_files_in_directory(base, "get")
        
        if config.is_error(status):
            return create_response(
                status=status,
                base=base,
                error=error_msg,
                data={"directory": str(sbp_paths.get) if sbp_paths else None}
            )
        
        if status == config.STATUS["NO_FILES"]:
            return create_response(
                status=status,
                base=base,
                message="Нет файлов для обработки",
                data={"directory": str(sbp_paths.get) if sbp_paths else None}
            )
        
        assert sbp_paths is not None
        
        results = []
        async with httpx.AsyncClient(verify=config.VERIFY_SSL) as client:
            for json_file in json_files:
                try:
                    json_packet, error_response = sbp_paths.read_json_file(json_file)
                    if error_response:
                        results.append(error_response)
                        continue
                    assert json_packet is not None
                    
                    response, error_response = await api_bank.get(
                        data=json_packet,
                        context=json_file.name
                    )
                    if error_response:
                        results.append(error_response)
                        continue
                    assert response is not None
                    
                    try:
                        json_response = response.json()
                        adapter = TypeAdapter(List[PayloadItem])
                        payload = adapter.validate_python(json_response)
                    except Exception as e:
                        log_error_with_context(e, f"JSON parse error {json_file.name} {json_response}")
                        results.append(
                            create_response(
                                status=config.STATUS["JSON_READ_ERROR"],
                                error=str(e),
                                context=json_file.name,
                                data={"filename": json_file.name}
                            )
                        )
                        continue
                    
                    # ✅ Исправленный вызов SOAP (без try/except)
                    soap_response, soap_error = common_soap.handle_exceptions_soap_base(
                        base,
                        "ProcessPayload",
                        context=json_file.name,
                        Payload=json.dumps([item.model_dump_json() for item in payload])
                    )
                    if soap_error:
                        results.append(soap_error)
                        continue
                    
                    request_ids = [item.requestId for item in payload]
                    deleted_count, delete_error = db.clear_multiple_db(request_ids)
                    if delete_error:
                        log_error_with_context(Exception(str(delete_error)), f"clear_multiple_db {json_file.name}")
                        results.append(
                            create_response(
                                status=config.STATUS["DB_CLEAR_ERROR"],
                                error=str(delete_error),
                                context=json_file.name,
                                data={"filename": json_file.name}
                            )
                        )
                        continue
                    
                    dest_path, move_error = sbp_paths.move_to_geted(json_file)
                    if move_error:
                        results.append(move_error)
                        continue
                    
                    results.append(
                        create_response(
                            status=config.STATUS["SUCCESS"],
                            context=json_file.name,
                            data={
                                "filename": json_file.name,
                                "requests_count": len(payload),
                                "deleted_count": deleted_count,
                                "soap_response": soap_response if config.DEBUG_VERBOSE else "disabled"
                            }
                        )
                    )
                    
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    
                except Exception as e:
                    log_error_with_context(e, f"get_payload обработка файла {json_file.name if hasattr(json_file, 'name') else 'unknown'}")
                    results.append(
                        create_response(
                            status=config.STATUS["UNKNOWN_ERROR"],
                            error=str(e),
                            data={"filename": json_file.name if hasattr(json_file, 'name') else 'unknown'}
                        )
                    )
                    continue
        
        success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
        error_count = len(results) - success_count
        
        status = (
            config.STATUS["SUCCESS"] if error_count == 0 else
            config.STATUS["PARTIAL_SUCCESS"] if success_count > 0 else
            config.STATUS["API_ERROR"]
        )
        
        return create_response(
            status=status,
            base=base,
            data={
                "total": len(results),
                "success": success_count,
                "errors": error_count,
                "results": results
            }
        )
        
    except Exception as e:
        log_error_with_context(e, f"get_payload для базы {base}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            base=base,
            error="Внутренняя ошибка при обработке запроса"
        )