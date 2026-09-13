# modules/api_bank_client/__init__.py
"""
API Bank Client — клиенты для работы с API банков.

Поддерживает:
- Центринвест (CI) — полностью работает
- Сбербанк (SB) — в разработке
- ВТБ (VTB) — в разработке

Использование:
    from modules.api_bank_client import create_bank_client, api_bank
    
    # Новый клиент
    client = create_bank_client('ci')
    response, error = await client.send_request(data)
    
    # Старый клиент (обратная совместимость)
    response, error = await api_bank.post(data)
"""

from .base import BaseBankClient
from .bank_ci import BankCI
from .bank_sb import BankSB
from .bank_vtb import BankVTB
from .factory import create_bank_client, get_bank_names
from .legacy import APIBankClient, api_bank

__all__ = [
    'BaseBankClient',
    'BankCI',
    'BankSB',
    'BankVTB',
    'create_bank_client',
    'get_bank_names',
    'APIBankClient',
    'api_bank',
]