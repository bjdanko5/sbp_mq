# routes/create_payload.py
import time
import httpx
from fastapi import APIRouter
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import config
from modules import db, sbp_utils
from modules.api_bank_client import api_bank
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from modules.sbp_utils import SBPPaths

router = APIRouter()


# ============================================================
# ФУНКЦИЯ ОБРАБОТКИ ОДНОГО ФАЙЛА
# ============================================================
async def process_single_file(
    json_file: Path,
    sbp_paths: SBPPaths,
    base: str,
    client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    """
    Обрабатывает один JSON-файл.
    
    Args:
        json_file: Путь к JSON-файлу
        sbp_paths: Объект с путями SBP
        base: Имя базы
        client: HTTP клиент для API банка
    
    Returns:
        Optional[Dict[str, Any]]: Результат обработки в формате create_response
    """
    stack = get_function_stack()
    logger.debug(f"[{stack}] Обработка файла {json_file.name} для базы {base}")
    
    try:
        # 1. Перемещаем в processing
        processing_file, error_response = sbp_paths.move_to_processing(json_file)
        if error_response:
            return error_response
        assert processing_file is not None

        # 2. Читаем JSON
        json_packet, error_response = sbp_paths.read_json_file(processing_file)
        if error_response:
            return error_response
        assert json_packet is not None

        # 3. Сохраняем в БД
        saved_count, error_response = db.save_all_requests_from_json(
            json_packet,
            base,
            filename=processing_file.name
        )
        if error_response:
            return error_response

        # 4. Отправляем запрос в банк
        response, error_response = await api_bank.post(
            data=json_packet,
            context=processing_file.name
        )
        if error_response:
            return error_response
        assert response is not None

        # 5. Формируем результат
        data = {
            "filename": processing_file.name,
            "status_code": response.status_code,
            "response": response.text,
            "base": base
        }
        
        if response.status_code == 202:
            _, error_response = sbp_paths.move_to_sended(processing_file)
            if error_response:
                return error_response
            status = config.STATUS["SUCCESS"]
        else:
            status = config.STATUS["API_ERROR"]

        result = create_response(
            status=status,
            context=processing_file.name,
            data=data,
            include_response=config.DEBUG_VERBOSE and status != config.STATUS["SUCCESS"]
        )
        
        logger.debug(f"[{stack}] Файл {json_file.name} для базы {base} обработан: {status}")
        return result
        
    except Exception as e:
        log_error_with_context(
            e, 
            f"process_single_file {json_file.name if hasattr(json_file, 'name') else 'unknown'} для базы {base}"
        )
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error=str(e),
            data={
                "filename": json_file.name if hasattr(json_file, 'name') else 'unknown',
                "base": base
            }
        )


# ============================================================
# ФУНКЦИЯ ПОДСЧЁТА СТАТИСТИКИ
# ============================================================
def calculate_statistics(
    results: List[Dict[str, Any]],
    base: str
) -> Tuple[int, int, str]:
    """
    Подсчитывает статистику по результатам обработки.
    
    Args:
        results: Список результатов
        base: Имя базы
    
    Returns:
        Tuple[int, int, str]: (success_count, error_count, status)
    """
    stack = get_function_stack()
    
    success_count = sum(1 for r in results if r.get("status") == "SUCCESS")
    error_count = len(results) - success_count

    status = (
        config.STATUS["SUCCESS"] if error_count == 0 else
        config.STATUS["PARTIAL_SUCCESS"] if success_count > 0 else
        config.STATUS["API_ERROR"]
    )

    logger.debug(f"[{stack}] База {base} обработана: {len(results)} файлов, "
                 f"успешно: {success_count}, ошибок: {error_count}")

    return success_count, error_count, status


# ============================================================
# ОСНОВНОЙ ЭНДПОИНТ
# ============================================================
@router.get("/create_payload/{base}")
async def create_payload(base: str):
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос к API ИВЦ из базы {base}")
        
        json_files, sbp_paths, response, should_process = sbp_utils.get_files_with_check(
            base, "base", "Запрос к API ИВЦ из базы"
        )
        if not should_process:
            return response
        
        assert json_files is not None
        assert sbp_paths is not None

        results = []
        
        async with httpx.AsyncClient(verify=config.VERIFY_SSL) as client:
            for json_file in json_files:
                result = await process_single_file(json_file, sbp_paths, base, client)
                if result:
                    results.append(result)
                
                # Задержка между файлами
                time.sleep(config.DELAY_BETWEEN_REQUESTS)

        # ✅ Подсчёт статистики через отдельную функцию
        success_count, error_count, status = calculate_statistics(results, base)

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
        log_error_with_context(e, f"create_payload для базы {base}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            base=base,
            error="Внутренняя ошибка при обработке запроса"
        )