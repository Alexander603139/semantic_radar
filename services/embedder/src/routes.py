from fastapi import APIRouter, HTTPException
import logging
from .models import EmbedRequest, EmbedResponse, EmbedTextsRequest, EmbedTextsResponse
from .embedder import process_articles, get_embeddings_for_texts

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    try:
        file_id, count = await process_articles(request.articles, request.user_id, request.model_slug)
        return EmbedResponse(status="ok", vectors_file=file_id, chunk_count=count)
    except Exception as e:
        logger.error(f"Ошибка векторизации: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- НОВЫЙ ЭНДПОИНТ ДЛЯ ЭТАПА 2 ---
@router.post("/embed_texts", response_model=EmbedTextsResponse)
async def embed_texts(request: EmbedTextsRequest):
    """
    Векторизует список текстов и возвращает эмбеддинги без сохранения в storage.
    """
    try:
        embeddings = await get_embeddings_for_texts(
            texts=request.texts,
            prefix_type=request.prefix_type,
            model_slug=request.model_slug,
            user_id=request.user_id
        )
        return EmbedTextsResponse(embeddings=embeddings)
    except Exception as e:
        logger.error(f"Ошибка векторизации текстов: {e}")
        raise HTTPException(status_code=500, detail=str(e))