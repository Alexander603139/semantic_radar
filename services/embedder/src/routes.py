from fastapi import APIRouter, HTTPException
import logging
from .models import EmbedRequest, EmbedResponse
from .embedder import process_articles
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    try:
        file_id, count = await process_articles(request.articles, request.user_id)
        return EmbedResponse(status="ok", vectors_file=file_id, chunk_count=count)
    except Exception as e:
        logger.error(f"Ошибка векторизации: {e}")
        raise HTTPException(status_code=500, detail=str(e))