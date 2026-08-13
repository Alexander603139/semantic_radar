import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import ValidationError

from .config import settings
from .models import OpenPageRankResponse, DomainStats
from .exceptions import OPRServerError, OPRClientValidationError

logger = logging.getLogger(__name__)


class OPRClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.OPR_API_KEY}",
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, OPRServerError)),
        reraise=True
    )
    async def fetch_bulk(self, domains: list[str]) -> OpenPageRankResponse:
        all_results: list[DomainStats] = []
        all_invalid: list[str] = []
        as_of = ""

        async with httpx.AsyncClient(timeout=settings.OPR_TIMEOUT) as client:
            # OPR принимает до 100 доменов за запрос — бьём на чанки
            for i in range(0, len(domains), 100):
                chunk = domains[i:i + 100]
                payload = {"domains": chunk, "include_history": False}

                logger.info(f"Fetching OPR stats for {len(chunk)} domains...")
                response = await client.post(
                    settings.OPR_BASE_URL,
                    json=payload,
                    headers=self.headers
                )

                if response.status_code >= 500:
                    logger.error(f"OPR server error: {response.status_code}")
                    raise OPRServerError(f"OPR returned {response.status_code}")
                elif response.status_code >= 400:
                    logger.error(f"OPR client error: {response.status_code} - {response.text}")
                    raise OPRClientValidationError(f"OPR returned {response.status_code}")

                try:
                    parsed = OpenPageRankResponse.model_validate(response.json())
                    all_results.extend(parsed.results)
                    all_invalid.extend(parsed.invalid)
                    if not as_of:
                        as_of = parsed.as_of
                except ValidationError as e:
                    logger.error(f"Pydantic validation failed: {e.errors()}")
                    raise OPRClientValidationError(f"Invalid OPR response: {e}")

        return OpenPageRankResponse(
            as_of=as_of,
            count=len(all_results),
            results=all_results,
            invalid=all_invalid
        )