from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class Article(BaseModel):
    id: str
    title: str
    text: str
    source: str
    published_at: Optional[datetime] = None


class EmbedRequest(BaseModel):
    user_id: str
    articles: List[Article]
    # Опциональный параметр для ручной проверки (Этап 4):
    # если указан — используется конкретная модель из реестра,
    # если нет — активная модель пользователя из настроек.
    model_slug: Optional[str] = None


class EmbedResponse(BaseModel):
    status: str
    vectors_file: str
    chunk_count: int

class EmbedTextsRequest(BaseModel):
    """Запрос на векторизацию списка текстов без сохранения."""
    texts: List[str]
    prefix_type: str  # "query" или "passage"
    model_slug: Optional[str] = None
    user_id: Optional[str] = "admin"  # используется, если model_slug не передан

class EmbedTextsResponse(BaseModel):
    """Ответ с массивом эмбеддингов."""
    embeddings: List[List[float]]