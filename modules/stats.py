# modules/stats.py
import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from config import STATS_LOG_FILE
from modules.logger_config import logger, get_function_stack


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Парсит строку лога и извлекает информацию о запросах.
    
    Returns:
        Dict с данными или None
    """
    pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)$'
    match = re.match(pattern, line)
    
    if not match:
        return None
    
    timestamp_str, level, message = match.groups()
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    
    data = {
        'timestamp': timestamp,
        'level': level,
        'message': message,
        'type': None,
        'base': None,
        'filename': None,
        'files_count': None,
        'requests_count': None,
        'requests_saved': None,
        'success': None,
        'errors': None,
        'api_error': None,
        'api_error_type': None,
        'api_method': None,
        'api_url': None,
        'request_ids': []
    }
    
    # ============================================================
    # 1. DB_SAVE_BATCH (структурированная запись)
    # ============================================================
    if 'DB_SAVE_BATCH:' in message:
        try:
            json_str = message.split('DB_SAVE_BATCH: ')[1]
            data_batch = json.loads(json_str)
            data['type'] = 'db_save_batch'
            data['base'] = data_batch.get('base')
            data['filename'] = data_batch.get('filename')
            data['requests_saved'] = data_batch.get('saved_count', 0)
            data['requests_count'] = data['requests_saved']
            data['request_ids'] = data_batch.get('request_ids', [])
            return data
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    
    # ============================================================
    # 2. CALLBACK_DELETE (структурированная запись)
    # ============================================================
    if 'CALLBACK_DELETE:' in message:
        try:
            json_str = message.split('CALLBACK_DELETE: ')[1]
            data_batch = json.loads(json_str)
            data['type'] = 'callback_delete'
            data['base'] = data_batch.get('base')
            data['requests_count'] = data_batch.get('deleted_count', 0)
            data['request_ids'] = data_batch.get('request_ids', [])
            return data
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    
    # ============================================================
    # 3. GET_PAYLOAD_DELETE (структурированная запись)
    # ============================================================
    if 'GET_PAYLOAD_DELETE:' in message:
        try:
            json_str = message.split('GET_PAYLOAD_DELETE: ')[1]
            data_batch = json.loads(json_str)
            data['type'] = 'get_payload_delete'
            data['base'] = data_batch.get('base')
            data['filename'] = data_batch.get('filename')
            data['requests_count'] = data_batch.get('deleted_count', 0)
            data['request_ids'] = data_batch.get('request_ids', [])
            return data
        except (json.JSONDecodeError, IndexError, KeyError):
            pass
    
    # ============================================================
    # 4. create_payload: Найдено X JSON файлов для базы 'Y'
    # ============================================================
    if 'Найдено' in message and 'JSON файлов' in message:
        data['type'] = 'create_payload'
        match_count = re.search(r'Найдено (\d+) JSON файлов', message)
        if match_count:
            data['files_count'] = int(match_count.group(1))
        match_base = re.search(r"базы '([^']+)'", message)
        if match_base:
            data['base'] = match_base.group(1)
        return data
    
    # ============================================================
    # 5. Перемещён X.json в processing
    # ============================================================
    if 'Перемещён' in message and 'processing' in message:
        data['type'] = 'file_moved_processing'
        match_file = re.search(r'Перемещён ([^\s]+)\.json', message)
        if match_file:
            data['filename'] = match_file.group(1) + '.json'
        match_base = re.search(r"базы '([^']+)'", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 6. Прочитан X.json (только с базой)
    # ============================================================
    if 'Прочитан' in message:
        data['type'] = 'file_read'
        match_file = re.search(r'Прочитан ([^\s]+)\.json', message)
        if match_file:
            data['filename'] = match_file.group(1) + '.json'
        match_base = re.search(r"базы '([^']+)'", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 7. Сохранено X запросов для базы Y (старый формат)
    # ============================================================
    if 'Сохранено' in message and 'запросов' in message and 'DB_SAVE_BATCH' not in message:
        data['type'] = 'db_save_old'
        match_count = re.search(r'Сохранено (\d+) запросов', message)
        if match_count:
            data['requests_saved'] = int(match_count.group(1))
            data['requests_count'] = data['requests_saved']
        match_base = re.search(r"базы ([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        match_file = re.search(r"filename=([^\s,}]+)", message)
        if match_file:
            data['filename'] = match_file.group(1)
        return data
    
    # ============================================================
    # 8. API банка POST/GET/PATCH
    # ============================================================
    if 'API банка' in message and ('POST' in message or 'GET' in message or 'PATCH' in message):
        data['type'] = 'api_request'
        match_url = re.search(r'(POST|GET|PATCH)\s+(https?://[^\s]+)', message)
        if match_url:
            data['api_method'] = match_url.group(1)
            data['api_url'] = match_url.group(2)
        match_file = re.search(r'\(([^)]+)\)', message)
        if match_file:
            data['filename'] = match_file.group(1)
        match_base = re.search(r"базы '([^']+)'", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 9. API ошибка
    # ============================================================
    if 'API банка' in message and ('ConnectTimeout' in message or 'ReadTimeout' in message or 'ERROR' in message):
        data['type'] = 'api_error'
        if 'ConnectTimeout' in message:
            data['api_error_type'] = 'ConnectTimeout'
            data['api_error'] = 'Ошибка подключения к API банка'
        elif 'ReadTimeout' in message:
            data['api_error_type'] = 'ReadTimeout'
            data['api_error'] = 'Превышено время ожидания ответа от API банка'
        else:
            data['api_error_type'] = 'Unknown'
            data['api_error'] = 'Неизвестная ошибка API'
        match_file = re.search(r'API банка\s+[^\s]+\s+([^\s]+\.json)', message)
        if match_file:
            data['filename'] = match_file.group(1)
        match_base = re.search(r"базы '([^']+)'", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 10. [API_TIMEOUT] context=file.json
    # ============================================================
    if '[API_TIMEOUT]' in message:
        data['type'] = 'api_timeout'
        match_file = re.search(r'context=([^\s]+)', message)
        if match_file:
            data['filename'] = match_file.group(1)
        match_base = re.search(r"base=([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 11. [API_ERROR] base=... total=... success=... errors=...
    # ============================================================
    if '[API_ERROR]' in message and 'base=' in message:
        data['type'] = 'api_error_summary'
        match_base = re.search(r'base=([^\s]+)', message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        match_total = re.search(r'total=(\d+)', message)
        if match_total:
            data['files_count'] = int(match_total.group(1))
        match_success = re.search(r'success=(\d+)', message)
        if match_success:
            data['success'] = int(match_success.group(1))
        match_errors = re.search(r'errors=(\d+)', message)
        if match_errors:
            data['errors'] = int(match_errors.group(1))
        return data
    
    # ============================================================
    # 12. SOAP ProcessPayload вызван успешно для базы ...
    # ============================================================
    if 'SOAP ProcessPayload вызван успешно' in message:
        data['type'] = 'soap_success'
        match_base = re.search(r"для базы ([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            match_base = re.search(r"базы '([^']+)'", message)
            if match_base:
                data['base'] = match_base.group(1)
            else:
                return None
        return data
    
    # ============================================================
    # 13. SOAP ошибка
    # ============================================================
    if 'SOAP ProcessPayload не выполнен' in message:
        data['type'] = 'soap_error'
        match_base = re.search(r"для базы ([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            match_base = re.search(r"базы '([^']+)'", message)
            if match_base:
                data['base'] = match_base.group(1)
            else:
                return None
        match_file = re.search(r"filename=([^\s,}]+)", message)
        if match_file:
            data['filename'] = match_file.group(1)
        return data
    
    # ============================================================
    # 14. Удалено X запросов из базы Y (старый формат)
    # ============================================================
    if 'Удалено' in message and 'запросов из базы' in message and 'DELETE' not in message:
        data['type'] = 'db_delete_old'
        match_count = re.search(r'Удалено (\d+) запросов', message)
        if match_count:
            data['requests_count'] = int(match_count.group(1))
        match_base = re.search(r"базы ([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 15. [SUCCESS] context=file.json
    # ============================================================
    if '[SUCCESS]' in message and 'context=' in message and 'total=' not in message:
        data['type'] = 'file_success'
        match_file = re.search(r'context=([^\s]+)', message)
        if match_file:
            data['filename'] = match_file.group(1)
        match_base = re.search(r"base=([^\s]+)", message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        return data
    
    # ============================================================
    # 16. [SUCCESS] base=... total=... success=... errors=...
    # ============================================================
    if '[SUCCESS]' in message and 'total=' in message and 'context=' not in message:
        data['type'] = 'base_summary'
        match_base = re.search(r'base=([^\s]+)', message)
        if match_base:
            data['base'] = match_base.group(1)
        else:
            return None
        match_total = re.search(r'total=(\d+)', message)
        if match_total:
            data['files_count'] = int(match_total.group(1))
        match_success = re.search(r'success=(\d+)', message)
        if match_success:
            data['success'] = int(match_success.group(1))
        match_errors = re.search(r'errors=(\d+)', message)
        if match_errors:
            data['errors'] = int(match_errors.group(1))
        return data
    
    return data


def get_stats(
    hours: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    base: Optional[str] = None
) -> Dict[str, Any]:
    stack = get_function_stack()
    logger.debug(f"{stack}: Запрос статистики")
    
    now = datetime.now()
    
    if hours:
        start_dt = now - timedelta(hours=hours)
        end_dt = now
    elif start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') if end_date else now
    else:
        start_dt = now - timedelta(hours=24)
        end_dt = now
    
    stats = {
        'period': {
            'from': start_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'to': end_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'hours': hours if hours else round((end_dt - start_dt).total_seconds() / 3600, 1)
        },
        'bases': {},
        'files': {},
        'errors': [],
        'total': {
            'requests': 0,
            'success': 0,
            'errors': 0,
            'files_processed': 0,
            'files_found': 0,
            'requests_saved': 0,
            'api_errors': 0,
            'api_timeouts': 0,
            'soap_calls': 0,
            'soap_errors': 0,
            'db_deletes': 0
        }
    }
    
    if not os.path.exists(STATS_LOG_FILE):
        return {
            'status': 'error',
            'error': f'Лог-файл не найден: {STATS_LOG_FILE}',
            'stats': stats
        }
    
    with open(STATS_LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            data = parse_log_line(line)
            if not data:
                continue
            
            if data['timestamp'] < start_dt or data['timestamp'] > end_dt:
                continue
            
            if base and data.get('base') and data['base'] != base:
                continue
            
            base_name = data.get('base') or 'unknown'
            if base_name not in stats['bases']:
                stats['bases'][base_name] = {
                    'requests': 0,
                    'success': 0,
                    'errors': 0,
                    'files_processed': 0,
                    'files_found': 0,
                    'requests_saved': 0,
                    'api_errors': 0,
                    'api_timeouts': 0,
                    'files': [],
                    'files_detail': [],
                    'soap_calls': 0,
                    'soap_errors': 0,
                    'db_deletes': 0
                }
            
            filename = data.get('filename')
            if filename:
                if filename not in stats['files']:
                    stats['files'][filename] = {
                        'base': base_name,
                        'requests': 0,
                        'requests_saved': 0,
                        'success': False,
                        'processed': False,
                        'api_error': False,
                        'api_error_type': None,
                        'moved_to_processing': False,
                        'moved_to_sended': False,
                        'moved_to_geted': False,
                        'moved_to_stoped': False,
                        'api_method': None,
                        'api_url': None,
                        'request_ids': []
                    }
                else:
                    if stats['files'][filename]['base'] == 'unknown' and base_name != 'unknown':
                        stats['files'][filename]['base'] = base_name
                
                if data.get('api_method'):
                    stats['files'][filename]['api_method'] = data['api_method']
                    stats['files'][filename]['api_url'] = data['api_url']
                
                if data.get('request_ids'):
                    stats['files'][filename]['request_ids'] = data['request_ids']
            
            # ============================================================
            # СБОР СТАТИСТИКИ
            # ============================================================
            
            # 1. Найдено файлов
            if data['type'] == 'create_payload' and data.get('files_count'):
                stats['total']['files_found'] += data['files_count']
                stats['bases'][base_name]['files_found'] += data['files_count']
            
            # 2. Файл перемещён в processing
            if data['type'] == 'file_moved_processing' and data.get('filename'):
                stats['files'][data['filename']]['moved_to_processing'] = True
                if stats['files'][data['filename']]['base'] == 'unknown' and base_name != 'unknown':
                    stats['files'][data['filename']]['base'] = base_name
            
            # 3. Файл прочитан
            if data['type'] == 'file_read' and data.get('filename'):
                stats['files'][data['filename']]['processed'] = True
                if stats['files'][data['filename']]['base'] == 'unknown' and base_name != 'unknown':
                    stats['files'][data['filename']]['base'] = base_name
            
            # 4. Сохранение в БД (структурированное)
            if data['type'] == 'db_save_batch' and data.get('requests_saved'):
                saved = data['requests_saved']
                stats['total']['requests_saved'] += saved
                stats['total']['requests'] += saved
                stats['bases'][base_name]['requests_saved'] += saved
                stats['bases'][base_name]['requests'] += saved
                
                if data.get('filename'):
                    if data['filename'] not in stats['files']:
                        stats['files'][data['filename']] = {
                            'base': base_name,
                            'requests': 0,
                            'requests_saved': 0,
                            'success': False,
                            'processed': False,
                            'api_error': False,
                            'api_error_type': None,
                            'moved_to_processing': False,
                            'moved_to_sended': False,
                            'moved_to_geted': False,
                            'moved_to_stoped': False,
                            'api_method': None,
                            'api_url': None,
                            'request_ids': []
                        }
                    stats['files'][data['filename']]['base'] = base_name
                    stats['files'][data['filename']]['requests_saved'] += saved
                    stats['files'][data['filename']]['requests'] += saved
                    if data.get('request_ids'):
                        stats['files'][data['filename']]['request_ids'] = data['request_ids']
            
            # 5. Сохранение в БД (старый формат)
            if data['type'] == 'db_save_old' and data.get('requests_saved'):
                saved = data['requests_saved']
                stats['total']['requests_saved'] += saved
                stats['total']['requests'] += saved
                stats['bases'][base_name]['requests_saved'] += saved
                stats['bases'][base_name]['requests'] += saved
                if data.get('filename') and data['filename'] in stats['files']:
                    stats['files'][data['filename']]['requests_saved'] += saved
                    stats['files'][data['filename']]['requests'] += saved
            
            # 6. API ошибка
            if data['type'] == 'api_error':
                stats['total']['api_errors'] += 1
                stats['bases'][base_name]['api_errors'] += 1
                if data.get('filename') and data['filename'] in stats['files']:
                    stats['files'][data['filename']]['api_error'] = True
                    stats['files'][data['filename']]['api_error_type'] = data.get('api_error_type')
                    if stats['files'][data['filename']]['base'] == 'unknown' and base_name != 'unknown':
                        stats['files'][data['filename']]['base'] = base_name
                
                stats['errors'].append({
                    'timestamp': data['timestamp'].strftime('%H:%M:%S'),
                    'file': data.get('filename') or 'unknown',
                    'base': base_name,
                    'error': data.get('api_error') or 'API Error',
                    'error_type': data.get('api_error_type') or 'Unknown'
                })
            
            # 7. API таймаут
            if data['type'] == 'api_timeout':
                stats['total']['api_timeouts'] += 1
                stats['bases'][base_name]['api_timeouts'] += 1
                stats['errors'].append({
                    'timestamp': data['timestamp'].strftime('%H:%M:%S'),
                    'file': data.get('filename') or 'unknown',
                    'base': base_name,
                    'error': 'Таймаут API',
                    'error_type': 'API_TIMEOUT'
                })
            
            # 8. SOAP успех
            if data['type'] == 'soap_success':
                stats['total']['soap_calls'] += 1
                if data.get('base') and data['base'] != 'unknown':
                    soap_base = data['base']
                else:
                    soap_base = base_name
                stats['bases'][soap_base]['soap_calls'] += 1
            
            # 9. SOAP ошибка
            if data['type'] == 'soap_error':
                stats['total']['soap_errors'] += 1
                stats['bases'][base_name]['soap_errors'] += 1
                stats['errors'].append({
                    'timestamp': data['timestamp'].strftime('%H:%M:%S'),
                    'file': data.get('filename') or 'unknown',
                    'base': base_name,
                    'error': 'SOAP ошибка',
                    'error_type': 'SOAP_ERROR'
                })
            
            # 10. Удаление из БД (структурированное)
            if data['type'] in ['callback_delete', 'get_payload_delete'] and data.get('requests_count'):
                deleted = data['requests_count']
                stats['total']['db_deletes'] += deleted
                stats['bases'][base_name]['db_deletes'] += deleted
                if data.get('filename') and data['filename'] in stats['files']:
                    stats['files'][data['filename']]['requests'] -= deleted
            
            # 11. Удаление из БД (старый формат)
            if data['type'] == 'db_delete_old' and data.get('requests_count'):
                stats['total']['db_deletes'] += data['requests_count']
                stats['bases'][base_name]['db_deletes'] += data['requests_count']
            
            # 12. Успешная обработка файла
            if data['type'] == 'file_success' and data.get('filename'):
                stats['files'][data['filename']]['success'] = True
                stats['files'][data['filename']]['processed'] = True
                stats['total']['files_processed'] += 1
                if data.get('base') and data['base'] != 'unknown':
                    base_name = data['base']
                    stats['files'][data['filename']]['base'] = base_name
                stats['bases'][base_name]['files_processed'] += 1
                if stats['files'][data['filename']]['base'] == 'unknown' and base_name != 'unknown':
                    stats['files'][data['filename']]['base'] = base_name
            
            # 13. Итог по базе (SUCCESS)
            if data['type'] == 'base_summary' and data.get('files_count'):
                stats['total']['requests'] += data.get('requests_count') or 0
                stats['total']['success'] += data.get('success') or 0
                stats['total']['errors'] += data.get('errors') or 0
                stats['bases'][base_name]['requests'] += data.get('requests_count') or 0
                stats['bases'][base_name]['success'] += data.get('success') or 0
                stats['bases'][base_name]['errors'] += data.get('errors') or 0
            
            # 14. API ошибка суммарная
            if data['type'] == 'api_error_summary':
                stats['bases'][base_name]['errors'] += data.get('errors') or 0
                stats['total']['requests'] += data.get('files_count') or 0
                stats['bases'][base_name]['requests'] += data.get('files_count') or 0
    
    # Добавляем список файлов по базам
    for base_name in stats['bases']:
        stats['bases'][base_name]['files'] = [
            f for f, info in stats['files'].items() 
            if info['base'] == base_name
        ]
    
    # Добавляем детали файлов в базы
    for base_name in stats['bases']:
        base_files = []
        for filename, file_data in stats['files'].items():
            if file_data['base'] == base_name:
                status_text = '✅ Успешно' if file_data.get('success') else '❌ Ошибка' if file_data.get('api_error') else '⏳ В обработке'
                base_files.append({
                    'name': filename,
                    'requests': file_data.get('requests', 0),
                    'requests_saved': file_data.get('requests_saved', 0),
                    'processed': file_data.get('processed', False),
                    'success': file_data.get('success', False),
                    'api_error': file_data.get('api_error', False),
                    'api_error_type': file_data.get('api_error_type'),
                    'api_method': file_data.get('api_method'),
                    'request_ids': file_data.get('request_ids', []),
                    'status': status_text
                })
        stats['bases'][base_name]['files_detail'] = base_files
    
    # Определяем статус API
    total_api_errors = stats['total']['api_errors'] + stats['total']['api_timeouts']
    if total_api_errors == 0:
        stats['api_status'] = '✅ Доступен'
    elif total_api_errors > 0 and stats['total']['requests_saved'] > 0:
        stats['api_status'] = '⚠️ Частично доступен'
    else:
        stats['api_status'] = '❌ Недоступен'
    
    # Удаляем пустые базы
    for base_name in list(stats['bases'].keys()):
        base_data = stats['bases'][base_name]
        if (base_data.get('requests', 0) == 0 and 
            base_data.get('files_found', 0) == 0 and 
            base_data.get('requests_saved', 0) == 0 and
            base_data.get('files_processed', 0) == 0 and
            len(base_data.get('files_detail', [])) == 0):
            del stats['bases'][base_name]
    
    return {
        'status': 'success',
        'stats': stats
    }
