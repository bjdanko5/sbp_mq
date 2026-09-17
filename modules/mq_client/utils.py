# modules/mq_client/utils.py
"""
Вспомогательные утилиты для MQ клиента.
"""

import uuid
from datetime import datetime
from typing import  Optional

def generate_task_id(prefix: str = "task") -> str:
    """
    Генерирует уникальный ID задачи.
    
    Args:
        prefix: Префикс для ID
    
    Returns:
        str: Уникальный ID задачи
    """
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"


def generate_job_id() -> str:
    """Генерирует ID для Job."""
    return generate_task_id("job")


def generate_batch_id() -> str:
    """Генерирует ID для пакета задач."""
    return generate_task_id("batch")


def validate_job_data(job_data: dict) -> list:
    """
    Проверяет обязательные поля в Job данных.
    
    Args:
        job_data: Данные Job
    
    Returns:
        list: Список отсутствующих полей
    
    Example:
        missing = validate_job_data(job_data)
        if missing:
            raise ValueError(f"Отсутствуют поля: {', '.join(missing)}")
    """
    required_fields = ['bank', 'base', 'job_id']
    return [field for field in required_fields if field not in job_data]