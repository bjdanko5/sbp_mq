# routes/stop_payload.py
"""
Остановка обработки запросов (блокировка QR).

Два эндпоинта:

1. GET /stop_payload/{base}
   Legacy (обратная совместимость, старая технология, bank=ci).
   Сканирует все stop/*.json, использует legacy api_bank.patch.
   
2. GET /stop_payload/{bank}/{base}/{job_id}
   Новый (мультибанк, mq-технология).
   Обрабатывает ОДИН файл stop/{job_id}.json через stop_processor.
   Использует create_bank_client(bank).send_request_patch().
"""

import time
from pathlib import Path
from fastapi import APIRouter

import config
from modules import sbp_utils
from modules.api_bank_client import api_bank
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from modules.stop_processor import process_stop_for_job
from modules import db

router = APIRouter()


# ============================================================
#         LEGACY: GET /stop_payload/{base} (старый синтаксис)
# ============================================================

async def _filter_unresolved_request_ids_legacy(
    bank: str,
    base: str,
    request_ids: list,
) -> tuple:
    """
    Legacy-фильтр для обратной совместимости (используется в /stop_payload/{base}).
    Дублирует логику stop_processor для legacy-пути (bank=ci).
    """
    if not request_ids:
        return [], []

    from modules.request_storage import request_storage

    rid_to_task_id = await request_storage.get_task_ids_for_requests(request_ids)
    in_redis = {rid for rid, tid in rid_to_task_id.items() if tid}

    in_sqlite = set()
    not_in_redis = [rid for rid in request_ids if rid not in in_redis]
    if not_in_redis:
        db_bases, db_error = db.get_bases_for_requests(not_in_redis)
        if not db_error and db_bases:
            in_sqlite = {rid for rid, base_val in db_bases.items() if base_val}

    unresolved = [rid for rid in request_ids if rid in in_redis or rid in in_sqlite]
    resolved = [rid for rid in request_ids if rid not in in_redis and rid not in in_sqlite]

    logger.debug(
        f"[stop_payload-legacy] [{bank}/{base}] request_ids: "
        f"всего={len(request_ids)}, unresolved={len(unresolved)} "
        f"(Redis={len(in_redis)}, SQLite={len(in_sqlite)}), "
        f"resolved={len(resolved)} (callback пришёл)"
    )

    return unresolved, resolved


@router.get("/stop_payload/{base}")
async def stop_payload_legacy(base: str):
    """
    Legacy: остановка обработки для базы (старая технология, bank=ci).

    Сканирует stop/*.json, для каждого файла:
    - job_id = имя файла
    - request_ids = из JSON
    - PATCH /block через legacy api_bank (bank=ci)

    ⚠️ Не переведён на factory — оставлен для обратной совместимости.
    """
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос к API ИВЦ STOP из базы {base}")

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

        bank = "ci"

        results = []
        for json_file in json_files:
            try:
                json_packet, error_response = sbp_paths.read_json_file(json_file)
                if error_response:
                    results.append(error_response)
                    continue
                assert json_packet is not None

                job_id_str = json_file.stem
                try:
                    job_id = int(job_id_str)
                except ValueError:
                    job_id = None
                    logger.warning(
                        f"[stop_payload-legacy] Не удалось распарсить job_id из {json_file.name}"
                    )

                request_ids = [
                    str(item.get("requestId")) for item in json_packet
                    if isinstance(item, dict) and item.get("requestId") is not None
                ]
                if not request_ids:
                    logger.warning(f"[stop_payload-legacy] В {json_file.name} нет requestId — пропуск")
                    continue

                unresolved, resolved = await _filter_unresolved_request_ids_legacy(
                    bank, base, request_ids
                )
                if resolved:
                    logger.debug(
                        f"[stop_payload-legacy] Пропущено {len(resolved)} requestId "
                        f"(callback уже пришёл)"
                    )

                if not unresolved:
                    logger.info(
                        f"[stop_payload-legacy] Все {len(request_ids)} requestId в {json_file.name} "
                        f"уже получили callback — блокировка не нужна"
                    )
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

                patch_payload = [{"requestId": rid} for rid in unresolved]

                response, error_response = await api_bank.patch(
                    data=patch_payload,
                    endpoint="/block",
                    context=json_file.name
                )
                if error_response:
                    results.append(error_response)
                    continue
                assert response is not None

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
                    f"stop_payload-legacy обработка файла "
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
        log_error_with_context(e, f"stop_payload-legacy для базы {base}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            base=base,
            error="Внутренняя ошибка при обработке запроса"
        )


# ============================================================
#         NEW: GET /stop_payload/{bank}/{base}/{job_id} (мультибанк)
# ============================================================

@router.get("/stop_payload/{bank}/{base}/{job_id}")
async def stop_payload_mq(bank: str, base: str, job_id: int):
    """
    Новый: остановка обработки для одного Job (мультибанк, mq-технология).

    Логика:
    1. Валидация bank (должен быть в config.SBP_ROOT)
    2. Поиск файла stop/{job_id}.json для {bank}/{base}
    3. Если файла нет — проверка stoped/{job_id}.json → FILE_NOT_FOUND
    4. process_stop_for_job(bank, base, job_id, stop_file, stoped_dir)

    URL: /stop_payload/{bank}/{base}/{job_id}
    Пример: /stop_payload/ci/zkh_ursv/123
    """
    stack = get_function_stack()
    logger.debug(f"[{stack}] Запрос к API ИВЦ STOP: bank={bank}, base={base}, job_id={job_id}")

    # 1. Валидация bank
    if bank not in config.SBP_ROOT:
        logger.error(f"[{stack}] Неизвестный банк: {bank}. Доступные: {list(config.SBP_ROOT.keys())}")
        return create_response(
            status=config.STATUS["CONFIG_ERROR"],
            bank=bank,
            base=base,
            error=f"Неизвестный банк: {bank}. Доступные: {list(config.SBP_ROOT.keys())}"
        )

    try:
        # 2. Формируем пути для банка/базы
        base_path = config.SBP_ROOT.bank_pathlib(bank, base)
        stop_dir = base_path / "stop"
        stoped_dir = base_path / "stoped"
        stop_file = stop_dir / f"{job_id}.json"

        # 3. Если файла нет в stop/ — проверяем stoped/
        if not stop_file.exists():
            stoped_file = stoped_dir / f"{job_id}.json"
            if stoped_file.exists():
                logger.info(
                    f"[{stack}] Файл {job_id}.json уже в stoped/ — обработан ранее"
                )
                return create_response(
                    status=config.STATUS["FILE_NOT_FOUND"],
                    bank=bank,
                    base=base,
                    error=f"Файл {job_id}.json уже обработан (в stoped/)",
                    data={
                        "bank": bank,
                        "base": base,
                        "job_id": job_id,
                        "stop_dir": str(stop_dir),
                        "stoped_dir": str(stoped_dir)
                    }
                )
            logger.error(
                f"[{stack}] Файл не найден ни в stop/, ни в stoped/: {stop_file}"
            )
            return create_response(
                status=config.STATUS["FILE_NOT_FOUND"],
                bank=bank,
                base=base,
                error=f"Файл {job_id}.json не найден",
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "stop_dir": str(stop_dir),
                    "stoped_dir": str(stoped_dir)
                }
            )

        # 4. Обработка через stop_processor
        result = await process_stop_for_job(
            bank=bank,
            base=base,
            job_id=job_id,
            stop_file=stop_file,
            stoped_dir=stoped_dir,
        )
        return result

    except Exception as e:
        log_error_with_context(e, f"stop_payload-mq bank={bank} base={base} job_id={job_id}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            bank=bank,
            base=base,
            error=f"Внутренняя ошибка: {str(e)}"
        )