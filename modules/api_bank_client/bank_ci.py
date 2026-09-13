# modules/api_bank_client/bank_ci.py
"""
Клиент для банка Центринвест (CI).
"""

import time
import httpx
from typing import Dict, Any, Optional, Tuple, Union

import config
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response
from .base import BaseBankClient


class BankCI(BaseBankClient):
    """Клиент для банка Центринвест."""
    
    def __init__(self):
        super().__init__("ci")
        self.callback_url = config.CALLBACK_URLS.get("ci", "/callback")
    
    async def send_request(self, data: Union[Dict[str, Any], list]) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """Отправляет POST-запрос в API Центринвеста."""
        client = await self._get_client()
        url = self._build_url()
        
        try:
            start = time.time()
            response = await client.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            logger.debug(f"API банка POST {url} выполнен за {elapsed:.2f} сек")
            return response, None
            
        except httpx.TimeoutException as e:
            log_error_with_context(e, f"API банка {self.bank_name} timeout")
            return None, create_response(
                status=config.STATUS["API_TIMEOUT"],
                error=str(e),
                data={"bank": self.bank_name}
            )
        except httpx.ConnectError as e:
            log_error_with_context(e, f"API банка {self.bank_name} connect error")
            return None, create_response(
                status=config.STATUS["API_CONNECTION_ERROR"],
                error=str(e),
                data={"bank": self.bank_name}
            )
        except Exception as e:
            log_error_with_context(e, f"API банка {self.bank_name} error")
            return None, create_response(
                status=config.STATUS["API_SOAP_ERROR"],
                error=str(e),
                data={"bank": self.bank_name}
            )
    
    def parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Парсит ответ Центринвеста."""
        try:
            data = response.json() if response.content else None
            # Центринвест возвращает список объектов
            if isinstance(data, list):
                return {
                    "status": "success",
                    "data": data,
                    "count": len(data)
                }
            return {
                "status": "success" if response.status_code == 202 else "error",
                "data": data,
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