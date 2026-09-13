# db.py
import json
import os
import time
import sqlite3
from typing import List, Dict, Optional, Any, Tuple, Union

from modules.logger_config import logger, get_function_stack, log_error_with_context
from models.schemas import PayloadItem
from config import DB_FILE, STATUS
from modules.response_utils import create_response


def init_db():
    """Инициализация базы данных"""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                requestID TEXT PRIMARY KEY,
                base TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            logger.info(f"База данных инициализирована: {DB_FILE}")
    except Exception as e:
        log_error_with_context(e, "init_db")
        raise


def get_db_connection():
    """Возвращает соединение с БД."""
    return sqlite3.connect(DB_FILE)


def save_to_db(requestID: str, base: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Сохранение запроса в БД.
    
    Returns:
        Tuple[bool, Optional[Dict[str, Any]]]:
            - (True, None) при успехе
            - (False, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT OR REPLACE INTO requests (requestID, base) VALUES (?, ?)", (requestID, base))
            conn.commit()
            logger.debug(f"{stack}: Сохранён requestID={requestID} для базы {base}")
            return True, None
    except sqlite3.Error as e:
        log_error_with_context(e, f"save_to_db requestID={requestID}")
        return False, create_response(
            status=STATUS["DB_SAVE_ERROR"],
            error=str(e),
            data={"requestID": requestID, "base": base}
        )
    except Exception as e:
        log_error_with_context(e, f"save_to_db requestID={requestID}")
        return False, create_response(
            status=STATUS["DB_SAVE_ERROR"],
            error=str(e),
            data={"requestID": requestID, "base": base}
        )


def clear_db(minRequestID: str) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Удаление запросов с ID меньше указанного.
    
    Returns:
        Tuple[int, Optional[Dict[str, Any]]]:
            - (count, None) при успехе
            - (0, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(
                "DELETE FROM requests WHERE CAST(requestID AS INTEGER) < CAST(? AS INTEGER)",
                (minRequestID,)
            )
            count = cursor.rowcount
            conn.commit()
            conn.execute("VACUUM")
            logger.debug(f"{stack}: Удалено {count} запросов с ID < {minRequestID}")
            return count, None
    except sqlite3.Error as e:
        log_error_with_context(e, f"clear_db minRequestID={minRequestID}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e),
            data={"minRequestID": minRequestID}
        )
    except Exception as e:
        log_error_with_context(e, f"clear_db minRequestID={minRequestID}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e),
            data={"minRequestID": minRequestID}
        )


def clear_one_db(requestID: str) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Удаление одного запроса по ID.
    
    Returns:
        Tuple[int, Optional[Dict[str, Any]]]:
            - (count, None) при успехе
            - (0, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(
                "DELETE FROM requests WHERE CAST(requestID AS INTEGER) = CAST(? AS INTEGER)",
                (requestID,)
            )
            count = cursor.rowcount
            conn.commit()
            logger.debug(f"{stack}: Удалён requestID={requestID}")
            return count, None
    except sqlite3.Error as e:
        log_error_with_context(e, f"clear_one_db requestID={requestID}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e),
            data={"requestID": requestID}
        )
    except Exception as e:
        log_error_with_context(e, f"clear_one_db requestID={requestID}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e),
            data={"requestID": requestID}
        )


def vacuum_db() -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Принудительно сжимает базу данных.
    
    Returns:
        Tuple[int, Optional[Dict[str, Any]]]:
            - (freed_bytes, None) при успехе
            - (0, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        size_before = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
        
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("VACUUM")
        
        size_after = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
        freed_bytes = size_before - size_after
        freed_bytes = freed_bytes if freed_bytes > 0 else 0
        
        logger.debug(f"{stack}: VACUUM выполнен, освобождено {freed_bytes} байт")
        return freed_bytes, None
        
    except sqlite3.Error as e:
        log_error_with_context(e, "vacuum_db")
        return 0, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e)
        )
    except Exception as e:
        log_error_with_context(e, "vacuum_db")
        return 0, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e)
        )


def get_from_db(requestID: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Получение base по requestID.
    
    Returns:
        Tuple[Optional[str], Optional[Dict[str, Any]]]:
            - (base, None) при успехе
            - (None, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute("SELECT base FROM requests WHERE requestID = ?", (requestID,))
            result = cursor.fetchone()
            base = result[0] if result else None
            logger.debug(f"{stack}: Получен base={base} для requestID={requestID}")
            return base, None
    except sqlite3.Error as e:
        log_error_with_context(e, f"get_from_db requestID={requestID}")
        return None, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e),
            data={"requestID": requestID}
        )
    except Exception as e:
        log_error_with_context(e, f"get_from_db requestID={requestID}")
        return None, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e),
            data={"requestID": requestID}
        )


def save_all_requests_from_json(
    json_packet: Union[Dict[str, Any], List[Dict[str, Any]]],
    base: str,
    filename: Optional[str] = None
) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """
    Сохраняет все requestId из JSON в БД.
    """
    stack = get_function_stack()
    start = time.time()
    try:
        # Приводим к списку
        if isinstance(json_packet, dict):
            items = [json_packet]
        elif isinstance(json_packet, list):
            items = json_packet
        else:
            error = f"Неверный формат JSON: ожидается dict или list, получен {type(json_packet)}"
            log_error_with_context(Exception(error), f"save_all_requests_from_json {filename}")
            return None, create_response(
                status=STATUS["JSON_ERROR"],
                error=error,
                context=filename,
                data={"filename": filename, "base": base}
            )
        
        # ✅ Собираем все requestId в список
        request_ids = []
        for item in items:
            request_id = item.get("requestId")
            if request_id:
                request_ids.append(request_id)
        
        if not request_ids:
            logger.debug(f"{stack}: Нет requestId для сохранения")
            return 0, None
        
        # ✅ Массовая вставка (один запрос)
        with sqlite3.connect(DB_FILE) as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO requests (requestID, base) VALUES (?, ?)",
                [(rid, base) for rid in request_ids]
            )
            conn.commit()
        
        saved_count = len(request_ids)
               # ✅ ФОРМИРУЕМ ОДНУ СТРУКТУРИРОВАННУЮ ЗАПИСЬ
        log_entry = {
            "event": "db_save_batch",
            "base": base,
            "filename": filename,
            "saved_count": saved_count,
            "request_ids": request_ids
        }
        
        # ✅ Пишем одну строку в лог в формате JSON
        logger.debug(f"DB_SAVE_BATCH: {json.dumps(log_entry, ensure_ascii=False)}")
        logger.debug(f"{stack}: Сохранено {saved_count} запросов для базы {base}")
        elapsed = time.time() - start
        logger.debug(f"Функция {"save_all_requests_from_json"} выполнен за {elapsed:.2f} сек")
        return saved_count, None
        
    except sqlite3.IntegrityError as e:
        log_error_with_context(e, f"save_all_requests_from_json {filename}")
        return None, create_response(
            status=STATUS["DB_SAVE_ERROR"],
            error=str(e),
            context=filename,
            data={"filename": filename, "base": base}
        )
    except sqlite3.OperationalError as e:
        log_error_with_context(e, f"save_all_requests_from_json {filename}")
        return None, create_response(
            status=STATUS["DB_SAVE_ERROR"],
            error=str(e),
            context=filename,
            data={"filename": filename, "base": base}
        )
    except Exception as e:
        log_error_with_context(e, f"save_all_requests_from_json {filename}")
        return None, create_response(
            status=STATUS["DB_SAVE_ERROR"],
            error=str(e),
            context=filename,
            data={"filename": filename, "base": base}
        )

def get_bases_for_requests(request_ids: List[str]) -> Tuple[Dict[str, Optional[str]], Optional[Dict[str, Any]]]:
    """
    Возвращает словарь {requestId: base} для всех requestId из списка.
    Делает один SQL-запрос.
    
    Returns:
        Tuple[Dict[str, Optional[str]], Optional[Dict[str, Any]]]:
            - (result_dict, None) при успехе
            - ({}, error_response) при ошибке
    """
    stack = get_function_stack()
    
    if not request_ids:
        return {}, None
    
    try:
        placeholders = ",".join(["?"] * len(request_ids))
        query = f"SELECT requestID, base FROM requests WHERE requestID IN ({placeholders})"
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(query, request_ids)
            rows = cursor.fetchall()
        
        result = {row[0]: row[1] for row in rows}
        full_result = {request_id: result.get(request_id) for request_id in request_ids}
        
        logger.debug(f"{stack}: Получены базы для {len(request_ids)} запросов")
        return full_result, None
        
    except sqlite3.Error as e:
        log_error_with_context(e, f"get_bases_for_requests count={len(request_ids)}")
        return {}, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e)
        )
    except Exception as e:
        log_error_with_context(e, f"get_bases_for_requests count={len(request_ids)}")
        return {}, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e)
        )


def clear_multiple_db(request_ids: List[str]) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Удаление нескольких запросов одной транзакцией.
    
    Returns:
        Tuple[int, Optional[Dict[str, Any]]]:
            - (count, None) при успехе
            - (0, error_response) при ошибке
    """
    stack = get_function_stack()
    
    if not request_ids:
        return 0, None
    
    try:
        placeholders = ','.join(['?'] * len(request_ids))
        query = f"DELETE FROM requests WHERE requestID IN ({placeholders})"
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.execute(query, request_ids)
            deleted_count = cursor.rowcount
            conn.commit()
        
        logger.debug(f"{stack}: Удалено {deleted_count} запросов")
        return deleted_count, None
        
    except sqlite3.Error as e:
        log_error_with_context(e, f"clear_multiple_db count={len(request_ids)}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e)
        )
    except Exception as e:
        log_error_with_context(e, f"clear_multiple_db count={len(request_ids)}")
        return 0, create_response(
            status=STATUS["DB_CLEAR_ERROR"],
            error=str(e)
        )


def group_payload_by_base(payload: List[PayloadItem]) -> Tuple[Dict[str, List[dict]], Optional[Dict[str, Any]]]:
    """
    Группирует элементы payload по базам 1C.
    
    Returns:
        Tuple[Dict[str, List[dict]], Optional[Dict[str, Any]]]:
            - (grouped_dict, None) при успехе
            - ({}, error_response) при ошибке
    """
    stack = get_function_stack()
    
    try:
        request_ids = [item.requestId for item in payload]
        request_id_to_base, error = get_bases_for_requests(request_ids)
        
        if error:
            return {}, error
        
        base_to_payload = {}
        for item in payload:
            base = request_id_to_base.get(item.requestId)
            if base:
                if base not in base_to_payload:
                    base_to_payload[base] = []
                base_to_payload[base].append(item.model_dump())
        
        logger.debug(f"{stack}: Сгруппировано {len(payload)} запросов по {len(base_to_payload)} базам")
        return base_to_payload, None
        
    except Exception as e:
        log_error_with_context(e, f"group_payload_by_base count={len(payload)}")
        return {}, create_response(
            status=STATUS["DB_ERROR"],
            error=str(e)
        )


# Инициализация БД при импорте
init_db()