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

logger = logging.getLogger(__name__)

# def load_vectors_for_week(user_id: str, week_date: datetime) -> pd.DataFrame:
#     """
#     Загружает Parquet-файл для указанной недели (по дате начала недели).
#     Возвращает DataFrame с колонками: article_id, chunk_index, text, embedding, source, published_at.
#     """
#     date_str = week_date.strftime("%Y-%m-%d")
#     filepath = os.path.join(settings.VECTORS_ROOT, f"user_{user_id}", f"{date_str}.parquet")
#     if not os.path.exists(filepath):
#         logger.warning(f"Файл {filepath} не найден")
#         return pd.DataFrame()
#     table = pq.read_table(filepath)
#     df = table.to_pandas()
#     return df

def load_vectors_for_period(user_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Загружает все Parquet-файлы пользователя за указанный период и объединяет их."""
    user_dir = os.path.join(settings.VECTORS_ROOT, f"user_{user_id}")
    if not os.path.exists(user_dir):
        return pd.DataFrame()
    all_dfs = []
    for filename in os.listdir(user_dir):
        if not filename.endswith('.parquet'):
            continue
        # Извлекаем дату из имени файла (формат YYYY-MM-DD.parquet)
        try:
            date_str = filename.split('.')[0]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if start_date <= file_date <= end_date:
                filepath = os.path.join(user_dir, filename)
                df = pd.read_parquet(filepath)
                all_dfs.append(df)
        except Exception:
            continue
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)

def compute_embeddings_matrix(df: pd.DataFrame) -> np.ndarray:
    """Извлекает векторы из колонки 'embedding' и возвращает матрицу (n_samples, dim)."""
    if df.empty:
        return np.array([])
    # Столбец 'embedding' содержит список float
    embeddings = np.stack(df['embedding'].values)
    return embeddings

def perform_clustering(embeddings: np.ndarray) -> Tuple[np.ndarray, Any, Any]:
    """
    Выполняет кластеризацию: UMAP снижение размерности, затем HDBSCAN.
    Возвращает: labels, reducer, clusterer.
    """
    if embeddings.shape[0] == 0:
        return np.array([]), None, None
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
    # Простой подсчёт слов (можно улучшить с использованием TF-IDF)
    from collections import Counter
    import re
    word_counter = Counter()
    for text in texts:
        words = re.findall(r'\b\w+\b', text.lower())
        word_counter.update(words)
    # Убираем стоп-слова (можно добавить список)
    stopwords = {'и', 'в', 'на', 'с', 'по', 'к', 'у', 'о', 'для', 'из', 'за', 'так', 'что', 'это', 'как', 'все', 'или'}
    top_words = [w for w, _ in word_counter.most_common(top_n + len(stopwords)) if w not in stopwords][:top_n]
    return top_words

def compute_drift_score(embeddings_old: np.ndarray, embeddings_new: np.ndarray) -> float:
    """
    Вычисляет Wasserstein Distance (Earth Mover's Distance) между распределениями двух наборов векторов.
    Возвращает нормализованное значение (0..1).
    """
    if embeddings_old.shape[0] == 0 or embeddings_new.shape[0] == 0:
        return 0.0
    # Для каждой размерности считаем EMD между одномерными распределениями
    # и усредняем по всем размерностям (или можно использовать многомерную версию, но она сложнее)
    # Упрощённо: используем среднее EMD по всем размерностям.
    dim = embeddings_old.shape[1]
    distances = []
    for d in range(dim):
        dist = wasserstein_distance(embeddings_old[:, d], embeddings_new[:, d])
        distances.append(dist)
    avg_dist = np.mean(distances)
    # Нормализуем: максимальное возможное расстояние зависит от размаха данных, но для простоты поделим на 10 (эмпирически)
    # Либо можно использовать сигмоиду или просто вернуть сырое значение, а интерпретацию оставить на потом.
    # Возвращаем сырое среднее EMD
    return avg_dist

def analyze_user(user_id: str, weeks: int) -> Dict[str, Any]:
    """
    Основная функция анализа:
    - загружает данные за последние 'weeks' и предыдущую неделю,
    - выполняет кластеризацию для каждой недели,
    - вычисляет дрифт,
    - возвращает отчёт.
    """
    # Определяем даты: сегодняшняя дата, начало текущей недели (понедельник) и предыдущей
    today = datetime.now()
    # Начало текущей недели (понедельник)
    start_current = today - timedelta(days=today.weekday())
    start_previous = start_current - timedelta(weeks=1)

    # Загружаем данные за текущую неделю (файл за понедельник)
    # df_current = load_vectors_for_week(user_id, start_current)
    # df_previous = load_vectors_for_week(user_id, start_previous)

    # # Загружаем данные за текущую неделю (последние 7 дней)
    # end_current = datetime.now()
    # start_current = end_current - timedelta(days=7)
    # df_current = load_vectors_for_period(user_id, start_current, end_current)

    # # Загружаем данные за предыдущую неделю (8-14 дней назад)
    # end_previous = start_current - timedelta(days=1)
    # start_previous = end_previous - timedelta(days=7)
    # df_previous = load_vectors_for_period(user_id, start_previous, end_previous)

    # Загружаем все доступные файлы
    all_files = load_all_vectors_for_user(user_id)
    if all_files.empty:
        return {"error": "Нет данных для анализа"}

    # Разделяем на две части: последние 7 дней и предыдущие 7 дней
    end_current = datetime.now()
    start_current = end_current - timedelta(days=7)
    df_current = all_files[all_files['file_date'] >= start_current]
    df_previous = all_files[all_files['file_date'] < start_current]

    if df_current.empty and df_previous.empty:
        return {"error": "Нет данных для анализа"}

    # Если данных за одну из недель нет – используем то, что есть
    if df_current.empty:
        # Анализируем только предыдущую неделю?
        # Пока возвращаем ошибку
        return {"error": f"Нет данных за текущую неделю ({start_current.strftime('%Y-%m-%d')})"}
    if df_previous.empty:
        # Если нет предыдущей недели, то дрифт не считается, но можно сделать кластеризацию текущей
        embeddings_cur = compute_embeddings_matrix(df_current)
        labels_cur, _, _ = perform_clustering(embeddings_cur)
        # Собираем информацию о кластерах
        clusters_info = {}
        unique_labels = set(labels_cur)
        for label in unique_labels:
            if label != -1:  # -1 означает шум
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

    # Поиск сместившихся тем (простейший подход: сопоставляем кластеры по размеру и терминам)
    # Упрощённо: если кластер из предыдущей недели исчез или значительно изменился, считаем это сдвигом.
    # Здесь можно реализовать более сложную логику, но для прототипа оставим заглушку.
    shifted = []
    if clusters_prev and clusters_cur:
        # Для демонстрации: берём первые кластеры и сравниваем термины (очень упрощённо)
        prev_items = list(clusters_prev.items())
        cur_items = list(clusters_cur.items())
        for i in range(min(len(prev_items), len(cur_items))):
            prev_terms = prev_items[i][1]["terms"]
            cur_terms = cur_items[i][1]["terms"]
            if prev_terms != cur_terms:
                shifted.append({"old_terms": prev_terms, "new_terms": cur_terms})
    # Если не удалось сопоставить, оставляем пустой список

    return {
        "drift_score": drift,
        "shifted_topics": shifted,
        "cluster_details": {
            "current_week": {"clusters": clusters_cur, "total_samples": len(labels_cur)},
            "previous_week": {"clusters": clusters_prev, "total_samples": len(labels_prev)}
        }
    }

def load_all_vectors_for_user(user_id: str) -> pd.DataFrame:
    """Загружает все Parquet-файлы пользователя и добавляет колонку file_date."""
    user_dir = os.path.join(settings.VECTORS_ROOT, f"user_{user_id}")
    if not os.path.exists(user_dir):
        return pd.DataFrame()
    all_dfs = []
    for filename in os.listdir(user_dir):
        if not filename.endswith('.parquet'):
            continue
        try:
            date_str = filename.split('.')[0]
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            filepath = os.path.join(user_dir, filename)
            df = pd.read_parquet(filepath)
            df['file_date'] = file_date
            all_dfs.append(df)
        except Exception as e:
            logger.warning(f"Не удалось загрузить {filename}: {e}")
            continue
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)