# routes/__init__.py
from fastapi import FastAPI

from routes.main import router as main_router
from routes.health import router as health_router
from routes.clear_db import router as clear_db_router
from routes.test import router as test_router
from routes.create_payload import router as create_payload_router
from routes.create_payload_mq import router as create_payload_mq_router
from routes.get_payload import router as get_payload_router
from routes.stop_payload import router as stop_payload_router
from routes.callback import router as callback_router
from routes.stats import router as stats_router
from routes.mockapi import router as mockapi_router
from routes.queue import router as queue_router
from routes.monitor import router as monitor_router


def register_routes(app: FastAPI):
    """Регистрирует все маршруты в приложении."""
    app.include_router(main_router)
    app.include_router(health_router)          # ← НОВЫЙ
    app.include_router(clear_db_router)
    #app.include_router(test_router)
    app.include_router(create_payload_router)
    app.include_router(create_payload_mq_router)
    app.include_router(get_payload_router)
    app.include_router(stop_payload_router)
    app.include_router(callback_router)
    app.include_router(stats_router)
    app.include_router(mockapi_router, prefix="/mockapi")
    app.include_router(queue_router)
    app.include_router(monitor_router)