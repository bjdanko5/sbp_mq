# routes/stop_payload.py
import time
import json
import shutil
import httpx
from pathlib import Path
from fastapi import APIRouter

import config
from modules import sbp_utils
from modules.api_bank_client import api_bank
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response

router = APIRouter()


@router.get("/stop_payload/{base}")
async def stop_payload(base: str):
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос к API ИВЦ STOP из базы {base}")
        
        # 1. Получаем файлы из директории "stop"
        json_files, error_msg, sbp_paths, status = sbp_utils.get_json_files_in_directory(base, "stop")
        
        if config.is_error(status):
            return create_response(
                status=status,
                base=base,
                error=error_msg,
                data={"directory": str(sbp_paths.stop) if sbp_paths else None}
            )
        
        if status == config.STATUS["NO_FILES"]:
            return create_response(
                status=status,
                base=base,
                message="Нет файлов для обработки",
                data={"directory": str(sbp_paths.stop) if sbp_paths else None}
            )
        
        assert sbp_paths is not None
        
        results = []
        async with httpx.AsyncClient(verify=config.VERIFY_SSL) as client:
            for json_file in json_files:
                try:
                    # 1. Читаем JSON-файл
                    json_packet, error_response = sbp_paths.read_json_file(json_file)
                    if error_response:
                        results.append(error_response)
                        continue
                    assert json_packet is not None
                    
                    # 2. Отправляем PATCH-запрос на блокировку
                    response, error_response = await api_bank.patch(
                        data=json_packet,
                        endpoint="/block",
                        context=json_file.name
                    )
                    if error_response:
                        results.append(error_response)
                        continue
                    assert response is not None
                    
                    # 3. Формируем результат
                    data = {
                        "filename": json_file.name,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                    
                    if response.status_code == 202:
                        # Перемещение в stoped
                        _, error_response = sbp_paths.move_to_stoped(json_file)
                        if error_response:
                            results.append(error_response)
                            continue
                        status = config.STATUS["SUCCESS"]
                    else:
                        status = config.STATUS["API_ERROR"]
                    
                    results.append(
                        create_response(
                            status=status,
                            context=json_file.name,
                            data=data,
                            include_response=config.DEBUG_VERBOSE and status != config.STATUS["SUCCESS"]
                        )
                    )
                    
                    if status in [config.STATUS["API_ERROR"], config.STATUS["API_OK_FILE_ERROR"]]:
                        continue
                    
                    time.sleep(config.DELAY_BETWEEN_REQUESTS)
                    
                except Exception as e:
                    log_error_with_context(e, f"stop_payload обработка файла {json_file.name if hasattr(json_file, 'name') else 'unknown'}")
                    results.append(
                        create_response(
                            status=config.STATUS["UNKNOWN_ERROR"],
                            error=str(e),
                            data={"filename": json_file.name if hasattr(json_file, 'name') else 'unknown'}
                        )
                    )
                    continue
        
        # Подсчёт статистики
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
        log_error_with_context(e, f"stop_payload для базы {base}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            base=base,
            error="Внутренняя ошибка при обработке запроса"
        )