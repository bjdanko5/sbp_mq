# modules/api_bank_client/bank_sb.py
"""
Клиент для банка Сбербанк (SB).

⚠️ ВАЖНО: У Сбербанка нет пакетного режима (batch). 
Запросы отправляются по одному. Чтобы избежать бана (429 Too Many Requests),
используется троттлинг: отправка пачками по 3 запроса с паузой в 1 секунду.

При фатальной ошибке (3 неудачных попытки подряд на один запрос)
выбрасывается FatalBankError, который прерывает обработку всего Job.
"""

import asyncio
import time
import httpx
from typing import Dict, Any, Optional, Tuple, Union, List

import config
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response
from .base import BaseBankClient


class FatalBankError(Exception):
    """Исключение для аварийной остановки обработки Job."""
    pass


class BankSB(BaseBankClient):
    """Клиент для банка Сбербанк."""

    def __init__(self):
        super().__init__("sb")
        self.callback_url = config.CALLBACK_URLS.get("sb", "/callback_sb")
        # Специфичные заголовки для Сбербанка (если нужны)
        self.headers.update({
            "User-Agent": "SBP-Service/1.0"
        })

    async def send_request(
        self,
        data: Union[Dict[str, Any], list],
        context: Optional[str] = None,
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """
        Отправляет POST-запросы в API Сбербанка по одному.
        Формирует единый ответ, чтобы не ломать архитектуру воркера.
        """
        # --- НАСТРОЙКИ ТРОТТЛИНГА И РЕТРАЕВ ---
        BATCH_SIZE = 3
        BATCH_DELAY = 1.0
        MAX_RETRIES = 3
        RETRY_DELAY = 2.0
        # --------------------------------------

        items = data if isinstance(data, list) else [data]
        if not items:
            return None, create_response(
                status=config.STATUS["VALIDATION_ERROR"],
                error="Пустой список данных для отправки",
                context=context,
                data={"bank": self.bank_name}
            )

        client = await self._get_client()
        url = self._build_url()
        ctx = f" ({context})" if context else ""
        
        aggregated_results = []
        
        try:
            start_total = time.time()
            
            # Разбиваем на чанки и обрабатываем
            for i in range(0, len(items), BATCH_SIZE):
                chunk = items[i:i + BATCH_SIZE]
                
                for item in chunk:
                    success = False
                    last_error = None
                    req_id = item.get("requestId") if isinstance(item, dict) else "unknown"
                    
                    # Цикл ретраев для КАЖДОГО отдельного запроса
                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            start_req = time.time()
                            response = await client.post(
                                url,
                                json=item,
                                headers=self.headers,
                                timeout=self.timeout
                            )
                            elapsed = time.time() - start_req
                            
                            # Если банк вернул 5xx, это тоже повод для ретрая
                            if response.status_code >= 500:
                                raise httpx.HTTPStatusError(
                                    f"Server error {response.status_code}", 
                                    request=response.request, 
                                    response=response
                                )

                            logger.debug(f"API банка SB POST {url} (reqId={req_id}) выполнен за {elapsed:.2f} сек{ctx}")
                            
                            try:
                                resp_json = response.json()
                            except Exception:
                                resp_json = {"raw_text": response.text}
                                
                            # Успех (200, 201, 202)
                            if response.status_code in (200, 201, 202):
                                aggregated_results.append(resp_json)
                            else:
                                # 4xx ошибки (кроме 500) не ретраим, а сразу записываем как ошибку запроса
                                aggregated_results.append({
                                    "requestId": req_id,
                                    "errorMessage": f"HTTP {response.status_code}",
                                    "response": resp_json
                                })
                            
                            success = True
                            break # Выходим из цикла ретраев

                        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as e:
                            last_error = e
                            logger.warning(
                                f"[{self.bank_name}] Попытка {attempt}/{MAX_RETRIES} "
                                f"для requestId={req_id} упала: {e}"
                            )
                            if attempt < MAX_RETRIES:
                                await asyncio.sleep(RETRY_DELAY)
                        except Exception as e:
                            # Другие ошибки (например, парсинг) — сразу прерываем
                            log_error_with_context(e, f"API банка {self.bank_name} POST error{ctx}")
                            raise FatalBankError(f"Неожиданная ошибка для requestId={req_id}: {e}")

                    # Если все попытки для текущего запроса провалились
                    if not success:
                        error_msg = f"RequestId {req_id} failed after {MAX_RETRIES} attempts: {last_error}"
                        logger.error(f"[{self.bank_name}] ❌ {error_msg}")
                        raise FatalBankError(error_msg)

                # Пауза после обработки пачки, чтобы не вылететь в бан
                if i + BATCH_SIZE < len(items):
                    logger.debug(f"Троттлинг Сбербанка: пауза {BATCH_DELAY} сек перед следующей пачкой...")
                    await asyncio.sleep(BATCH_DELAY)

            elapsed_total = time.time() - start_total
            logger.info(f"API банка SB обработал {len(items)} запросов за {elapsed_total:.2f} сек{ctx}")

            # Формируем фейковый httpx.Response с агрегированными данными.
            # Возвращаем 202, чтобы FileProcessor понял, что можно перемещать в sended.
            fake_response = httpx.Response(
                status_code=202,
                json=aggregated_results,
                request=httpx.Request("POST", url)
            )
            return fake_response, None

        except FatalBankError:
            # Пробрасываем наверх в FileProcessor для аварийной остановки Job
            raise
        except Exception as e:
            log_error_with_context(e, f"Критическая ошибка при отправке пачки в {self.bank_name}{ctx}")
            return None, create_response(
                status=config.STATUS["API_ERROR"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )

    async def send_request_patch(
        self,
        data: Union[Dict[str, Any], list],
        endpoint: str = "",
        context: Optional[str] = None,
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет PATCH-запрос в API Сбербанка (блокировка QR)."""
        client = await self._get_client()
        url = self._build_url(endpoint)
        ctx = f" ({context})" if context else ""

        try:
            start = time.time()
            response = await client.patch(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            logger.debug(f"API банка SB PATCH {url} выполнен за {elapsed:.2f} сек{ctx}")
            return response, None

        except httpx.TimeoutException as e:
            log_error_with_context(e, f"API банка {self.bank_name} PATCH timeout{ctx}")
            return None, create_response(
                status=config.STATUS["API_TIMEOUT"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )
        except httpx.ConnectError as e:
            log_error_with_context(e, f"API банка {self.bank_name} PATCH connect error{ctx}")
            return None, create_response(
                status=config.STATUS["API_CONNECTION_ERROR"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )
        except Exception as e:
            log_error_with_context(e, f"API банка {self.bank_name} PATCH error{ctx}")
            return None, create_response(
                status=config.STATUS["API_ERROR"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )

    def parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Парсит агрегированный ответ Сбербанка."""
        try:
            data = response.json() if response.content else []
            if not isinstance(data, list):
                data = [data]

            return {
                "status": "success",
                "data": data,
                "count": len(data)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "status_code": response.status_code
            }

    def get_callback_url(self) -> str:
        return self.callback_url