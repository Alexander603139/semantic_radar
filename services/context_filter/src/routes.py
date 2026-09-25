from fastapi import APIRouter, HTTPException
import logging
from .models import FilterRequest, FilterResponse
from .filter import filter_articles_by_context

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/filter", response_model=FilterResponse)
async def filter_articles(request: FilterRequest):
    """
    Принимает статьи и контекст, возвращает только релевантные статьи.
    """
    try:
        result = await filter_articles_by_context(
            user_id=request.user_id,
            context=request.context,
            threshold=request.threshold,
            articles=request.articles
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка фильтрации: {e}")
        raise HTTPException(status_code=500, detail=str(e))