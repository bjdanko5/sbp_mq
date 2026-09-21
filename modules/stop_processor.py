# modules/stop_processor.py
"""
Общая логика обработки stop (блокировки QR) для одного Job.

Используется из:
- routes/stop_payload.py — эндпоинт /stop_payload/{bank}/{base}/{job_id}
"""

from pathlib import Path
from typing import Dict, Any, List, Tuple

import config
from modules.api_bank_client import create_bank_client
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.response_utils import create_response
from modules.request_storage import request_storage
from modules import db


async def _filter_unresolved_request_ids(
    bank: str,
    base: str,
    request_ids: List[str],
) -> Tuple[List[str], List[str]]:
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
        f"[stop_processor] [{bank}/{base}] request_ids: "
        f"всего={len(request_ids)}, unresolved={len(unresolved)} "
        f"(Redis={len(in_redis)}, SQLite={len(in_sqlite)}), "
        f"resolved={len(resolved)} (callback пришёл)"
    )

    return unresolved, resolved


async def process_stop_for_job(
    bank: str,
    base: str,
    job_id: int,
    stop_file: Path,
    stoped_dir: Path,
) -> Dict[str, Any]:
    """
    Обработка stop для одного Job.

    Логика:
    1. Прочитать stop_file → request_ids
    2. Нормализовать request_ids к str
    3. Фильтр unresolved (req:* Redis ИЛИ SQLite)
    4. Если unresolved пусто → переместить в stoped/, SUCCESS (callback пришёл для всех)
    5. PATCH /block в банк через create_bank_client(bank)
    6. Если 202 → переместить в stoped/, SUCCESS
    7. Вернуть результат

    Args:
        bank: Имя банка (ci / sb / vtb)
        base: Имя базы
        job_id: ID Job
        stop_file: Путь к stop/{job_id}.json
        stoped_dir: Путь к stoped/

    Returns:
        Dict[str, Any]: create_response(...) с результатом
    """
    stack = get_function_stack()
    filename = stop_file.name

    try:
        logger.debug(f"[{stack}] Начало обработки stop: {bank}/{base}/{job_id} ({filename})")

        # 1. Читаем файл
        if not stop_file.exists():
            logger.error(f"[{stack}] Файл не найден: {stop_file}")
            return create_response(
                status=config.STATUS["FILE_NOT_FOUND"],
                base=base,
                context=filename,
                error=f"Файл не найден: {stop_file}",
                data={"filename": filename, "job_id": job_id}
            )

        try:
            import json
            with open(stop_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception as e:
            log_error_with_context(e, f"read stop_file {filename}")
            return create_response(
                status=config.STATUS["JSON_READ_ERROR"],
                base=base,
                context=filename,
                error=str(e),
                data={"filename": filename, "job_id": job_id}
            )

        # 2. Извлекаем request_ids (нормализация к str)
        if not isinstance(json_data, list):
            return create_response(
                status=config.STATUS["JSON_ERROR"],
                base=base,
                context=filename,
                error="Ожидался массив JSON",
                data={"filename": filename, "job_id": job_id}
            )

        request_ids = [
            str(item.get("requestId")) for item in json_data
            if isinstance(item, dict) and item.get("requestId") is not None
        ]
        if not request_ids:
            logger.warning(f"[{stack}] В {filename} нет requestId — пропуск")
            return create_response(
                status=config.STATUS["JSON_EMPTY"],
                base=base,
                context=filename,
                error="Нет requestId в файле",
                data={"filename": filename, "job_id": job_id}
            )

        # 3. Фильтр: только те, по которым НЕ пришёл callback
        unresolved, resolved = await _filter_unresolved_request_ids(bank, base, request_ids)

        # 4. Если нечего блокировать — переводим в stoped и возвращаем SUCCESS
        if not unresolved:
            logger.info(
                f"[{stack}] Все {len(request_ids)} requestId в {filename} "
                f"уже получили callback — блокировка не нужна"
            )
            _move_to_stoped(stop_file, stoped_dir, filename)
            return create_response(
                status=config.STATUS["SUCCESS"],
                base=base,
                context=filename,
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "filename": filename,
                    "total": len(request_ids),
                    "blocked": 0,
                    "skipped_callback": len(resolved),
                    "message": "Все requestId уже получили callback"
                }
            )

        # 5. PATCH /block в банк через factory
        patch_payload = [{"requestId": rid} for rid in unresolved]
        client = create_bank_client(bank)
        try:
            response, error = await client.send_request_patch(
                data=patch_payload,
                endpoint="/block",
                context=filename,
            )
        finally:
            await client.close()

        if error:
            err_text = error.get("error") if isinstance(error, dict) else str(error)
            logger.error(f"[{stack}] PATCH error для {bank}/{base}/{job_id}: {err_text}")
            return create_response(
                status=config.STATUS["API_ERROR"],
                base=base,
                context=filename,
                error=err_text or "Unknown error",
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "filename": filename,
                    "total": len(request_ids),
                    "blocked": 0,
                    "skipped_callback": len(resolved)
                }
            )

        if response is None:
            return create_response(
                status=config.STATUS["API_ERROR"],
                base=base,
                context=filename,
                error="Пустой ответ от API",
                data={"bank": bank, "base": base, "job_id": job_id, "filename": filename}
            )

        # 6. Если 202 → перемещаем в stoped
        status_code = response.status_code
        if status_code == 202:
            _move_to_stoped(stop_file, stoped_dir, filename)
            logger.info(
                f"[{stack}] [{bank}/{base}/{job_id}] stop выполнен: "
                f"blocked={len(unresolved)}, skipped={len(resolved)}, 202"
            )
            return create_response(
                status=config.STATUS["SUCCESS"],
                base=base,
                context=filename,
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "filename": filename,
                    "total": len(request_ids),
                    "blocked": len(unresolved),
                    "skipped_callback": len(resolved),
                    "status_code": status_code,
                    "response": response.text if config.DEBUG_VERBOSE else None
                }
            )
        else:
            # Не 202 — оставляем файл в stop/ для повтора
            logger.warning(
                f"[{stack}] [{bank}/{base}/{job_id}] stop не выполнен: "
                f"blocked={len(unresolved)}, status_code={status_code}, "
                f"файл остаётся в stop/"
            )
            return create_response(
                status=config.STATUS["API_ERROR"],
                base=base,
                context=filename,
                error=f"HTTP {status_code}",
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "filename": filename,
                    "total": len(request_ids),
                    "blocked": 0,
                    "skipped_callback": len(resolved),
                    "status_code": status_code,
                    "response": response.text[:500] if response.text else None
                }
            )

    except Exception as e:
        log_error_with_context(e, f"process_stop_for_job {bank}/{base}/{job_id}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            base=base,
            context=filename,
            error=str(e),
            data={"bank": bank, "base": base, "job_id": job_id, "filename": filename}
        )


def _move_to_stoped(stop_file: Path, stoped_dir: Path, filename: str) -> bool:
    """
    Перемещает stop_file в stoped_dir.
    
    Returns:
        True при успехе, False при ошибке.
    """
    try:
        stoped_dir.mkdir(parents=True, exist_ok=True)
        dest = stoped_dir / filename
        # Если уже есть — перезаписываем
        if dest.exists():
            dest.unlink()
        stop_file.rename(dest)
        logger.debug(f"[stop_processor] Перемещён {filename} в {stoped_dir.name}/")
        return True
    except Exception as e:
        logger.error(f"[stop_processor] Ошибка перемещения {filename} → {stoped_dir}: {e}")
        return False