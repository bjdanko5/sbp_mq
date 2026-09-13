# modules/api_bank_client/factory.py
"""
Фабрика для создания клиентов банков.
"""

from .base import BaseBankClient
from .bank_ci import BankCI
from .bank_sb import BankSB
from .bank_vtb import BankVTB


def create_bank_client(bank: str) -> BaseBankClient:
    """
    Создаёт клиент для указанного банка.
    
    Args:
        bank: Имя банка (ci, sb, vtb)
    
    Returns:
        BaseBankClient: Клиент банка
    
    Raises:
        ValueError: Если банк неизвестен
    
    Пример:
        client = create_bank_client('ci')
        response, error = await client.send_request(data)
    """
    bank = bank.lower()
    
    if bank == "ci":
        return BankCI()
    elif bank == "sb":
        return BankSB()
    elif bank == "vtb":
        return BankVTB()
    else:
        raise ValueError(f"Неизвестный банк: {bank}. Доступные: ci, sb, vtb")


def get_bank_names() -> list:
    """Возвращает список доступных банков."""
    return ["ci", "sb", "vtb"]