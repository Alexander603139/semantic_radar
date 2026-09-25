import logging
import numpy as np
import httpx
from typing import List, Dict
from fastapi import HTTPException
from .models import Article, FilterResponse
from .settings import settings

logger = logging.getLogger(__name__)

async def filter_articles_by_context(
    user_id: str,
    context: str,
    threshold: float,
    articles: List[Article]
) -> FilterResponse:
    """
    Основная логика фильтрации:
    1. Узнает активную модель из storage.
    2. Векторизует контекст (query) и статьи (passage) через embedder.
    3. Считает косинусное сходство.
    4. Возвращает только статьи, превышающие порог.
    """
    if not articles:
        return FilterResponse(
            total_received=0, total_passed=0, total_filtered=0,
            articles=[], scores={}, embeddings=None
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Узнаем активную модель пользователя
        try:
            settings_resp = await client.get(f"{settings.STORAGE_URL}/settings/{user_id}")
            settings_resp.raise_for_status()
            active_model_slug = settings_resp.json().get("active_model_slug", "e5-base-local")
            logger.info(f"🎯 Фильтрация использует модель: {active_model_slug}")
        except Exception as e:
            logger.error(f"Не удалось получить настройки из storage: {e}")
            raise HTTPException(status_code=500, detail="Storage settings error")

        # 2. Векторизуем КОНТЕКСТ (всегда один текст, префикс query)
        try:
            ctx_resp = await client.post(
                f"{settings.EMBEDDER_URL}/embed_texts",
                json={
                    "texts": [context],
                    "prefix_type": "query",
                    "model_slug": active_model_slug,
                    "user_id": user_id
                }
            )
            ctx_resp.raise_for_status()
            context_embedding = np.array(ctx_resp.json()["embeddings"][0])
        except Exception as e:
            logger.error(f"Ошибка векторизации контекста: {e}")
            raise HTTPException(status_code=500, detail="Context embedding failed")

        # 3. Векторизуем СТАТЬИ батчем (префикс passage)
        texts_to_embed = [f"{art.title}. {art.text}" for art in articles]
        try:
            arts_resp = await client.post(
                f"{settings.EMBEDDER_URL}/embed_texts",
                json={
                    "texts": texts_to_embed,
                    "prefix_type": "passage",
                    "model_slug": active_model_slug,
                    "user_id": user_id
                }
            )
            arts_resp.raise_for_status()
            articles_embeddings = np.array(arts_resp.json()["embeddings"])
        except Exception as e:
            logger.error(f"Ошибка векторизации статей: {e}")
            raise HTTPException(status_code=500, detail="Articles embedding failed")

        # 4. Вычисляем косинусное сходство (Cosine Similarity)
        # Нормализуем векторы для быстрого скалярного произведения
        context_norm = context_embedding / np.linalg.norm(context_embedding)
        articles_norm = articles_embeddings / np.linalg.norm(articles_embeddings, axis=1, keepdims=True)
        
        # Скалярное произведение нормализованных векторов = косинусное сходство
        similarities = np.dot(articles_norm, context_norm)

        # 5. Фильтруем и формируем ответ
        passed_articles = []
        passed_embeddings = []
        scores = {}

        for i, art in enumerate(articles):
            score = float(similarities[i])
            scores[art.id] = round(score, 4)
            
            if score >= threshold:
                passed_articles.append(art)
                passed_embeddings.append(articles_embeddings[i].tolist())

        logger.info(f"✅ Фильтрация: получено {len(articles)}, прошло {len(passed_articles)}, отклонено {len(articles) - len(passed_articles)}")

        return FilterResponse(
            total_received=len(articles),
            total_passed=len(passed_articles),
            total_filtered=len(articles) - len(passed_articles),
            articles=passed_articles,
            scores=scores,
            embeddings=passed_embeddings  # Возвращаем векторы, чтобы ingestor мог сразу сохранить их, не вызывая embedder второй раз!
        )