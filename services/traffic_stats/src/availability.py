import asyncio
import logging
import httpx
from typing import Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Статусы "доступен". 403 намеренно исключён (по требованию — красный).
AVAILABLE_STATUSES = {200, 301, 302}

# Заголовки как у парсера, чтобы проверка давала тот же результат, что и реальный парсинг
CHECK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def check_domain_availability(domain: str, timeout: float = 10.0) -> Tuple[Optional[bool], Optional[int]]:
    """Проверяет доступность одного домена. Возвращает (available, http_status)."""
    url = f"https://{domain}"
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=CHECK_HEADERS,
        ) as client:
            response = await client.get(url)
            status = response.status_code
            available = status in AVAILABLE_STATUSES
            logger.info(f"🔎 Проверка {domain}: HTTP {status} -> {'✅ доступен' if available else '❌ недоступен'}")
            return available, status
    except Exception as e:
        logger.warning(f"🔎 Проверка {domain} не удалась: {type(e).__name__}: {e}")
        return False, None


async def check_domains_availability(domains: list[str], timeout: float = 10.0) -> Dict[str, Tuple[Optional[bool], Optional[int]]]:
    """Проверяет список доменов параллельно. Возвращает {domain: (available, http_status)}."""
    if not domains:
        return {}
    tasks = [check_domain_availability(d, timeout) for d in domains]
    results = await asyncio.gather(*tasks)
    return dict(zip(domains, results))