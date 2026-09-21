# modules/api_bank_client/legacy.py
"""
Старый API клиент для обратной совместимости.
Используется в create_payload, stop_payload, get_payload.
НЕ ИЗМЕНЯТЬ (кроме добавления методов)!
"""

import time
import httpx
from typing import Dict, Any, Optional, Tuple, Union

import config
from modules.logger_config import logger
from modules.response_utils import create_response


class APIBankClient:
    """
    Старый клиент для обратной совместимости.
    Используется в create_payload, stop_payload, get_payload.
    """

    def __init__(self):
        self.base_url = config.BANK_URLS.get("ci")
        self.timeout = config.REQUEST_TIMEOUT
        self.verify_ssl = config.VERIFY_SSL
        self.default_headers = config.DEFAULT_HEADERS
        self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def post(
        self,
        data: Union[Dict[str, Any], list],
        endpoint: str = "",
        context: Optional[str] = None
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет POST-запрос (обратная совместимость)."""
        return await self._request("POST", data, endpoint, context)

    async def patch(
        self,
        data: Union[Dict[str, Any], list],
        endpoint: str = "",
        context: Optional[str] = None
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет PATCH-запрос (обратная совместимость)."""
        return await self._request("PATCH", data, endpoint, context)

    async def get(
        self,
        data: Union[Dict[str, Any], list] = None,
        endpoint: str = "",
        context: Optional[str] = None
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет GET-запрос (обратная совместимость)."""
        return await self._request("GET", data, endpoint, context)

    async def _request(
        self,
        method: str,
        data: Optional[Union[Dict[str, Any], list]] = None,
        endpoint: str = "",
        context: Optional[str] = None
    ) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Универсальный метод для запросов (POST/PATCH/GET)."""
        client = await self._get_client()
        url = f"{self.base_url}{endpoint}" if endpoint else self.base_url

        # GET — без body, PATCH/POST — с json
        kwargs = {"headers": self.default_headers, "timeout": self.timeout}
        if method != "GET" and data is not None:
            kwargs["json"] = data

        try:
            start = time.time()
            response = await client.request(method, url, **kwargs)
            elapsed = time.time() - start
            ctx = f" ({context})" if context else ""
            logger.debug(f"API банка {method} {url} выполнен за {elapsed:.2f} сек{ctx}")
            return response, None

        except httpx.TimeoutException as e:
            return None, create_response(
                status=config.STATUS["API_TIMEOUT"],
                error=str(e),
                context=context
            )
        except httpx.ConnectError as e:
            return None, create_response(
                status=config.STATUS["API_CONNECTION_ERROR"],
                error=str(e),
                context=context
            )
        except Exception as e:
            return None, create_response(
                status=config.STATUS["API_ERROR"],
                error=str(e),
                context=context
            )

    def is_success(self, response: httpx.Response) -> bool:
        return response.status_code == 202


# ✅ Глобальный экземпляр для обратной совместимости
api_bank = APIBankClient()