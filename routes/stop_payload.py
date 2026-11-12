# routes/stop_payload.py
"""
Остановка обработки запросов (блокировка QR).

Два эндпоинта:

1. GET /stop_payload/{base}
   Legacy (обратная совместимость, старая технология, bank=ci).
   Сканирует все stop/*.json, использует legacy api_bank.patch.
   
2. GET /stop_payload/{bank}/{base}/{job_id}
   Новый (мультибанк, mq-технология).
   Ищет {bank}@{base}@{job_id}.json во всех подпапках jobs/,
   перемещает в stop/{job_id}.json и обрабатывает через stop_processor.
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

def _find_job_file_in_jobs(base_path: Path, bank: str, base: str, job_id: int) -> Path | None:
    """
    Ищет файл Job рекурсивно во всех подпапках base_path/jobs/.

    Поддерживаемые имена:
      - {bank}@{base}@{job_id}.json   ← основной формат (напр. ci@zkh_ursv@123.json)
      - {job_id}.json                 ← legacy / fallback

    Возвращает первый найденный путь или None.
    """
    jobs_dir = base_path / "jobs"
    if not jobs_dir.exists():
        return None

    primary_name = f"{bank}@{base}@{job_id}.json"
    legacy_name = f"{job_id}.json"
    # суффикс — на случай base с @ внутри или нестандартного имени
    suffix = f"@{job_id}.json"

    # 1. Быстрый путь: типичное место активного Job — jobs/processing/
    direct = jobs_dir / "processing" / primary_name
    if direct.is_file():
        return direct

    # 2. Полный рекурсивный обход — сверяем имя
    for candidate in jobs_dir.rglob("*.json"):
        if not candidate.is_file():
            continue
        name = candidate.name
        if name == primary_name or name == legacy_name:
            return candidate
        # на случай нестандартной вложенности/имени — по суффиксу
        if name.endswith(suffix):
            return candidate

    return None


@router.get("/stop_payload/{bank}/{base}/{job_id}")
async def stop_payload_mq(bank: str, base: str, job_id: int):
    """
    Новый: остановка обработки для одного Job (мультибанк, mq-технология).

    Логика:
    1. Валидация bank (должен быть в config.SBP_ROOT)
    2. Поиск {bank}@{base}@{job_id}.json во всех подпапках jobs/
       (напр. jobs/processing/ci@zkh_ursv@123.json);
       при нахождении — перемещение в stop/{job_id}.json
    3. Если файла нет (ни в jobs/, ни в stop/) — проверка stoped/{job_id}.json
       → FILE_NOT_FOUND
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

        # 2a. Если в stop/ файла нет — ищем в jobs/** и переносим в stop/
        if not stop_file.exists():
            found = _find_job_file_in_jobs(base_path, bank, base, job_id)
            if found is not None:
                stop_dir.mkdir(parents=True, exist_ok=True)
                try:
                    found.replace(stop_file)  # атомарное перемещение в пределах ФС
                except OSError as move_err:
                    log_error_with_context(
                        move_err,
                        f"stop_payload-mq перемещение {found} → {stop_file}"
                    )
                    return create_response(
                        status=config.STATUS["FILE_MOVE_TO_STOPED_ERROR"],
                        bank=bank,
                        base=base,
                        error=f"Не удалось переместить {found.name} в stop/: {move_err}",
                        data={
                            "bank": bank,
                            "base": base,
                            "job_id": job_id,
                            "source": str(found),
                            "target": str(stop_file),
                        }
                    )

                logger.info(
                    f"[{stack}] Найден и перемещён {found} → {stop_file}"
                )
            else:
                logger.debug(
                    f"[{stack}] Job-файл не найден в jobs/ для {bank}/{base}/{job_id}"
                )

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
                f"[{stack}] Файл не найден ни в jobs/, ни в stop/, ни в stoped/: {stop_file}"
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