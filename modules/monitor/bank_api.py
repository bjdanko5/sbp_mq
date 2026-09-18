# modules/monitor/bank_api.py
"""
Проверка доступности банков — только TCP.

Особенности:
- TCP connect (без HTTP-запросов).
- Не нагружает nginx, не видно в access log.
- Редкий опрос (5 мин) + jitter.
- Backoff при ошибках (10/30 мин).
"""

import asyncio
import random
import socket
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import config
from modules.logger_config import logger


# ============================================================
#                   НАСТРОЙКИ
# ============================================================

HEALTHCHECK_INTERVAL = 300
HEALTHCHECK_JITTER = 60
HEALTHCHECK_TIMEOUT = 5.0

BACKOFF_MAP = {
    0: 300,
    3: 600,
    5: 1800,
}


# ============================================================
#                   DATA CLASS
# ============================================================

@dataclass
class BankApiStatus:
    """Статус TCP-доступности банка."""
    bank: str
    host: str
    port: int
    available: bool = False
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    checked_at: str = ""
    error_type: Optional[str] = None    # dns / timeout / refused / other
    
    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================
#                   TCP ПРОВЕРКА
# ============================================================

async def check_bank_tcp(
    bank: str,
    host: str,
    port: int = 443,
    timeout: float = HEALTHCHECK_TIMEOUT,
) -> BankApiStatus:
    """
    Проверка TCP-доступности банка.
    
    Не делает HTTP-запросов.
    """
    status = BankApiStatus(
        bank=bank,
        host=host,
        port=port,
        checked_at=datetime.now().isoformat(),
    )
    start = time.time()
    
    # DNS (если hostname)
    try:
        socket.gethostbyname(host)
    except socket.gaierror as e:
        status.error = f"DNS: {e}"
        status.error_type = "dns"
        status.latency_ms = round((time.time() - start) * 1000, 1)
        return status
    
    # TCP connect
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        status.available = True
    except asyncio.TimeoutError:
        status.error = "TCP timeout"
        status.error_type = "timeout"
    except ConnectionRefusedError:
        status.error = "Connection refused"
        status.error_type = "refused"
    except OSError as e:
        status.error = f"TCP: {e}"
        status.error_type = "other"
    except Exception as e:
        status.error = f"Unknown: {e}"
        status.error_type = "other"
    
    status.latency_ms = round((time.time() - start) * 1000, 1)
    return status


# ============================================================
#                   ПАРСИНГ URL
# ============================================================

def _parse_target(url_or_host: str) -> tuple[str, int]:
    """Парсит URL или host → (host, port)."""
    if "://" in url_or_host:
        parsed = urlparse(url_or_host)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return host, port
    
    if ":" in url_or_host:
        host, port_str = url_or_host.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 443
        return host, port
    
    return url_or_host, 443


# ============================================================
#                   ПРОВЕРКА ВСЕХ БАНКОВ
# ============================================================

async def check_all_banks() -> dict:
    """Проверка всех банков параллельно (TCP)."""
    tasks = []
    banks = []
    
    for bank, bank_cfg in config.BANK_CONFIG.items():
        url = bank_cfg.get("url")
        if not url:
            continue
        
        # Пропускаем заглушки (с "..." в URL)
        if "..." in url:
            logger.debug(f"[BankAPI] Пропуск {bank}: URL-заглушка")
            continue
        
        host, port = _parse_target(url)
        if not host:
            continue
        
        banks.append(bank)
        tasks.append(check_bank_tcp(bank, host, port))
    
    if not tasks:
        return {}
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    output = {}
    for bank, result in zip(banks, results):
        if isinstance(result, Exception):
            output[bank] = {
                "bank": bank,
                "available": False,
                "error": f"Check failed: {result}",
                "error_type": "other",
                "checked_at": datetime.now().isoformat(),
            }
        else:
            output[bank] = result.to_dict()
    
    return output


# ============================================================
#                   BACKOFF STATE
# ============================================================

class BankApiHealthState:
    """Состояние health-проверки с backoff."""
    
    def __init__(self):
        self.consecutive_errors = 0
        self.last_check: Optional[str] = None
        self.last_result: Optional[dict] = None
    
    def get_next_interval(self) -> int:
        """Интервал до следующей проверки (с jitter)."""
        base = self._get_base_interval()
        jitter = random.uniform(-HEALTHCHECK_JITTER, HEALTHCHECK_JITTER)
        return max(30, int(base + jitter))
    
    def _get_base_interval(self) -> int:
        """Базовый интервал по кол-ву ошибок."""
        if self.consecutive_errors >= 5:
            return BACKOFF_MAP[5]
        if self.consecutive_errors >= 3:
            return BACKOFF_MAP[3]
        return BACKOFF_MAP[0]
    
    def record(self, banks_result: dict) -> None:
        """Записать результат проверки."""
        self.last_check = datetime.now().isoformat()
        self.last_result = banks_result
        
        all_ok = all(
            b.get("available", False) for b in banks_result.values()
        )
        
        if all_ok:
            self.consecutive_errors = 0
        else:
            self.consecutive_errors += 1
        
        logger.debug(
            f"[BankAPI] TCP errors={self.consecutive_errors}, "
            f"next_interval={self._get_base_interval()}s"
        )
    
    def get_status(self) -> dict:
        """Текущее состояние (для /health)."""
        return {
            "consecutive_errors": self.consecutive_errors,
            "last_check": self.last_check,
            "next_interval": self._get_base_interval(),
            "last_result": self.last_result,
        }
