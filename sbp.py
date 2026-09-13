# sbp.py
import os
import sys
import asyncio

# ✅ НАСТРОЙКА ПУТЕЙ (ТОЛЬКО ЗДЕСЬ!)
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI

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
        
        if config.DEBUG_VERBOSE:
            import subprocess
            
            # ✅ Перезапускаем все Worker'ы через bash (wildcard работает)
            result = subprocess.run(
                ["sudo", "bash", "-c", "systemctl restart sbp_mq-worker*"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("✅ Все Worker'ы перезапущены")
            else:
                logger.error(f"❌ Ошибка перезапуска Worker'ов: {result.stderr}")
        else:
            logger.info("ℹ️ Worker управляется через systemd (production)")
        
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