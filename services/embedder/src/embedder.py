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
import json
import httpx
import io

logger = logging.getLogger(__name__)

CHUNK_SIZE = settings.CHUNK_SIZE
CHUNK_OVERLAP = settings.CHUNK_OVERLAP

# Кэш для загруженных локальных моделей (экономим RAM и время загрузки)
_loaded_local_models = {}

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

async def process_articles(articles: List[Article], user_id: str) -> tuple[str, int]:
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

    # 1. Узнаем, какую модель использовать
    model_config = await get_active_model_config(user_id)
    logger.info(f"🎯 Активная модель для векторизации: {model_config['name']} ({model_config['slug']})")

    # 2. Инициализируем стратегию
    if model_config["provider_type"] == "local_huggingface":
        model_path = model_config["model_path"]
        if model_path not in _loaded_local_models:
            _loaded_local_models[model_path] = LocalHuggingFaceEmbedder(model_path)
        strategy = _loaded_local_models[model_path]
        
    elif model_config["provider_type"] == "openai_api":
        # Ключ берем из env (безопасность!), если нет - из БД
        api_key = settings.YA_AI_PROXY_KEY or model_config.get("api_key")
        if not api_key:
            raise ValueError("API ключ не задан в переменных окружения (YA_AI_PROXY_KEY)")
        strategy = OpenAIAPIEmbedder(
            base_url=model_config["base_url"],
            api_key=api_key,
            model_name=model_config["model_name"]
        )
    else:
        raise ValueError(f"Неизвестный provider_type: {model_config['provider_type']}")

    # 3. Вычисляем эмбеддинги
    embeddings = await strategy.embed_texts(all_chunks, requires_prefix=model_config["requires_prefix"])

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

    # 5. Отправляем в storage с указанием модели
    async with httpx.AsyncClient(timeout=60.0) as client:
        files = {'file': (filename, buf, 'application/octet-stream')}
        data = {
            'user_id': user_id,
            'file_type': 'vectors',
            'file_key': filename,
            'metadata': json.dumps({
                "chunk_count": len(all_chunks), 
                "source_count": len(articles),
                "model_slug": model_config["slug"],
                "model_name": model_config["model_name"]
            })
        }
        resp = await client.post(
            f"{settings.STORAGE_URL}/upload",
            files=files,
            data=data
        )
        resp.raise_for_status()
        result = resp.json()
        file_id = result.get('id')
        logger.info(f"✅ Векторы сохранены: file_id={file_id}, модель={model_config['slug']}, чанков={len(all_chunks)}")
        return file_id, len(all_chunks)