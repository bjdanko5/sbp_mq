# sbp.py
import os
import sys
import asyncio

# ✅ НАСТРОЙКА ПУТЕЙ (ТОЛЬКО ЗДЕСЬ!)
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI

from modules.logger_config import configure_uvicorn_access_filter
from modules.mq_client import mq_client
from modules.request_storage import request_storage
from modules.worker import worker
from modules.exceptions import register_exception_handlers
from modules.logger_config import logger
from routes import register_routes
import config

logger.info("=== Логирование инициализировано ===")

app = FastAPI()
register_exception_handlers(app)

# Регистрируем все маршруты из routes/
register_routes(app)


@app.on_event("startup")
async def startup_event():
    try:
        await mq_client.connect()
        await request_storage.connect()
        logger.info("✅ MQ Client + RequestStorage подключены")
        configure_uvicorn_access_filter(("/monitor/data", "/monitor/cards"))
        # ✅ Параметризованный лог: sbp_mq-worker*.service (PROD) / sbp_mq-dev-worker*.service (DEV)
        # Перезапуск — через run_debug.sh (после правки кода)
        logger.info(
            f"ℹ️  Worker'ы управляются через systemd "
            f"({config.WORKER_PATTERN}*.service)"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке."""
    try:
        await mq_client.close()
        await request_storage.close()
        await worker.stop()
        logger.info("✅ Ресурсы очищены")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке: {e}")