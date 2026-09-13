# routes/queue.py
"""
Эндпоинты для работы с очередью.
"""

from fastapi import APIRouter

from modules.mq_client import mq_client
from modules.response_utils import create_response
from modules.worker import worker
import config

router = APIRouter()


@router.get("/queue/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Получить статус задачи.
    
    Логика:
    1. Если есть полный результат → возвращаем его
    2. Если есть прогресс → возвращаем прогресс
    3. Иначе → pending
    """
    status = await mq_client.get_task_status(task_id)
    
    return create_response(
        status=config.STATUS["SUCCESS"],
        data=status
    )


@router.get("/queue/result/{task_id}")
async def get_task_result(task_id: str):
    """
    Получить полный результат задачи.
    
    Если задача ещё обрабатывается → возвращаем прогресс.
    """
    result = await mq_client.get_result(task_id)
    
    if result:
        return create_response(
            status=config.STATUS["SUCCESS"],
            data={
                "task_id": task_id,
                "result": result
            }
        )
    
    # Прогресс (задача ещё обрабатывается)
    progress = await mq_client.get_progress(task_id)
    
    if progress:
        return create_response(
            status=config.STATUS["SUCCESS"],
            message="Задача ещё обрабатывается",
            data={
                "task_id": task_id,
                "status": "processing",
                "progress": progress
            }
        )
    
    # Ничего нет
    return create_response(
        status=config.STATUS["API_ERROR"],
        error=f"Результаты для задачи {task_id} не найдены"
    )


@router.get("/queue/progress/{task_id}")
async def get_task_progress(task_id: str):
    """
    Получить ТОЛЬКО прогресс задачи.
    """
    progress = await mq_client.get_progress(task_id)
    
    if progress:
        return create_response(
            status=config.STATUS["SUCCESS"],
            data={
                "task_id": task_id,
                "progress": progress
            }
        )
    
    return create_response(
        status=config.STATUS["SUCCESS"],
        message="Прогресс не найден",
        data={
            "task_id": task_id,
            "status": "not_found"
        }
    )


@router.post("/queue/worker/start")
async def start_worker():
    """Запустить Worker."""
    if worker.is_running:
        return create_response(
            status=config.STATUS["SUCCESS"],
            message="Worker уже запущен"
        )
    
    import asyncio
    asyncio.create_task(worker.start())
    
    return create_response(
        status=config.STATUS["SUCCESS"],
        message="Worker запущен"
    )


@router.post("/queue/worker/stop")
async def stop_worker():
    """Остановить Worker."""
    await worker.stop()
    return create_response(
        status=config.STATUS["SUCCESS"],
        message="Worker остановлен"
    )


@router.get("/queue/worker/status")
async def get_worker_status():
    """Получить статус Worker."""
    return create_response(
        status=config.STATUS["SUCCESS"],
        data={
            "is_running": worker.is_running
        }
    )