import logging
from typing import List, Dict
from .models import Article, FilterResponse

logger = logging.getLogger(__name__)

async def filter_articles_by_context(
    user_id: str,
    context: str,
    threshold: float,
    articles: List[Article]
) -> FilterResponse:
    """
    Заглушка: возвращает все статьи без фильтрации.
    Полная логика будет реализована на Этапе 3.
    """
    logger.info(f"Фильтрация для user_id={user_id}, контекст='{context}', порог={threshold}, статей={len(articles)}")
    
    # Пока возвращаем все статьи (заглушка)
    passed_articles = articles
    scores = {art.id: 1.0 for art in articles}  # все оценки = 1.0
    
    return FilterResponse(
        total_received=len(articles),
        total_passed=len(passed_articles),
        total_filtered=0,
        articles=passed_articles,
        scores=scores,
        embeddings=None
    )