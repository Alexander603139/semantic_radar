import logging
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime
from typing import List
from .settings import settings
from .models import Article
from .strategies import LocalHuggingFaceEmbedder, OpenAIAPIEmbedder
from .factory import EmbedderFactory
import json
import httpx
import io

logger = logging.getLogger(__name__)

CHUNK_SIZE = settings.CHUNK_SIZE
CHUNK_OVERLAP = settings.CHUNK_OVERLAP

# Фабрика стратегий (Этап 6) — кэширует локальные модели внутри себя
_factory = EmbedderFactory()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [" ".join(words)]
    chunks = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i+chunk_size])
        if chunk:
            chunks.append(chunk)
            
    return chunks


async def get_active_model_config(user_id: str) -> dict:
    """Получает конфигурацию активной модели из storage."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        settings_resp = await client.get(f"{settings.STORAGE_URL}/settings/{user_id}")
        settings_resp.raise_for_status()
        active_slug = settings_resp.json().get("active_model_slug", "e5-base-local")

        models_resp = await client.get(f"{settings.STORAGE_URL}/ai-models")
        models_resp.raise_for_status()
        models = models_resp.json()

        for m in models:
            if m["slug"] == active_slug:
                return m

        raise ValueError(f"Модель с slug '{active_slug}' не найдена в реестре storage")


async def get_model_config_by_slug(model_slug: str) -> dict:
    """
    Получает конфигурацию модели из реестра по slug.
    Используется для ручного вызова /embed с конкретной моделью (Этап 4).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        models_resp = await client.get(f"{settings.STORAGE_URL}/ai-models")
        models_resp.raise_for_status()
        models = models_resp.json()

        for m in models:
            if m["slug"] == model_slug:
                return m

        raise ValueError(f"Модель с slug '{model_slug}' не найдена в реестре storage")


# =====================================================================
# ЭТАП 7: Fallback-логика — две новые функции
# =====================================================================

async def get_fallback_model_config() -> dict:
    """Возвращает локальную E5 как fallback-модель."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        models_resp = await client.get(f"{settings.STORAGE_URL}/ai-models")
        models_resp.raise_for_status()
        models = models_resp.json()
        for m in models:
            if m["slug"] == "e5-base-local":
                return m
    raise ValueError("Fallback модель e5-base-local не найдена в реестре")


async def log_fallback_event(user_id: str, reason: str, from_slug: str, to_slug: str):
    """Записывает событие fallback в storage для отображения в админке."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "reason": reason[:500],
        "from_model": from_slug,
        "to_model": to_slug,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.STORAGE_URL}/settings/{user_id}",
                json={"last_fallback_event": event},
            )
            logger.info(f"📝 Событие fallback записано: {from_slug} → {to_slug}")
    except Exception as e:
        logger.error(f"Не удалось записать событие fallback: {e}")


# =====================================================================
# Основная функция process_articles (с поддержкой fallback)
# =====================================================================

async def process_articles(articles: List[Article], user_id: str, model_slug: str = None) -> tuple[str, int]:
    all_chunks = []
    all_meta = []

    for article in articles:
        chunks = chunk_text(article.text)
        for idx, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            all_meta.append({
                "article_id": article.id,
                "chunk_index": idx,
                "source": article.source,
                "published_at": article.published_at,
                "title": article.title,
            })

    if not all_chunks:
        raise ValueError("Нет текста для векторизации")

    # 1. Определяем, какую модель использовать
    if model_slug:
        # Ручной вызов с конкретной моделью (проверка Этапа 4)
        model_config = await get_model_config_by_slug(model_slug)
    else:
        # Обычный режим: используем активную модель пользователя из настроек
        model_config = await get_active_model_config(user_id)

    logger.info(f"🎯 Модель для векторизации: {model_config['name']} ({model_config['slug']})")

    # Трекинг: какая модель фактически использована (может измениться на fallback)
    used_model_slug = model_config["slug"]
    used_requires_prefix = model_config["requires_prefix"]
    strategy = None

    # 2. Инициализируем стратегию через фабрику (Этап 6)
    if model_config["provider_type"] == "local_huggingface":
        # Для локальной модели фабрика загрузит её в кэш
        strategy = _factory.get_strategy(model_config)

    elif model_config["provider_type"] == "openai_api":
        # Для API-модели проверяем наличие ключа (Этап 7 — первый слой fallback)
        api_key = settings.YA_AI_PROXY_KEY or model_config.get("api_key")
        if not api_key:
            # Ключа нет — сразу идём в fallback на E5
            logger.warning("⚠️ API ключ не задан, переключаемся на fallback (E5)")
            fallback_config = await get_fallback_model_config()
            strategy = _factory.get_strategy(fallback_config)
            used_model_slug = fallback_config["slug"]
            used_requires_prefix = fallback_config["requires_prefix"]
            await log_fallback_event(
                user_id,
                "API key missing",
                model_config["slug"],
                fallback_config["slug"],
            )
        else:
            strategy = _factory.get_strategy(model_config)
    else:
        raise ValueError(f"Неизвестный provider_type: {model_config['provider_type']}")

    # 3. Вычисляем эмбеддинги с Fallback-логикой (Этап 7 — второй слой)
    try:
        embeddings = await strategy.embed_texts(
            all_chunks,
            requires_prefix=used_requires_prefix,
            prefix_type="passage",
        )
    except Exception as e:
        # Основная модель упала (API ошибка, таймаут, 5xx и т.п.) — переключаемся на E5
        logger.error(f"❌ Ошибка основной модели ({used_model_slug}): {e}. Переключаемся на fallback...")
        fallback_config = await get_fallback_model_config()
        fallback_strategy = _factory.get_strategy(fallback_config)
        embeddings = await fallback_strategy.embed_texts(
            all_chunks,
            requires_prefix=fallback_config["requires_prefix"],
            prefix_type="passage",
        )
        await log_fallback_event(
            user_id,
            str(e)[:500],
            used_model_slug,
            fallback_config["slug"],
        )
        used_model_slug = fallback_config["slug"]
        logger.info(f"✅ Fallback на {fallback_config['slug']} успешно выполнен")

    # 4. Формируем DataFrame и Parquet
    df_data = {
        "article_id": [m["article_id"] for m in all_meta],
        "chunk_index": [m["chunk_index"] for m in all_meta],
        "source": [m["source"] for m in all_meta],
        "published_at": [m["published_at"] for m in all_meta],
        "title": [m["title"] for m in all_meta],
        "text": all_chunks,
        "embedding": [emb.tolist() for emb in embeddings],
    }
    df = pd.DataFrame(df_data)
    table = pa.Table.from_pandas(df)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    buf.seek(0)

    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}.parquet"

    # 5. Отправляем в storage с указанием РЕАЛЬНО использованной модели
    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {'file': (filename, buf, 'application/octet-stream')}
        data = {
            'user_id': user_id,
            'file_type': 'vectors',
            'file_key': filename,
            'model_slug': used_model_slug,  # ← НОВОЕ: для изоляции в S3 (Этап 8)
            'metadata': json.dumps({
                "chunk_count": len(all_chunks),
                "source_count": len(articles),
                "model_slug": used_model_slug,  # ← ВАЖНО: не model_config['slug'], а used_model_slug
            }),
        }
        resp = await client.post(
            f"{settings.STORAGE_URL}/upload",
            files=files,
            data=data,
        )
        resp.raise_for_status()
        result = resp.json()
        file_id = result.get('id')
        logger.info(f"✅ Векторы сохранены: file_id={file_id}, модель={used_model_slug}, чанков={len(all_chunks)}")
        return file_id, len(all_chunks)

async def get_embeddings_for_texts(
    texts: List[str],
    prefix_type: str,
    model_slug: str = None,
    user_id: str = "admin"
) -> List[List[float]]:
    """
    Векторизует список текстов и возвращает эмбеддинги без сохранения в storage.
    Используется сервисом context_filter для семантической фильтрации.
    """
    if not texts:
        return []
    
    # 1. Определяем конфигурацию модели
    if model_slug:
        model_config = await get_model_config_by_slug(model_slug)
    else:
        model_config = await get_active_model_config(user_id)
        
    # 2. Получаем стратегию из фабрики (модель закеширована)
    strategy = _factory.get_strategy(model_config)
    
    # 3. Вычисляем эмбеддинги
    embeddings = await strategy.embed_texts(
        texts,
        requires_prefix=model_config["requires_prefix"],
        prefix_type=prefix_type,
    )
    
    # 4. Возвращаем как списки float (для JSON-сериализации)
    return [emb.tolist() for emb in embeddings]