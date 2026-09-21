# modules/worker/file_processor.py
"""
Обработка отдельных файлов.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional

import config
from modules.logger_config import logger
from modules import db
from modules.api_bank_client import create_bank_client
from modules.request_storage import request_storage


class FileProcessor:
    """Обработчик файлов."""
    
    def __init__(self, parent):
        self.parent = parent
    
    async def process_file(
        self,
        file_path: Path,
        bank: str,
        base: str,
        paths: Dict[str, Path],
        request_ids: List[str],
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обработка одного файла для указанного банка.
        
        Args:
            file_path: Путь к файлу
            bank: Имя банка
            base: Имя базы
            paths: Словарь с путями
            request_ids: Список requestId в файле
            task_id: ID задачи (для сохранения req:{id} → task_id)
        
        Returns:
            Dict: Результат обработки
        """
        worker_id = self.parent.worker_id
        
        try:
            logger.debug(f"[Worker {worker_id}] [{bank}/{base}] Начало обработки {file_path.name}")
            
            # 1. Проверяем, что файл существует
            if not file_path.exists():
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Файл не найден: {file_path}'
                }
            
            # 2. Перемещаем в processing
            processing_file = paths['processing'] / file_path.name
            try:
                shutil.move(str(file_path), str(processing_file))
                logger.debug(f"[Worker {worker_id}] Перемещён {file_path.name} в processing")
            except OSError as e:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Ошибка перемещения в processing: {e}'
                }
            
            # 3. Читаем JSON
            try:
                with open(processing_file, 'r', encoding='utf-8') as f:
                    json_packet = json.load(f)
                logger.debug(f"[Worker {worker_id}] Прочитан {file_path.name}")
            except json.JSONDecodeError as e:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Ошибка парсинга JSON: {e}'
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Ошибка чтения файла: {e}'
                }
            
            # 4. Сохраняем в БД (SQLite) — существующее поведение
            try:
                saved_count, error = db.save_all_requests_from_json(
                    json_packet,
                    base,
                    filename=processing_file.name
                )
                if error:
                    return {
                        'status': 'error',
                        'filename': file_path.name,
                        'error': error
                    }
                logger.debug(f"[Worker {worker_id}] Сохранено {saved_count} запросов в SQLite")
            except Exception as e:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Ошибка сохранения в БД: {e}'
                }
            
            # ============================================================
            # ✅ Сохраняем req:{id} → task_id в Redis
            # ДО отправки в банк — чтобы callback точно нашёл base
            # ============================================================
            if task_id and request_ids:
                try:
                    redis_saved = await request_storage.save_requests(request_ids, task_id)
                    logger.debug(
                        f"[Worker {worker_id}] Сохранено {redis_saved} req:* → "
                        f"task_id={task_id} для {processing_file.name}"
                    )
                except Exception as e:
                    # Не прерываем обработку — fallback на SQLite спасёт
                    logger.error(
                        f"[Worker {worker_id}] Ошибка сохранения req:* в Redis: {e}"
                    )
            
            # 5. Отправляем запрос в банк через factory
            try:
                client = create_bank_client(bank)
                try:
                    response, error = await client.send_request(
                        json_packet,
                        context=processing_file.name,
                    )
                finally:
                    await client.close()
                
                if error:
                    # error — dict от create_response(); извлекаем текст
                    err_text = error.get('error') if isinstance(error, dict) else str(error)
                    return {
                        'status': 'error',
                        'filename': file_path.name,
                        'error': err_text or 'Unknown error'
                    }
                
                # ✅ Pylance: после проверки error response не None
                if response is None:
                    return {
                        'status': 'error',
                        'filename': file_path.name,
                        'error': 'Пустой ответ от API'
                    }
                logger.debug(f"[Worker {worker_id}] API ответ {response.status_code}")
            except Exception as e:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'error': f'Ошибка отправки в API: {e}'
                }
            
            # 6. Формируем результат
            if response.status_code == 202:
                # Перемещаем в sended
                try:
                    dest_path = paths['sended'] / processing_file.name
                    shutil.move(str(processing_file), str(dest_path))
                    logger.debug(f"[Worker {worker_id}] Перемещён {file_path.name} в sended")
                except OSError as e:
                    return {
                        'status': 'error',
                        'filename': file_path.name,
                        'error': f'Ошибка перемещения в sended: {e}'
                    }
                
                return {
                    'status': 'completed',
                    'filename': file_path.name,
                    'status_code': response.status_code,
                    'saved_count': saved_count,
                    'response': response.text if config.DEBUG_VERBOSE else None
                }
            else:
                return {
                    'status': 'error',
                    'filename': file_path.name,
                    'status_code': response.status_code,
                    'error': response.text[:500] if response.text else 'Unknown error',
                    'saved_count': saved_count
                }
            
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Ошибка: {e}")
            return {
                'status': 'error',
                'filename': file_path.name,
                'error': str(e)
            }