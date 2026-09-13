# modules/api_bank_client/base.py
"""
Базовый абстрактный класс для всех банков.
"""

import httpx
from typing import Dict, Any, Optional, Tuple, Union
from abc import ABC, abstractmethod

import config
from modules.logger_config import logger, log_error_with_context
from modules.response_utils import create_response


class BaseBankClient(ABC):
    """
    Базовый класс для всех банков.
    
    Каждый банк должен реализовать:
    - send_request() — отправка запроса в API банка
    - parse_response() — парсинг ответа API банка
    - get_callback_url() — URL для callback
    """
    
    def __init__(self, bank_name: str):
        self.bank_name = bank_name
        self.base_url = config.BANK_CONFIG.get(bank_name, {}).get('url')
        self.timeout = config.REQUEST_TIMEOUT
        self.verify_ssl = config.BANK_CONFIG.get(bank_name, {}).get('verify_ssl', False)
        self.headers = config.DEFAULT_HEADERS.copy()
        self._client: Optional[httpx.AsyncClient] = None
        self._is_closed = False
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Возвращает асинхронный HTTP клиент."""
        if self._client is None or self._is_closed:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            self._is_closed = False
        return self._client
    
    async def close(self):
        """Закрывает HTTP клиент."""
        if self._client and not self._is_closed:
            await self._client.aclose()
            self._client = None
            self._is_closed = True
    
    async def __aenter__(self):
        """Поддержка контекстного менеджера."""
        await self._get_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера."""
        await self.close()
    
    @abstractmethod
    async def send_request(self, data: Union[Dict[str, Any], list]) -> Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
        """
        Отправляет запрос в API банка.
        
        Args:
            data: Данные для отправки
        
        Returns:
            Tuple[Optional[httpx.Response], Optional[Dict[str, Any]]]:
                - (response, None) при успехе
                - (None, error_response) при ошибке
        """
        pass
    
    @abstractmethod
    def parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Парсит ответ API банка.
        
        Args:
            response: Ответ от API
        
        Returns:
            Dict[str, Any]: Распарсенный ответ
        """
        pass
    
    @abstractmethod
    def get_callback_url(self) -> str:
        """
        Возвращает URL для callback.
        
        Returns:
            str: URL callback
        """
        pass
    
    def is_success(self, response: httpx.Response) -> bool:
        """Проверяет, является ли ответ успешным."""
        return response.status_code == 202
    
    def _build_url(self, endpoint: str = "") -> str:
        """Строит полный URL."""
        if not self.base_url:
            raise ValueError(f"Base URL для банка {self.bank_name} не настроен")
        if endpoint.startswith("/"):
            return f"{self.base_url}{endpoint}"
        return f"{self.base_url}/{endpoint}" if endpoint else self.base_url