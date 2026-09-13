# modules/worker/job_processor.py
"""
Обработка Job (последовательная обработка файлов).

Результат формируется в том же формате, что и задание,
с добавлением информации об обработке.

Прогресс сохраняется в Redis после каждого файла,
полный результат — только в конце.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

import config
from modules.logger_config import logger


class JobProcessor:
    """Обработчик Job."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def process_job(
        self,
        bank: str,
        base: str,
        job_id: int,
        files: list,
        job_data: Optional[dict] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обработка Job (последовательная обработка файлов).
        
        Args:
            bank: Имя банка
            base: Имя базы
            job_id: ID Job
            files: Список файлов в Job
            job_data: Полные данные Job (для сохранения реквизитов)
            task_id: ID задачи в Redis (для сохранения прогресса и req:*)
        
        Returns:
            Dict: Результат обработки (симметричный заданию)
        """
        from modules.mq_client import mq_client
        
        worker_id = self.parent.worker_id
        logger.debug(f"[Worker {worker_id}] Начало обработки Job {job_id} для банка {bank}")
        
        started_at = datetime.now().isoformat()
        
        # ✅ Формируем результат в том же формате, что и задание
        result = {
            "bank": bank,
            "base": base,
            "job_id": job_id,
            "job_name": job_data.get('job_name', '') if job_data else '',
            "created_at": job_data.get('created_at', '') if job_data else '',
            "started_at": started_at,
            "finished_at": None,
            "files": [],
            "total_requests": job_data.get('total_requests', 0) if job_data else 0,
            "status": "processing",
            "summary": {
                "total_files": len(files),
                "processed_files": 0,
                "success_files": 0,
                "error_files": 0,
                "total_requests": 0,
                "success_requests": 0,
                "error_requests": 0
            }
        }
        
        # ✅ Сохраняем начальный прогресс
        if task_id:
            await self._save_progress(task_id, result, files, started_at, None)
        
        # Получаем пути для банка
        base_path = config.SBP_ROOT.pathlib(bank, base)
        
        paths = {
            'base': base_path,
            'processing': base_path / 'processing',
            'sended': base_path / 'sended',
            'get': base_path / 'get',
            'geted': base_path / 'geted',
            'stop': base_path / 'stop',
            'stoped': base_path / 'stoped'
        }
        
        # Создаём папки
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"[Worker {worker_id}] Пути для банка {bank}: {paths['base']}")
        
        has_error = False
        
        for file_info in files:
            filename = file_info.get('filename') or ''
            request_ids = file_info.get('request_ids', [])
            count = file_info.get('count', len(request_ids))
            
            logger.debug(f"[Worker {worker_id}] Обработка файла {filename} (банк: {bank})")
            
            # ✅ Формируем запись файла в том же формате + результат
            file_result = {
                "filename": filename,
                "count": count,
                "request_ids": request_ids,
                "status": "pending",
                "status_code": None,
                "saved_count": 0,
                "processed_at": None,
                "error": None,
                "response": []
            }
            
            try:
                file_path = paths['base'] / filename
                
                # ✅ Обрабатываем файл (передаём task_id для сохранения req:*)
                result_data = await self.parent.file_processor.process_file(
                    file_path=file_path,
                    bank=bank,
                    base=base,
                    paths=paths,
                    request_ids=request_ids,
                    task_id=task_id
                )
                
                # ✅ Обогащаем file_result данными обработки
                file_result['status'] = result_data.get('status', 'error')
                file_result['status_code'] = result_data.get('status_code')
                file_result['saved_count'] = result_data.get('saved_count', 0)
                file_result['processed_at'] = datetime.now().isoformat()
                
                if result_data.get('error'):
                    file_result['error'] = result_data['error']
                
                # ✅ Парсим response в структурированный вид
                response_text = result_data.get('response')
                if response_text:
                    try:
                        file_result['response'] = json.loads(response_text) if isinstance(response_text, str) else response_text
                    except (json.JSONDecodeError, TypeError):
                        file_result['response'] = response_text
                
                # ✅ Обновляем сводку
                result['summary']['processed_files'] += 1
                result['summary']['total_requests'] += count
                
                if file_result['status'] in ['completed', 'success']:
                    result['summary']['success_files'] += 1
                    result['summary']['success_requests'] += count
                else:
                    result['summary']['error_files'] += 1
                    result['summary']['error_requests'] += count
                    has_error = True
                    logger.error(f"[Worker {worker_id}] Ошибка в файле {filename}, Job {job_id} прерван")
                
                result['files'].append(file_result)
                
                # ✅ Сохраняем ПРОГРЕСС после каждого файла (краткий!)
                if task_id:
                    await self._save_progress(
                        task_id, result, files, started_at,
                        current_file=filename if not has_error else None
                    )
                
                if has_error:
                    break
                    
            except Exception as e:
                file_result['status'] = 'error'
                file_result['error'] = str(e)
                file_result['processed_at'] = datetime.now().isoformat()
                result['files'].append(file_result)
                result['summary']['error_files'] += 1
                result['summary']['error_requests'] += count
                has_error = True
                logger.error(f"[Worker {worker_id}] Критическая ошибка в файле {filename}: {e}")
                
                # ✅ Сохраняем прогресс даже при ошибке
                if task_id:
                    await self._save_progress(task_id, result, files, started_at, current_file=None)
                
                break
        
        # ✅ Финальный статус
        result['status'] = 'error' if has_error else 'completed'
        result['finished_at'] = datetime.now().isoformat()
        
        logger.info(
            f"[Worker {worker_id}] Job {job_id} завершён: {result['status']}, "
            f"файлов: {result['summary']['processed_files']}/{result['summary']['total_files']}, "
            f"запросов: {result['summary']['success_requests']}/{result['summary']['total_requests']}"
        )
        
        return result
    
    async def _save_progress(
        self,
        task_id: str,
        result: Dict[str, Any],
        all_files: list,
        started_at: str,
        current_file: Optional[str] = None
    ) -> None:
        """
        Сохраняет краткий прогресс задачи в Redis.
        
        Args:
            task_id: ID задачи
            result: Текущий результат
            all_files: Список всех файлов
            started_at: Время старта
            current_file: Текущий обрабатываемый файл (может быть None)
        """
        from modules.mq_client import mq_client
        
        try:
            total = len(all_files)
            processed = result['summary']['processed_files']
            percent = int((processed / total * 100) if total > 0 else 0)
            
            progress = {
                "task_id": task_id,
                "status": "processing",
                "bank": result['bank'],
                "base": result['base'],
                "job_id": result['job_id'],
                "job_name": result['job_name'],
                "total_files": total,
                "processed_files": processed,
                "success_files": result['summary']['success_files'],
                "error_files": result['summary']['error_files'],
                "current_file": current_file,
                "progress_percent": percent,
                "started_at": started_at
            }
            
            await mq_client.save_progress(task_id, progress)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения прогресса: {e}")