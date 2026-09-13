#!/usr/bin/env python
# run_worker.py
"""
Запуск Worker'а.

Worker управляется через systemd:
- sbp_mq-worker.service      — Worker #1 (LOG_NAME=worker-default)
- sbp_mq-worker@1.service    — Worker #2 (LOG_NAME=worker-1, WORKER_ID=mq-worker-1)
- sbp_mq-worker@2.service    — Worker #3 (LOG_NAME=worker-2, WORKER_ID=mq-worker-2)
- sbp_mq-worker@3.service    — Worker #4 (LOG_NAME=worker-3, WORKER_ID=mq-worker-3)
"""

import asyncio
import sys
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# ✅ Импортируем logger_config ДО всего
from modules.logger_config import logger, aggregated_logger
from modules.mq_client import mq_client
import config


async def main() -> None:
    """Запуск Worker'а."""
    worker_id = os.getenv('WORKER_ID', 'default')
    log_name = os.getenv('LOG_NAME', f"worker-{worker_id}")
    
    # ✅ Логи в свой файл
    logger.info(f"🚀 Запуск Worker'а из {PROJECT_DIR}")
    logger.info(f"   LOG_NAME: {log_name}")
    logger.info(f"   WORKER_ID: {worker_id}")
    logger.info(f"   LOG_DIR: {config.LOG_DIR}")
    
    # ✅ АГРЕГИРОВАННЫЙ ЛОГ — старт
    aggregated_logger.info(
        f"🚀 [Worker {worker_id}] СТАРТ | "
        f"LOG_NAME: {log_name} | "
        f"детали: logs/{log_name}.log"
    )
    
    # ✅ Инициализируем MQ Client
    await mq_client.connect()
    
    # ✅ Запускаем Worker
    from modules.worker.base import worker
    await worker.start()


if __name__ == "__main__":
    worker_id = os.getenv('WORKER_ID', 'default')
    log_name = os.getenv('LOG_NAME', f"worker-{worker_id}")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Worker остановлен пользователем")
        aggregated_logger.info(f"👋 [Worker {worker_id}] СТОП (пользователь)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        aggregated_logger.error(
            f"❌ [Worker {worker_id}] КРИТИЧЕСКАЯ ОШИБКА | "
            f"детали: logs/{log_name}_errors.log"
        )
        sys.exit(1)