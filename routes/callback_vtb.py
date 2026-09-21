# routes/callback_vtb.py
"""
Callback от ВТБ (VTB) — тонкая обёртка над callback_base.

⚠️ Банк VTB — в разработке. URL зарегистрирован, логика общая с ci.
"""

from fastapi import APIRouter, HTTPException, Body

from modules.logger_config import log_error_with_context
from modules.callback_base import handle_callback_for_bank
from models.schemas import PayloadItem

router = APIRouter()


@router.post("/callback_vtb")
async def handle_callback_vtb(payload: list[PayloadItem] = Body(..., max_length=10000)):
    """Callback от ВТБ."""
    try:
        return await handle_callback_for_bank("vtb", payload)
    except Exception as e:
        log_error_with_context(e, "handle_callback (vtb)")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
