# routes/callback.py
"""
Callback от банка Центринвест (CI) — тонкая обёртка над callback_base.
"""

from fastapi import APIRouter, HTTPException, Body

from modules.logger_config import log_error_with_context
from modules.callback_base import handle_callback_for_bank
from models.schemas import PayloadItem

router = APIRouter()


@router.post("/callback")
async def handle_callback(payload: list[PayloadItem] = Body(..., max_length=10000)):
    """Callback от Центринвеста."""
    try:
        return await handle_callback_for_bank("ci", payload)
    except Exception as e:
        log_error_with_context(e, "handle_callback (ci)")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")