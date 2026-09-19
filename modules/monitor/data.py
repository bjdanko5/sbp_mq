# modules/monitor/data.py
"""
Сбор данных мониторинга из Redis.
"""

from datetime import datetime, timedelta
import json

from modules.mq_client import mq_client
from modules.callback_stats import callback_stats
from modules.logger_config import logger


COMPLETED_TTL_MINUTES = 5


async def get_monitor_data() -> dict:
    """Читает все активные и недавно завершённые задачи из Redis."""
    redis_client = mq_client.redis_client
    if redis_client is None:
        return _empty_response()
    
    banks: set = set()
    bases: set = set()
    cutoff = datetime.now() - timedelta(minutes=COMPLETED_TTL_MINUTES)
    
    processing = await _load_processing(redis_client, banks, bases)
    completed = await _load_completed(redis_client, cutoff, banks, bases)
    await _enrich_with_callbacks(processing + completed)
    
    processing.sort(key=lambda x: x.get('started_at', ''), reverse=True)
    completed.sort(key=lambda x: x.get('finished_at', ''), reverse=True)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "processing": processing,
        "completed": completed,
        "banks": sorted(banks),
        "bases": sorted(bases),
    }


async def _load_processing(redis_client, banks: set, bases: set) -> list:
    result = []
    keys = await redis_client.keys("progress:*")
    for key in keys:
        key_str = str(key)
        data = await redis_client.get(key_str)
        if not data:
            continue
        try:
            progress = json.loads(str(data))
            progress['task_id'] = key_str.replace("progress:", "")
            progress['_type'] = 'processing'
            result.append(progress)
            if progress.get('bank'):
                banks.add(progress['bank'])
            if progress.get('base'):
                bases.add(progress['base'])
        except json.JSONDecodeError:
            continue
    return result


async def _load_completed(redis_client, cutoff, banks: set, bases: set) -> list:
    result = []
    keys = await redis_client.keys("task:*")
    for key in keys:
        key_str = str(key)
        data = await redis_client.get(key_str)
        if not data:
            continue
        try:
            task = json.loads(str(data))
            finished_str = task.get('finished_at')
            if finished_str:
                try:
                    finished_dt = datetime.fromisoformat(finished_str)
                    if finished_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            result.append({
                "task_id": key_str.replace("task:", ""),
                "bank": task.get('bank'),
                "base": task.get('base'),
                "job_id": task.get('job_id'),
                "job_name": task.get('job_name'),
                "status": task.get('status'),
                "started_at": task.get('started_at'),
                "finished_at": task.get('finished_at'),
                "summary": task.get('summary', {}),
                "error": task.get('error'),
                "files": task.get('files', []),
                "_type": 'completed',
            })
            if task.get('bank'):
                banks.add(task['bank'])
            if task.get('base'):
                bases.add(task['base'])
        except json.JSONDecodeError:
            continue
    return result


async def _enrich_with_callbacks(jobs: list) -> None:
    for job in jobs:
        bank = job.get('bank')
        base = job.get('base')
        job_id = job.get('job_id')
        if bank and base and job_id is not None:
            job['callback_count'] = await callback_stats.get_count(bank, base, job_id)
            job['callback_last_error'] = await callback_stats.get_last_error(bank, base, job_id)
        else:
            job['callback_count'] = 0
            job['callback_last_error'] = None


def _empty_response() -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "processing": [],
        "completed": [],
        "banks": [],
        "bases": [],
    }
