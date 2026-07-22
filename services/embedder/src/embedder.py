import os
import logging
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import List, Dict, Any
from .config import MODEL_NAME, VECTORS_ROOT, CHUNK_SIZE, CHUNK_OVERLAP
from .models import Article

logger = logging.getLogger(__name__)

# Глобальный объект модели (загружается один раз при старте)
_model = None

def load_model():
    global _model
    if _model is None:
        logger.info(f"Загрузка модели {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Модель загружена")
    return _model

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

def process_articles(articles: List[Article], user_id: str) -> tuple[str, int]:
    """
    Основная функция:
      - чанкует все статьи,
      - вычисляет эмбеддинги,
      - сохраняет в Parquet,
      - возвращает путь к файлу.
    """
    all_chunks = []
    all_meta = []  # будет хранить словари с метаданными для каждого чанка

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

    model = load_model()
    embeddings = model.encode(all_chunks, convert_to_numpy=True)  # shape (n_chunks, 384)

    # Собираем DataFrame
    df_data = {
        "article_id": [m["article_id"] for m in all_meta],
        "chunk_index": [m["chunk_index"] for m in all_meta],
        "source": [m["source"] for m in all_meta],
        "published_at": [m["published_at"] for m in all_meta],
        "title": [m["title"] for m in all_meta],
        "text": all_chunks,
        "embedding": [emb.tolist() for emb in embeddings],  # список float
    }
    df = pd.DataFrame(df_data)

    # Путь для сохранения
    date_str = datetime.now().strftime("%Y-%m-%d")
    user_dir = os.path.join(VECTORS_ROOT, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, f"{date_str}.parquet")

    # Сохраняем в Parquet
    table = pa.Table.from_pandas(df)
    pq.write_table(table, filepath)
    logger.info(f"Сохранено {len(all_chunks)} чанков в {filepath}")

    return filepath, len(all_chunks)

def compute_embeddings(texts: List[str]) -> np.ndarray:
    """
    Вычисляет эмбеддинги для списка текстов (синхронно).
    """
    model = load_model()
    # MiniLM на CPU работает быстро, batch_size можно оставить по умолчанию
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings

def save_vectors_to_parquet(
    user_id: str,
    article_id: str,
    chunks: List[str],
    embeddings: np.ndarray,
    metadata: Dict[str, Any]
) -> str:
    """
    Сохраняет чанки и их векторы в Parquet-файл.
    Возвращает путь к сохранённому файлу.
    """
    # Создаём структуру папок
    date_str = datetime.now().strftime("%Y-%m-%d")
    user_dir = os.path.join(VECTORS_ROOT, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)

    # Формируем файл: user_{id}_{date}.parquet
    filename = f"{article_id}_{date_str}.parquet"   # или единый файл за день?
    # Лучше сохранять все чанки за день в один файл, чтобы уменьшить количество файлов
    # Для простоты будем сохранять отдельно для каждой статьи, но можно объединять.
    # Реализуем накопление чанков в общий файл за день.
    # Однако для демонстрации сделаем по одному файлу на запрос (массив статей).
    # Удобнее сохранять все чанки всех статей запроса в один Parquet.
    # Поэтому в функции будем принимать список чанков и эмбеддингов для всех статей.
    pass