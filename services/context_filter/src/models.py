from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Article(BaseModel):
    """Структура одной статьи."""
    id: str
    title: str
    text: str
    source: Optional[str] = None
    published_at: Optional[str] = None

class FilterRequest(BaseModel):
    """Запрос на фильтрацию статей."""
    user_id: str
    context: str
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    articles: List[Article]

class FilterResponse(BaseModel):
    """Ответ с отфильтрованными статьями."""
    total_received: int
    total_passed: int
    total_filtered: int
    articles: List[Article]
    scores: Dict[str, float]  # {article_id: similarity_score}
    embeddings: Optional[List[List[float]]] = None  # векторы прошедших статей (для embedder)