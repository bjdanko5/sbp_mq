# routes/clear_db.py
from fastapi import APIRouter

import config
from modules import db
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response

router = APIRouter()


@router.get("/clear_db/{minRequestID}")
async def clear_db(minRequestID: str):
    try:
        requests_cleared, error = db.clear_db(minRequestID)
        if error:
            log_error_with_context(Exception(str(error)), f"clear_db {minRequestID}")
            return error
        logger.debug(f"Удалено запросов: %s", requests_cleared)
        return {"Удалено": requests_cleared}
    except Exception as e:
        log_error_with_context(e, f"clear_db {minRequestID}")
        return create_response(
            status=config.STATUS["DB_ERROR"],
            error=str(e),
            data={"minRequestID": minRequestID}
        )


@router.get("/clear_one_db/{RequestID}")
async def clear_one_db(RequestID: str):
    try:
        requests_cleared, error = db.clear_one_db(RequestID)
        if error:
            log_error_with_context(Exception(str(error)), f"clear_one_db {RequestID}")
            return error
        logger.debug(f"Удален запрос %s: %s", RequestID, requests_cleared)
        return {"Удалено": requests_cleared}
    except Exception as e:
        log_error_with_context(e, f"clear_one_db {RequestID}")
        return create_response(
            status=config.STATUS["DB_ERROR"],
            error=str(e),
            data={"RequestID": RequestID}
        )


@router.get("/vacuum")
async def vacuum_db():
    try:
        freed_bytes, error = db.vacuum_db()
        if error:
            log_error_with_context(Exception(str(error)), "vacuum_db")
            return error
        
        return {
            "status": "VACUUM выполнен",
            "freed_bytes": freed_bytes,
            "freed_kb": round(freed_bytes / 1024, 2),
            "freed_mb": round(freed_bytes / (1024 * 1024), 2)
        }
    except Exception as e:
        log_error_with_context(e, "vacuum_db")
        return create_response(
            status=config.STATUS["DB_ERROR"],
            error=str(e)
        )
