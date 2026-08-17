import os
import logging
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
from sklearn.preprocessing import StandardScaler
import umap
import hdbscan
from scipy.stats import wasserstein_distance
from .settings import settings
import httpx
import io

logger = logging.getLogger(__name__)

async def load_vectors_for_period(user_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Загружает векторы из storage через API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Получаем список файлов за период
        resp = await client.get(
            f"{settings.STORAGE_URL}/list",
            params={
                "user_id": user_id,
                "file_type": "vectors",
                "limit": 100
            }
        )
        if resp.status_code != 200:
            logger.warning(f"Failed to get file list from storage: {resp.status_code}")
            return pd.DataFrame()
        files = resp.json()
        if not files:
            logger.info(f"No vector files found for user {user_id}")
            return pd.DataFrame()

        # Загружаем каждый Parquet-файл из storage
        all_dfs = []
        for file in files:
            file_id = file["id"]
            created_at = file["created_at"]
            if created_at:
                try:
                    file_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    continue
                if start_date <= file_date <= end_date:
                    # Скачиваем файл
                    dl_resp = await client.get(f"{settings.STORAGE_URL}/download/{file_id}")
                    if dl_resp.status_code == 200:
                        buf = io.BytesIO(dl_resp.content)
                        df = pd.read_parquet(buf)
                        all_dfs.append(df)
                    else:
                        logger.warning(f"Failed to download file {file_id}: {dl_resp.status_code}")
        if not all_dfs:
            return pd.DataFrame()
        return pd.concat(all_dfs, ignore_index=True)

def compute_embeddings_matrix(df: pd.DataFrame) -> np.ndarray:
    """Извлекает векторы из колонки 'embedding' и возвращает матрицу (n_samples, dim)."""
    if df.empty:
        return np.array([])
    try:
        embeddings = np.stack(df['embedding'].values)
    except Exception as e:
        logger.error(f"Failed to stack embeddings: {e}")
        return np.array([])
    return embeddings

def perform_clustering(embeddings: np.ndarray) -> Tuple[np.ndarray, Any, Any]:
    """
    Выполняет кластеризацию: UMAP снижение размерности, затем HDBSCAN.
    Возвращает: labels, reducer, clusterer.
    """
    if embeddings.shape[0] == 0:
        return np.array([]), None, None
    if embeddings.shape[0] < 2:
        logger.warning("Too few samples for clustering")
        return np.array([-1] * embeddings.shape[0]), None, None
    # Стандартизация
    scaler = StandardScaler()
    embeddings_scaled = scaler.fit_transform(embeddings)
    # UMAP
    reducer = umap.UMAP(n_components=settings.UMAP_N_COMPONENTS, random_state=42)
    embedding_umap = reducer.fit_transform(embeddings_scaled)
    # HDBSCAN
    clusterer = hdbscan.HDBSCAN(min_cluster_size=settings.HDBSCAN_MIN_CLUSTER_SIZE)
    labels = clusterer.fit_predict(embedding_umap)
    return labels, reducer, clusterer

def get_terms_for_cluster(df: pd.DataFrame, labels: np.ndarray, cluster_id: int, top_n: int = 5) -> List[str]:
    """
    Для заданного кластера возвращает топ-N частотных слов (терминов) из текстов.
    """
    mask = labels == cluster_id
    texts = df.loc[mask, 'text'].tolist()
    if not texts:
        return []
    from collections import Counter
    import re
    word_counter = Counter()
    for text in texts:
        words = re.findall(r'\b\w+\b', text.lower())
        word_counter.update(words)
    stopwords = {'и', 'в', 'на', 'с', 'по', 'к', 'у', 'о', 'для', 'из', 'за', 'так', 'что', 'это', 'как', 'все', 'или'}
    top_words = [w for w, _ in word_counter.most_common(top_n + len(stopwords)) if w not in stopwords][:top_n]
    return top_words

def compute_drift_score(embeddings_old: np.ndarray, embeddings_new: np.ndarray) -> float:
    """
    Вычисляет Wasserstein Distance (Earth Mover's Distance) между распределениями двух наборов векторов.
    """
    if embeddings_old.shape[0] == 0 or embeddings_new.shape[0] == 0:
        return 0.0
    dim = embeddings_old.shape[1]
    distances = []
    for d in range(dim):
        dist = wasserstein_distance(embeddings_old[:, d], embeddings_new[:, d])
        distances.append(dist)
    avg_dist = np.mean(distances)
    return avg_dist

async def analyze_user(user_id: str, weeks: int) -> Dict[str, Any]:
    """
    Основная функция анализа:
    - загружает данные за последние 'weeks' и предыдущую неделю,
    - выполняет кластеризацию для каждой недели,
    - вычисляет дрифт,
    - возвращает отчёт.
    """
    # Загружаем данные за текущую неделю (последние 7 дней)
    end_current = datetime.now()
    start_current = end_current - timedelta(days=7)
    df_current = await load_vectors_for_period(user_id, start_current, end_current)

    # Загружаем данные за предыдущую неделю (8-14 дней назад)
    end_previous = start_current - timedelta(days=1)
    start_previous = end_previous - timedelta(days=7)
    df_previous = await load_vectors_for_period(user_id, start_previous, end_previous)

    if df_current.empty and df_previous.empty:
        return {"error": "Нет данных для анализа"}

    # Если данных за одну из недель нет – используем то, что есть
    if df_current.empty:
        return {"error": f"Нет данных за текущую неделю"}
    if df_previous.empty:
        # Анализируем только текущую неделю
        embeddings_cur = compute_embeddings_matrix(df_current)
        if embeddings_cur.size == 0:
            return {"error": "Нет эмбеддингов для анализа"}
        labels_cur, _, _ = perform_clustering(embeddings_cur)
        clusters_info = {}
        unique_labels = set(labels_cur)
        for label in unique_labels:
            if label != -1:
                terms = get_terms_for_cluster(df_current, labels_cur, label)
                clusters_info[f"cluster_{label}"] = {"size": int(np.sum(labels_cur == label)), "terms": terms}
        return {
            "drift_score": 0.0,
            "shifted_topics": [],
            "cluster_details": {
                "current_week": {"clusters": clusters_info, "total_samples": len(labels_cur)},
                "previous_week": {"clusters": {}, "total_samples": 0}
            }
        }

    # Обе недели есть – вычисляем кластеры и дрифт
    embeddings_cur = compute_embeddings_matrix(df_current)
    embeddings_prev = compute_embeddings_matrix(df_previous)

    if embeddings_cur.size == 0 or embeddings_prev.size == 0:
        return {"error": "Нет эмбеддингов для анализа"}

    labels_cur, _, _ = perform_clustering(embeddings_cur)
    labels_prev, _, _ = perform_clustering(embeddings_prev)

    # Вычисляем дрифт
    drift = compute_drift_score(embeddings_prev, embeddings_cur)

    # Собираем информацию о кластерах для текущей и предыдущей недели
    clusters_cur = {}
    for label in set(labels_cur):
        if label != -1:
            terms = get_terms_for_cluster(df_current, labels_cur, label)
            clusters_cur[f"cluster_{label}"] = {"size": int(np.sum(labels_cur == label)), "terms": terms}

    clusters_prev = {}
    for label in set(labels_prev):
        if label != -1:
            terms = get_terms_for_cluster(df_previous, labels_prev, label)
            clusters_prev[f"cluster_{label}"] = {"size": int(np.sum(labels_prev == label)), "terms": terms}

    # Поиск сместившихся тем (простое сопоставление)
    shifted = []
    if clusters_prev and clusters_cur:
        prev_items = list(clusters_prev.items())
        cur_items = list(clusters_cur.items())
        for i in range(min(len(prev_items), len(cur_items))):
            prev_terms = prev_items[i][1]["terms"]
            cur_terms = cur_items[i][1]["terms"]
            if prev_terms != cur_terms:
                shifted.append({"old_terms": prev_terms, "new_terms": cur_terms})

    return {
        "drift_score": drift,
        "shifted_topics": shifted,
        "cluster_details": {
            "current_week": {"clusters": clusters_cur, "total_samples": len(labels_cur)},
            "previous_week": {"clusters": clusters_prev, "total_samples": len(labels_prev)}
        }
    }