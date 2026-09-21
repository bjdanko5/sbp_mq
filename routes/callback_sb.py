# routes/callback_sb.py
"""
Callback от Сбербанка (SB) — тонкая обёртка над callback_base.

⚠️ Банк SB — в разработке. URL зарегистрирован, логика общая с ci.
"""

from fastapi import APIRouter, HTTPException, Body

from modules.logger_config import log_error_with_context
from modules.callback_base import handle_callback_for_bank
from models.schemas import PayloadItem

router = APIRouter()


@router.post("/callback_sb")
async def handle_callback_sb(payload: list[PayloadItem] = Body(..., max_length=10000)):
    """Callback от Сбербанка."""
    try:
        return await handle_callback_for_bank("sb", payload)
    except Exception as e:
        log_error_with_context(e, "handle_callback (sb)")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
