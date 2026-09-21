import time
# modules/api_bank_client/legacy.py
"""
Старый API клиент для обратной совместимости.
Используется в create_payload (синхронный).
НЕ ИЗМЕНЯТЬ!
"""

import httpx
from typing import Dict, Any, Optional, Tuple, Union

import config
from modules.logger_config import logger
from modules.response_utils import create_response


class APIBankClient:
    """
    Старый клиент для обратной совместимости.
    Используется в create_payload (синхронный).
    Не изменять!
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
        client = await self._get_client()
        url = f"{self.base_url}{endpoint}" if endpoint else self.base_url
        
        try:
            start = time.time()
            response = await client.post(
                url,
                json=data,
                headers=self.default_headers,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            logger.debug(f"API банка POST {url} выполнен за {elapsed:.2f} сек{f' ({context})' if context else ''}")
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