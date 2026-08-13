from pydantic import BaseModel, Field, field_validator
from .utils import clean_domain


class AnalyzeRequest(BaseModel):
    domains: list[str] = Field(..., min_length=1, description="Список доменов для анализа")

    @field_validator('domains', mode='before')
    @classmethod
    def clean_and_deduplicate(cls, v: list[str]) -> list[str]:
        cleaned = [clean_domain(d) for d in v]
        seen = set()
        result = []
        for d in cleaned:
            if d and d not in seen:
                seen.add(d)
                result.append(d)
        return result


class DomainStats(BaseModel):
    """Схема одного домена из ответа OpenPageRank."""
    domain: str
    found: bool
    open_page_rank: float | None = None
    rank: int | None = None
    referring_domains: int | None = None

    @property
    def is_valid(self) -> bool:
        return self.found


class OpenPageRankResponse(BaseModel):
    """Полный ответ от API OpenPageRank."""
    as_of: str
    count: int
    results: list[DomainStats]
    invalid: list[str] = []


class AnalyzeResponse(BaseModel):
    """Ответ нашего сервиса клиенту."""
    task_id: str
    status: str
    as_of: str
    total_requested: int
    successful: int
    failed: int
    results: list[DomainStats]