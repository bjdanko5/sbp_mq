# routes/health.py
"""
Healthcheck-эндпоинты для мониторинга состояния сервиса.

Два эндпоинта:
  - GET /health           — быстрый (только HTTP-ответ, < 100мс)
  - GET /health/detailed  — полный (RabbitMQ, Redis, воркеры, очередь)
"""

import os
from datetime import datetime, timedelta
from fastapi import APIRouter
from fastapi.responses import JSONResponse

import config
from modules.logger_config import logger

router = APIRouter()

# Время старта приложения (для uptime)
START_TIME = datetime.now()


# ============================================================
#                   БЫСТРЫЙ HEALTHCHECK
# ============================================================

@router.get("/health")
async def health():
    """
    Быстрый healthcheck.
    Отвечает моментально — только для балансировщика / мониторинга.
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================
#                   ПОЛНЫЙ HEALTHCHECK
# ============================================================

@router.get("/health/detailed")
async def health_detailed():
    """
    Полный healthcheck — проверяет все компоненты.
    
    Компоненты:
      - api: сервер отвечает
      - rabbitmq: соединение + размер очереди
      - redis: соединение + количество ключей по типам
      - workers: сколько активно
    """
    result = {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Uptime
    uptime = datetime.now() - START_TIME
    result["uptime_seconds"] = int(uptime.total_seconds())
    result["uptime_human"] = _format_uptime(uptime)
    
    # === API ===
    result["components"]["api"] = {"status": "ok"}
    
    # === RabbitMQ ===
    result["components"]["rabbitmq"] = await _check_rabbitmq()
    
    # === Redis ===
    result["components"]["redis"] = await _check_redis()
    
    # === Workers ===
    result["components"]["workers"] = _check_workers()

    # === CallbackStats ===
    result["components"]["callback_stats"] = await _check_callback_stats()

    # === Monitor WebSocket ===
    result["components"]["monitor_ws"] = _check_monitor_ws()

    # === Общий статус ===
    for comp_name, comp_data in result["components"].items():
        if comp_data.get("status") == "error":
            result["status"] = "error"
            break
    
    # HTTP-код: 200 при OK, 503 при ошибке
    http_code = 200 if result["status"] == "ok" else 503
    
    return JSONResponse(content=result, status_code=http_code)


# ============================================================
#                   ПРОВЕРКИ КОМПОНЕНТОВ
# ============================================================

async def _check_rabbitmq() -> dict:
    """Проверка RabbitMQ."""
    try:
        # Импортируем mq_client (глобальный экземпляр)
        from modules.mq_client import mq_client
        
        if not mq_client.is_connected:
            return {"status": "error", "error": "не подключён"}
        
        # Размер очереди
        queue_size = 0
        consumers = 0
        try:
            from aio_pika import connect_robust
            conn = mq_client._connection
            if conn is not None:
                channel = await conn.channel()
                queue = await channel.declare_queue(
                    config.RABBITMQ_QUEUE,
                    passive=True
                )
                queue_size = queue.declaration_result.message_count
                consumers = queue.declaration_result.consumer_count
                await channel.close()
        except Exception:
            pass  # не критично — соединение уже проверено
        
        return {
            "status": "ok",
            "queue": config.RABBITMQ_QUEUE,
            "queue_size": queue_size,
            "consumers": consumers
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def _check_redis() -> dict:
    """Проверка Redis."""
    try:
        from modules.mq_client import mq_client
        
        redis_client = mq_client.redis_client
        if redis_client is None:
            return {"status": "error", "error": "не подключён"}
        
        # Ping
        await redis_client.ping()
        
        # Считаем ключи по типам
        keys_counts = {}
        for prefix in ["req", "task", "progress", "lock", "processed"]:
            try:
                keys = await redis_client.keys(f"{prefix}:*")
                keys_counts[prefix] = len(keys)
            except Exception:
                keys_counts[prefix] = -1
        
        return {
            "status": "ok",
            "host": f"{config.REDIS_HOST}:{config.REDIS_PORT}",
            "db": config.REDIS_DB,
            "keys": keys_counts
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _check_workers() -> dict:
    """Проверка воркеров (через systemd)."""
    import subprocess
    import config  # ✅ единый источник
    
    # ✅ Паттерн воркеров — из config.py
    # DEV:  sbp_mq-dev-worker
    # PROD: sbp_mq-worker
    pattern = config.WORKER_PATTERN
    
    try:
        # Через systemctl list-units
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        active = 0
        total = 0
        services = []
        
        for line in result.stdout.split("\n"):
            if pattern in line and ".service" in line:
                total += 1
                parts = line.split()
                if len(parts) >= 4 and parts[2] == "active" and parts[3] == "running":
                    active += 1
                    services.append(parts[0])
        
        return {
            "status": "ok" if active > 0 else "warning",
            "pattern": pattern,
            "active": active,
            "total": total,
            "services": services
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def _check_callback_stats() -> dict:
    """Проверка CallbackStats (Redis)."""
    try:
        from modules.callback_stats import callback_stats
        
        if callback_stats._redis is None:
            return {"status": "warning", "error": "не подключён"}
        
        # Ping
        await callback_stats._redis.ping()
        
        return {
            "status": "ok",
            "connected": True,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
    
# ============================================================
#                   MONITOR WEBSOCKET
# ============================================================

def _check_monitor_ws() -> dict:
    """Проверка WebSocket-подключений мониторинга."""
    try:
        from modules.monitor import manager
        
        return {
            "status": "ok",
            "connections": manager.count,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============================================================
#                   УТИЛИТЫ
# ============================================================

def _format_uptime(uptime: timedelta) -> str:
    """Форматирует uptime в 'Xd Xh Xm'."""
    total_seconds = int(uptime.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or not parts:
        parts.append(f"{minutes}m")
    
    return " ".join(parts)