# exceptions.py
import logging
import traceback
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from modules.logger_config import logger, get_function_stack

# Создаём отдельный логгер для ошибок
error_logger = logging.getLogger("error")


def register_exception_handlers(app: FastAPI):
    """Регистрация обработчиков исключений"""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        stack = get_function_stack()
        error_msg = f"Validation error for request {request.method} {request.url}"
        logger.error(f"[{stack}] 🔴 {error_msg}")
        logger.error(f"[{stack}] 🔴 Error details: {exc.errors()}")
        try:
            body = await request.body()
            logger.error(f"[{stack}] 🔴 Request body: {body.decode('utf-8', errors='ignore')[:500]}")
        except Exception:
            pass
        
        # Детальный лог в error_logger
        error_logger.error(f"=== VALIDATION ERROR IN {stack} ===")
        error_logger.error(f"Method: {request.method}")
        error_logger.error(f"URL: {request.url}")
        error_logger.error(f"Errors: {exc.errors()}")
        error_logger.error("=" * 80)
        
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        stack = get_function_stack()
        logger.error(f"[{stack}] 🔴 HTTPException {exc.status_code}: {request.method} {request.url}")
        logger.error(f"[{stack}] 🔴 Detail: {exc.detail}")
        try:
            body = await request.body()
            logger.error(f"[{stack}] 🔴 Request body: {body.decode('utf-8', errors='ignore')[:500]}")
        except Exception:
            pass
        logger.error(f"[{stack}] 🔴 Headers: {dict(request.headers)}")
        
        # Детальный лог в error_logger
        error_logger.error(f"=== HTTP EXCEPTION IN {stack} ===")
        error_logger.error(f"Status: {exc.status_code}")
        error_logger.error(f"Method: {request.method}")
        error_logger.error(f"URL: {request.url}")
        error_logger.error(f"Detail: {exc.detail}")
        error_logger.error("=" * 80)
        
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Глобальный обработчик всех непредвиденных исключений."""
        stack = get_function_stack()
        error_type = type(exc).__name__
        error_msg = str(exc)
        
        # Краткий лог
        logger.error(f"[{stack}] 🔴 Unhandled {error_type}: {error_msg}")
        logger.error(f"[{stack}] 🔴 Request: {request.method} {request.url}")
        try:
            body = await request.body()
            logger.error(f"[{stack}] 🔴 Request body: {body.decode('utf-8', errors='ignore')[:500]}")
        except Exception:
            pass
        
        # Подробный лог с полным стеком
        error_logger.error(f"=== UNHANDLED EXCEPTION IN {stack} ===")
        error_logger.error(f"Method: {request.method}")
        error_logger.error(f"URL: {request.url}")
        error_logger.error(f"Exception: {error_type}: {error_msg}")
        error_logger.error("Full traceback:")
        error_logger.error(traceback.format_exc())
        error_logger.error("=" * 80)
        
        # В production возвращаем общее сообщение
        return JSONResponse(
            status_code=500,
            content={
                "status": "ERROR",
                "detail": "Внутренняя ошибка сервера",
                "error_type": error_type
            }
        )