# routes/stop_payload.py
"""
Остановка обработки запросов (блокировка QR).

Обратная совместимость: 1С кладёт JSON-файл в stop/{job_id}.json
с массивом [{"requestId": "..."}, ...].

Логика:
1. Сканируем stop/*.json
2. Для каждого файла:
   - job_id = имя файла без .json
   - request_ids = из JSON
   - Фильтруем: только те, по которым НЕ пришёл callback
     (проверка: req:* в Redis ИЛИ requests.db в SQLite)
   - PATCH /block в банк
   - Перемещаем в stoped/
"""

import time
from pathlib import Path
from fastapi import APIRouter

import config
from modules import sbp_utils
from modules.api_bank_client import api_bank
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from modules.request_storage import request_storage
from modules import db

router = APIRouter()


async def _filter_unresolved_request_ids(
    bank: str,
    base: str,
    request_ids: list,
) -> tuple:
    """
    Фильтрует request_ids — оставляет только те, по которым НЕ пришёл callback.

    Проверка:
    - req:* в Redis (основной путь)
    - requests.db в SQLite (fallback, если TTL истёк)

    Args:
        bank: Имя банка (для логов)
        base: Имя базы (для логов)
        request_ids: Все request_ids из файла

    Returns:
        (unresolved, resolved):
            unresolved — не получили callback (нужно блокировать)
            resolved — получили callback (пропускаем)
    """
    if not request_ids:
        return [], []

    # 1. Проверка в Redis: есть ли req:{id} → task_id
    rid_to_task_id = await request_storage.get_task_ids_for_requests(request_ids)
    in_redis = {rid for rid, tid in rid_to_task_id.items() if tid}

    # 2. Проверка в SQLite (для тех, кого нет в Redis)
    in_sqlite = set()
    not_in_redis = [rid for rid in request_ids if rid not in in_redis]
    if not_in_redis:
        db_bases, db_error = db.get_bases_for_requests(not_in_redis)
        if not db_error and db_bases:
            in_sqlite = {rid for rid, base_val in db_bases.items() if base_val}

    # 3. Фильтр: unresolved = в Redis ИЛИ в SQLite
    unresolved = [rid for rid in request_ids if rid in in_redis or rid in in_sqlite]
    resolved = [rid for rid in request_ids if rid not in in_redis and rid not in in_sqlite]

    logger.debug(
        f"[stop_payload] [{bank}/{base}] request_ids: "
        f"всего={len(request_ids)}, unresolved={len(unresolved)} "
        f"(Redis={len(in_redis)}, SQLite={len(in_sqlite)}), "
        f"resolved={len(resolved)} (callback пришёл)"
    )

    return unresolved, resolved


@router.get("/stop_payload/{base}")
async def stop_payload(base: str):
    """
    Остановка обработки для базы (обратная совместимость, старая технология).

    Сканирует stop/*.json, для каждого файла:
    - job_id = имя файла
    - request_ids = из JSON
    - PATCH /block в банк

    ⚠️ Банк = ci (жёстко, т.к. URL без bank).
    """
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

        bank = "ci"  # жёстко для обратной совместимости

        results = []
        for json_file in json_files:
            try:
                # 1. Читаем JSON-файл с request_ids
                json_packet, error_response = sbp_paths.read_json_file(json_file)
                if error_response:
                    results.append(error_response)
                    continue
                assert json_packet is not None

                # 2. job_id = имя файла без расширения
                job_id_str = json_file.stem  # {job_id}.json → {job_id}
                try:
                    job_id = int(job_id_str)
                except ValueError:
                    job_id = None
                    logger.warning(
                        f"[stop_payload] Не удалось распарсить job_id из {json_file.name}, "
                        f"использую как есть: {job_id_str}"
                    )

                # 3. Извлекаем request_ids из JSON (нормализуем к str)
                request_ids = [
                    str(item.get("requestId")) for item in json_packet
                    if isinstance(item, dict) and item.get("requestId") is not None
                ]
                if not request_ids:
                    logger.warning(f"[stop_payload] В {json_file.name} нет requestId — пропуск")
                    continue

                # 4. Фильтруем: только те, по которым НЕ пришёл callback
                unresolved, resolved = await _filter_unresolved_request_ids(
                    bank, base, request_ids
                )
                if resolved:
                    logger.debug(
                        f"[stop_payload] Пропущено {len(resolved)} requestId "
                        f"(callback уже пришёл): {resolved[:5]}..."
                    )

                if not unresolved:
                    logger.info(
                        f"[stop_payload] Все {len(request_ids)} requestId в {json_file.name} "
                        f"уже получили callback — блокировка не нужна"
                    )
                    # Перемещаем в stoped — файл обработан (нечего блокировать)
                    sbp_paths.move_to_stoped(json_file)
                    results.append(
                        create_response(
                            status=config.STATUS["SUCCESS"],
                            context=json_file.name,
                            data={
                                "filename": json_file.name,
                                "job_id": job_id,
                                "total": len(request_ids),
                                "blocked": 0,
                                "skipped_callback": len(resolved),
                                "message": "Все requestId уже получили callback"
                            }
                        )
                    )
                    continue

                # 5. Формируем тело запроса: только unresolved
                patch_payload = [{"requestId": rid} for rid in unresolved]

                # 6. PATCH /block в банк
                response, error_response = await api_bank.patch(
                    data=patch_payload,
                    endpoint="/block",
                    context=json_file.name
                )
                if error_response:
                    results.append(error_response)
                    continue
                assert response is not None

                # 7. Формируем результат
                data = {
                    "filename": json_file.name,
                    "job_id": job_id,
                    "total": len(request_ids),
                    "blocked": len(unresolved),
                    "skipped_callback": len(resolved),
                    "status_code": response.status_code,
                    "response": response.text
                }

                if response.status_code == 202:
                    # Перемещаем в stoped
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
                log_error_with_context(
                    e,
                    f"stop_payload обработка файла "
                    f"{json_file.name if hasattr(json_file, 'name') else 'unknown'}"
                )
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
                "bank": bank,
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