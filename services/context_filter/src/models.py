from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Article(BaseModel):
    """Структура статьи. Совместима со схемой из ingestor."""
    id: Optional[str] = None              # Делаем опциональным
    title: str                            # Обязательное
    body: str                             # Переименовали 'text' → 'body' (как в ingestor)
    source: Optional[str] = None
    url: Optional[str] = None             # Нужно для генерации id
    published_at: Optional[Any] = None    # Any, т.к. может быть datetime или str
    scraped_at: Optional[Any] = None
    
    class Config:
        extra = "ignore"

class FilterRequest(BaseModel):
    """Запрос на фильтрацию статей."""
    user_id: str
    context: str
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    articles: List[Article]
    
    class Config:
        extra = "ignore"

class FilterResponse(BaseModel):
    """Ответ с отфильтрованными статьями."""
    total_received: int
    total_passed: int
    total_filtered: int
    articles: List[Article]
    scores: Dict[str, float]
    embeddings: Optional[List[List[float]]] = None