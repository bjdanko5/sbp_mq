# sbp.py
import os
import sys
import asyncio
from contextlib import asynccontextmanager

# ✅ НАСТРОЙКА ПУТЕЙ (ТОЛЬКО ЗДЕСЬ!)
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI

from modules.logger_config import configure_uvicorn_access_filter
from modules.mq_client import mq_client
from modules.request_storage import request_storage
from modules.callback_stats import callback_stats       # ← ДОБАВЛЕНО
from modules.worker import worker
from modules.exceptions import register_exception_handlers
from modules.logger_config import logger
from routes import register_routes
import config

logger.info("=== Логирование инициализировано ===")


# ============================================================
#                     LIFESPAN (startup + shutdown)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    
    Startup: подключение к RabbitMQ, Redis, RequestStorage, CallbackStats.
    Shutdown: закрытие всех соединений.
    """
    # ============================================================
    # STARTUP
    # ============================================================
    try:
        await mq_client.connect()
        await request_storage.connect()
        await callback_stats.connect()      # ← ДОБАВЛЕНО
        logger.info("✅ MQ Client + RequestStorage + CallbackStats подключены")
        
        configure_uvicorn_access_filter(("/monitor/data", "/monitor/cards"))
        
        logger.info(
            f"ℹ️  Worker'ы управляются через systemd "
            f"({config.WORKER_PATTERN}*.service)"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации: {e}")
        raise   # ← если startup упал, приложение не запустится
    
    yield   # ← приложение работает
    
    # ============================================================
    # SHUTDOWN
    # ============================================================
    try:
        await mq_client.close()
        await request_storage.close()
        await callback_stats.close()        # ← ДОБАВЛЕНО
        await worker.stop()
        logger.info("✅ Ресурсы очищены")
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке: {e}")


# ============================================================
#                     ПРИЛОЖЕНИЕ
# ============================================================

app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)

# Регистрируем все маршруты из routes/
register_routes(app)