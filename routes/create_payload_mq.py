# routes/create_payload_mq.py
from pathlib import Path
from fastapi import APIRouter
from typing import Optional

import config
from modules.logger_config import logger, get_function_stack, log_error_with_context
from modules.mq_client import mq_client
from modules.job_manager import job_manager  # ← импорт НЕ МЕНЯЕТСЯ!
from modules.response_utils import create_response

router = APIRouter()


# ============================================================
#                     ЭНДПОИНТЫ
# ============================================================

@router.get("/create_payload_mq/{bank}/{base}/{job_id}")
async def create_payload_mq(bank: str, base: str, job_id: int):
    """
    Создаёт задачу для указанного банка через MQ (асинхронная обработка).
    
    Args:
        bank: Имя банка (ci, sb, vtb)
        base: Имя базы (например, zkh_ursv)
        job_id: ID Job в 1С (уникальный в пределах базы)
    
    Returns:
        Dict: task_id и статус задачи
    
    Пример:
        GET /create_payload_mq/ci/zkh_ursv/123
    
    Ожидаемый ответ:
        {
            "status": "SUCCESS",
            "code": "SUCCESS",
            "data": {
                "task_id": "job_20260906120000_abc123",
                "bank": "ci",
                "base": "zkh_ursv",
                "job_id": 123,
                "files_count": 1,
                "total_requests": 4,
                "status_url": "/queue/status/job_20260906120000_abc123",
                "result_url": "/queue/result/job_20260906120000_abc123"
            }
        }
    """
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос к API ИВЦ: bank={bank}, base={base}, job_id={job_id}")
        
        # 1. Проверяем, что банк существует
        if bank not in config.SBP_ROOT.keys():
            return create_response(
                status=config.STATUS["CONFIG_ERROR"],
                error=f"Неизвестный банк: {bank}. Доступные: {list(config.SBP_ROOT.keys())}"
            )
        
        # 2. Проверяем статус Job
        job_status = job_manager.get_job_status(bank, base, job_id)
        
        if job_status == 'not_found':
            return create_response(
                status=config.STATUS["JOB_NOT_FOUND"],
                error=f"Job не найден: {bank}@{base}@{job_id}"
            )
        
        if job_status == 'success':
            return create_response(
                status=config.STATUS["JOB_ALREADY_COMPLETED"],
                error=f"Job {job_id} уже обработан",
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "success",
                    "file_path": str(job_manager.get_success_path(bank, base, job_id))
                }
            )
        
        if job_status == 'error':
            return create_response(
                status=config.STATUS["JOB_ALREADY_COMPLETED"],
                error=f"Job {job_id} завершился с ошибкой",
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "error",
                    "file_path": str(job_manager.get_error_path(bank, base, job_id))
                }
            )
        
        # 3. Проверяем блокировку Job (защита от дублирования)
        lock_key = f"job:{bank}:{base}:{job_id}"
        if await mq_client.is_file_locked(lock_key):
            return create_response(
                status=config.STATUS["JOB_ALREADY_PROCESSING"],
                error=f"Job {job_id} уже обрабатывается"
            )
        
        # 4. Читаем Job-файл
        job_data = job_manager.read_job(bank, base, job_id)
        if job_data is None:
            return create_response(
                status=config.STATUS["FILE_NOT_FOUND"],
                error=f"Job-файл не найден: {bank}@{base}@{job_id}.json"
            )
        
        # 5. Проверяем, что банк в Job-файле совпадает с переданным
        if job_data.get('bank') != bank:
            return create_response(
                status=config.STATUS["VALIDATION_ERROR"],
                error=f"Несоответствие банка: в URL '{bank}', в файле '{job_data.get('bank')}'"
            )
        
        # 6. Проверяем, что есть файлы для обработки
        files = job_data.get('files', [])
        if not files:
            return create_response(
                status=config.STATUS["NO_FILES"],
                error="В Job нет файлов для обработки"
            )
        
        # 7. Проверяем total_requests
        total_requests = job_data.get('total_requests', 0)
        if total_requests <= 0:
            return create_response(
                status=config.STATUS["VALIDATION_ERROR"],
                error="total_requests должен быть больше 0"
            )
        
        # 8. Проверяем, что файлы существуют
        base_path = config.SBP_ROOT.pathlib(bank, base)
        
        missing_files = []
        invalid_request_ids = []
        
        for file_info in files:
            filename = file_info.get('filename')
            if not filename:
                invalid_request_ids.append(f"Файл без имени: {file_info}")
                continue
            
            file_path = base_path / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            return create_response(
                status=config.STATUS["FILE_NOT_FOUND"],
                error=f"Следующие файлы не найдены в {base_path}: {', '.join(missing_files)}"
            )
        
        if invalid_request_ids:
            return create_response(
                status=config.STATUS["VALIDATION_ERROR"],
                error=f"Некорректные записи в Job: {', '.join(invalid_request_ids[:5])}"
            )
        
        # 9. Блокируем Job
        await mq_client.lock_file(lock_key, ttl=3600)
        
        # 10. Публикуем Job в MQ
        task_id = await mq_client.publish_job(job_data)
        
        logger.info(
            f"[{stack}] Job {task_id} создан: {bank}@{base}@{job_id}, "
            f"файлов: {len(files)}, запросов: {total_requests}"
        )
        
        # 11. Возвращаем результат
        return create_response(
            status=config.STATUS["SUCCESS"],
            message="Job отправлен в очередь на обработку",
            data={
                "task_id": task_id,
                "bank": bank,
                "base": base,
                "job_id": job_id,
                "job_name": job_data.get('job_name'),
                "files_count": len(files),
                "total_requests": total_requests,
                "status_url": f"/queue/status/{task_id}",
                "result_url": f"/queue/result/{task_id}",
                "mode": "async_mq"
            }
        )
        
    except Exception as e:
        log_error_with_context(e, f"create_payload_mq {bank}/{base}/{job_id}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error=f"Внутренняя ошибка: {str(e)}"
        )


@router.get("/create_payload_mq/{bank}/{base}/{job_id}/status")
async def get_job_status_endpoint(bank: str, base: str, job_id: int):
    """
    Проверяет статус Job-файла.
    
    Args:
        bank: Имя банка
        base: Имя базы
        job_id: ID Job
    
    Returns:
        Dict: Статус Job-файла
    """
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Проверка статуса Job: {bank}@{base}@{job_id}")
        
        job_status = job_manager.get_job_status(bank, base, job_id)
        
        if job_status == 'pending':
            return create_response(
                status=config.STATUS["SUCCESS"],
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "pending",
                    "file_path": str(job_manager.get_job_file_path(bank, base, job_id)),
                    "message": "Job ожидает обработки"
                }
            )
        elif job_status == 'success':
            return create_response(
                status=config.STATUS["SUCCESS"],
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "success",
                    "file_path": str(job_manager.get_success_path(bank, base, job_id)),
                    "message": "Job успешно обработан"
                }
            )
        elif job_status == 'error':
            return create_response(
                status=config.STATUS["SUCCESS"],
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "error",
                    "file_path": str(job_manager.get_error_path(bank, base, job_id)),
                    "message": "Job завершился с ошибкой"
                }
            )
        else:
            return create_response(
                status=config.STATUS["SUCCESS"],
                data={
                    "bank": bank,
                    "base": base,
                    "job_id": job_id,
                    "status": "not_found",
                    "message": "Job не найден"
                }
            )
        
    except Exception as e:
        log_error_with_context(e, f"get_job_status {bank}/{base}/{job_id}")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error=f"Ошибка проверки статуса: {str(e)}"
        )


@router.get("/create_payload_mq/jobs/pending")
async def get_pending_jobs(bank: Optional[str] = None, base: Optional[str] = None):
    """
    Получает список ожидающих Job-файлов.
    
    Args:
        bank: Фильтр по банку (опционально)
        base: Фильтр по базе (опционально)
    
    Returns:
        Dict: Список ожидающих Job
    """
    try:
        stack = get_function_stack()
        logger.debug(f"[{stack}] Запрос списка ожидающих Job: bank={bank}, base={base}")
        
        job_files = job_manager.find_jobs(bank, base)
        
        jobs = []
        for file_path in job_files:
            job_info = job_manager.get_job_info(file_path)
            if job_info:
                # Читаем содержимое для дополнительной информации
                job_data = job_manager.read_job_by_path(file_path)
                jobs.append({
                    "file_path": str(file_path),
                    "bank": job_info.get('bank'),
                    "base": job_info.get('base'),
                    "job_id": job_info.get('job_id'),
                    "job_name": job_data.get('job_name') if job_data else None,
                    "total_requests": job_data.get('total_requests') if job_data else None,
                    "files_count": len(job_data.get('files', [])) if job_data else 0
                })
        
        return create_response(
            status=config.STATUS["SUCCESS"],
            data={
                "total": len(jobs),
                "jobs": jobs
            }
        )
        
    except Exception as e:
        log_error_with_context(e, "get_pending_jobs")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error=f"Ошибка получения списка Job: {str(e)}"
        )


@router.delete("/create_payload_mq/jobs/clean")
async def clean_old_jobs(days: int = 30):
    """
    Удаляет старые Job-файлы из папок success и error.
    
    Args:
        days: Возраст файлов в днях (по умолчанию 30)
    
    Returns:
        Dict: Результат очистки
    """
    try:
        stack = get_function_stack()
        logger.info(f"[{stack}] Запуск очистки старых Job-файлов (старше {days} дней)")
        
        deleted_success, deleted_error = job_manager.clean_old_jobs(days)
        
        return create_response(
            status=config.STATUS["SUCCESS"],
            data={
                "deleted_success": deleted_success,
                "deleted_error": deleted_error,
                "total_deleted": deleted_success + deleted_error,
                "days": days
            }
        )
        
    except Exception as e:
        log_error_with_context(e, "clean_old_jobs")
        return create_response(
            status=config.STATUS["UNKNOWN_ERROR"],
            error=f"Ошибка очистки: {str(e)}"
        )