# modules/api_bank_client/bank_sb.py
"""
Клиент для банка Сбербанк (SB).

⚠️ В РАЗРАБОТКЕ — требует уточнения API.
"""

import time
import httpx
from typing import Dict, Any, Optional, Tuple, Union

import config
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response
from .base import BaseBankClient


class BankSB(BaseBankClient):
    """Клиент для банка Сбербанк."""

    def __init__(self):
        super().__init__("sb")
        self.callback_url = config.CALLBACK_URLS.get("sb", "/callback_sb")
        # Специфичные заголовки для Сбербанка
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SBP-Service/1.0"
        }

    async def send_request(
        self,
        data: Union[Dict[str, Any], list],
        context: Optional[str] = None,
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет POST-запрос в API Сбербанка (создание QR)."""
        client = await self._get_client()
        url = self._build_url()
        ctx = f" ({context})" if context else ""

        try:
            start = time.time()
            response = await client.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            logger.debug(f"API банка SB POST {url} выполнен за {elapsed:.2f} сек{ctx}")
            return response, None

        except httpx.TimeoutException as e:
            log_error_with_context(e, f"API банка {self.bank_name} POST timeout{ctx}")
            return None, create_response(
                status=config.STATUS["API_TIMEOUT"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )
        except httpx.ConnectError as e:
            log_error_with_context(e, f"API банка {self.bank_name} POST connect error{ctx}")
            return None, create_response(
                status=config.STATUS["API_CONNECTION_ERROR"],
                error=str(e),
                context=context,
                data={"bank": self.bank_name}
            )
        except Exception as e:
            log_error_with_context(e, f"API банка {self.bank_name} POST error{ctx}")
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
        """Парсит ответ Сбербанка."""
        try:
            data = response.json() if response.content else None
            if isinstance(data, dict):
                if "data" in data:
                    return {
                        "status": "success" if response.status_code == 200 else "error",
                        "data": data.get("data"),
                        "meta": data.get("meta", {}),
                        "status_code": response.status_code
                    }
                return {
                    "status": "success" if response.status_code == 200 else "error",
                    "data": data,
                    "status_code": response.status_code
                }
            return {
                "status": "success" if response.status_code == 200 else "error",
                "data": data,
                "count": len(data) if isinstance(data, list) else 0,
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "status_code": response.status_code
            }

    def get_callback_url(self) -> str:
        return self.callback_url