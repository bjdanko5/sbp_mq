# routes/test.py
import os
import json
import shutil
import time
import httpx
from fastapi import APIRouter

import config
from modules import db
from modules.logger_config import logger, log_error_with_context, get_function_stack

router = APIRouter()


@router.get("/test_all")
async def test_all():
    """
    Полный тест всех функций:
    1. create_payload
    2. callback
    3. get_payload
    4. stop_payload
    
    Использует цифровые ID: 1, 2, 3
    """
    from modules import sbp_utils
    
    stack = get_function_stack()
    logger.info(f"[{stack}] Запуск полного теста всех функций")
    
    base = "copy_ursv"
    
    result = {
        "test": "all_functions",
        "base": base,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": []
    }
    
    # ============================================================
    # ШАГ 1: Создание тестовых файлов
    # ============================================================
    logger.debug("Шаг 1: Создание тестовых файлов")
    
    test_data = [
        {"requestId": "1", "amount": 100},
        {"requestId": "2", "amount": 200},
        {"requestId": "3", "amount": 300}
    ]
    
    # Файл для create_payload (в корне /sbp/ci/copy_ursv/)
    os.makedirs(f"/sbp/ci/{base}", exist_ok=True)
    with open(f"/sbp/ci/{base}/test_all.json", 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    # Файл для get_payload (в /sbp/ci/copy_ursv/get/)
    os.makedirs(f"/sbp/ci/{base}/get", exist_ok=True)
    with open(f"/sbp/ci/{base}/get/test_get.json", 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    # Файл для stop_payload (в /sbp/ci/copy_ursv/stop/)
    os.makedirs(f"/sbp/ci/{base}/stop", exist_ok=True)
    with open(f"/sbp/ci/{base}/stop/test_stop.json", 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
    
    result["steps"].append({
        "step": 1,
        "name": "Создание тестовых файлов",
        "status": "success",
        "files": ["test_all.json", "get/test_get.json", "stop/test_stop.json"]
    })
    
    # ============================================================
    # ШАГ 2: Тест create_payload (через httpx)
    # ============================================================
    logger.debug("Шаг 2: Тест create_payload")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8510/create_payload/{base}")
    
    step2 = {
        "step": 2,
        "name": "create_payload",
        "status_code": response.status_code,
        "response": response.json() if response.status_code == 200 else response.text
    }
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "SUCCESS":
            step2["status"] = "success"
            step2["total"] = data.get("data", {}).get("total", 0)
            step2["success_count"] = data.get("data", {}).get("success", 0)
            step2["errors"] = data.get("data", {}).get("errors", 0)
        else:
            step2["status"] = "failed"
    else:
        step2["status"] = "error"
    
    result["steps"].append(step2)
    
    # ============================================================
    # ШАГ 3: Тест callback (через httpx)
    # ============================================================
    logger.debug("Шаг 3: Тест callback")
    
    callback_data = [
        {"requestId": "1", "qrPayload": "https://example.com/qr/1"},
        {"requestId": "2", "qrPayload": "https://example.com/qr/2"},
        {"requestId": "3", "qrPayload": "https://example.com/qr/3"}
    ]
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8510/callback",
            json=callback_data,
            headers={"Content-Type": "application/json"}
        )
    
    step3 = {
        "step": 3,
        "name": "callback",
        "status_code": response.status_code,
        "response": response.json() if response.status_code == 200 else response.text
    }
    
    if response.status_code == 200:
        data = response.json()
        if base in data:
            step3["base_response"] = data[base]
            if data[base].get("status") in ["success", "warning"]:
                step3["status"] = "success"
            else:
                step3["status"] = "failed"
        else:
            step3["status"] = "success" if data.get("status") == "success" else "failed"
    else:
        step3["status"] = "error"
    
    result["steps"].append(step3)
    
    # ============================================================
    # ШАГ 4: Тест get_payload (через httpx)
    # ============================================================
    logger.debug("Шаг 4: Тест get_payload")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8510/get_payload/{base}")
    
    step4 = {
        "step": 4,
        "name": "get_payload",
        "status_code": response.status_code,
        "response": response.json() if response.status_code == 200 else response.text
    }
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "SUCCESS":
            step4["status"] = "success"
            step4["total"] = data.get("data", {}).get("total", 0)
            step4["success_count"] = data.get("data", {}).get("success", 0)
            step4["errors"] = data.get("data", {}).get("errors", 0)
        else:
            step4["status"] = "failed"
    else:
        step4["status"] = "error"
    
    result["steps"].append(step4)
    
    # ============================================================
    # ШАГ 5: Тест stop_payload (через httpx)
    # ============================================================
    logger.debug("Шаг 5: Тест stop_payload")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8510/stop_payload/{base}")
    
    step5 = {
        "step": 5,
        "name": "stop_payload",
        "status_code": response.status_code,
        "response": response.json() if response.status_code == 200 else response.text
    }
    
    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "SUCCESS":
            step5["status"] = "success"
            step5["total"] = data.get("data", {}).get("total", 0)
            step5["success_count"] = data.get("data", {}).get("success", 0)
            step5["errors"] = data.get("data", {}).get("errors", 0)
        elif data.get("status") == "NO_FILES":
            step5["status"] = "skipped"
            step5["message"] = "Нет файлов для обработки"
        else:
            step5["status"] = "failed"
    else:
        step5["status"] = "error"
    
    result["steps"].append(step5)
    
    # ============================================================
    # ШАГ 6: Очистка
    # ============================================================
    logger.debug("Шаг 6: Очистка")
    
    # Очищаем БД
    db.clear_db("4")
    
    # Удаляем тестовые файлы
    files_to_remove = [
        f"/sbp/ci/{base}/test_all.json",
        f"/sbp/ci/{base}/get/test_get.json",
        f"/sbp/ci/{base}/stop/test_stop.json",
        f"/sbp/ci/{base}/sended/test_all.json",
        f"/sbp/ci/{base}/sended/test_get.json",
        f"/sbp/ci/{base}/geted/test_get.json",
        f"/sbp/ci/{base}/stoped/test_stop.json",
        f"/sbp/ci/{base}/processing/test_all.json",
        f"/sbp/ci/{base}/processing/test_get.json",
        f"/sbp/ci/{base}/processing/test_stop.json",
    ]
    
    removed = []
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)
            removed.append(file_path)
    
    step6 = {
        "step": 6,
        "name": "Очистка",
        "status": "success",
        "files_removed": len(removed),
        "details": removed[:5] if len(removed) > 5 else removed
    }
    
    result["steps"].append(step6)
    
    # ============================================================
    # ИТОГ
    # ============================================================
    success_steps = sum(1 for s in result["steps"] if s.get("status") == "success")
    total_steps = len(result["steps"])
    
    result["summary"] = {
        "total_steps": total_steps,
        "success_steps": success_steps,
        "failed_steps": total_steps - success_steps,
        "all_success": success_steps == total_steps
    }
    
    logger.info(f"[{stack}] Тест завершён: {success_steps}/{total_steps} успешно")
    
    return result


@router.get("/debug_routes")
async def debug_routes():
    """Проверка зарегистрированных маршрутов."""
    from sbp import app
    
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path, # type: ignore
            "name": route.name, # type: ignore
            "methods": list(route.methods) if hasattr(route, "methods") else [] # type: ignore
        })
    
    mockapi_routes = [r for r in routes if "/mockapi" in r["path"]]
    
    return {
        "total_routes": len(routes),
        "mockapi_routes": mockapi_routes,
        "all_routes": routes
    }


@router.get("/test_app_routes")
async def test_app_routes():
    """Проверяет, какие роутеры в app."""
    from sbp import app
    
    routes = []
    for route in app.routes:
        if "/mockapi" in route.path: # type: ignore
            routes.append(route.path) # type: ignore
    
    return {
        "mockapi_in_app": routes,
        "total_routes": len(app.routes)
    }