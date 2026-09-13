import logging
import numpy as np
import asyncio
from abc import ABC, abstractmethod
from typing import List
from sentence_transformers import SentenceTransformer
from openai import OpenAI

logger = logging.getLogger(__name__)

# Допустимые типы префиксов для моделей, требующих их (например, E5)
VALID_PREFIX_TYPES = ("passage", "query")


class BaseEmbedder(ABC):
    """
    Абстрактный базовый класс для всех стратегий векторизации.
    Каждая стратегия умеет превращать список текстов в матрицу эмбеддингов.
    """

    @abstractmethod
    async def embed_texts(
        self,
        texts: List[str],
        requires_prefix: bool = False,
        prefix_type: str = "passage",
    ) -> np.ndarray:
        """
        Векторизует список текстов.

        :param texts: Список текстов для векторизации.
        :param requires_prefix: Нужно ли добавлять префикс (для моделей типа E5).
        :param prefix_type: Тип префикса — "passage" (для документов) или "query" (для запросов).
        :return: numpy-массив эмбеддингов формы (n_texts, dimension).
        """
        pass

    @staticmethod
    def _apply_prefix(texts: List[str], prefix_type: str) -> List[str]:
        """Добавляет префикс к каждому тексту (используется моделями типа E5)."""
        if prefix_type not in VALID_PREFIX_TYPES:
            raise ValueError(
                f"Недопустимый prefix_type: {prefix_type}. "
                f"Ожидается один из {VALID_PREFIX_TYPES}"
            )
        return [f"{prefix_type}: {t}" for t in texts]


class LocalHuggingFaceEmbedder(BaseEmbedder):
    """
    Стратегия для локальных моделей на базе sentence-transformers (HuggingFace).
    Реализует требования Этапа 4 для intfloat/multilingual-e5-base:
    загружает модель по пути из реестра и поддерживает префиксы passage:/query:.
    """

    def __init__(self, model_path: str):
        logger.info(f"Загрузка локальной модели {model_path}...")
        self.model = SentenceTransformer(model_path)
        logger.info(f"Модель {model_path} успешно загружена в RAM")

    async def embed_texts(
        self,
        texts: List[str],
        requires_prefix: bool = False,
        prefix_type: str = "passage",
    ) -> np.ndarray:
        # Для моделей типа E5 добавляем префикс (passage для статей, query для запросов)
        if requires_prefix:
            texts = self._apply_prefix(texts, prefix_type)

        loop = asyncio.get_running_loop()
        # run_in_executor предотвращает блокировку event loop'а во время CPU-вычислений
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False),
        )
        return embeddings


class OpenAIAPIEmbedder(BaseEmbedder):
    """
    Стратегия для моделей, доступных через OpenAI-совместимый API
    (например, Yandex через Timeweb AI Gateway).
    """

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name

    async def embed_texts(
        self,
        texts: List[str],
        requires_prefix: bool = False,
        prefix_type: str = "passage",
    ) -> np.ndarray:
        # Для моделей типа E5 добавляем префикс (для Яндекса обычно requires_prefix=False)
        if requires_prefix:
            texts = self._apply_prefix(texts, prefix_type)

        # Фильтруем пустые строки и None
        texts = [t for t in texts if t and isinstance(t, str) and t.strip()]
        if not texts:
            logger.warning("Нет валидных текстов для векторизации")
            return np.array([])

        all_embeddings = []
        loop = asyncio.get_running_loop()

        # Отправляем по ОДНОЙ строке за раз (Яндекс не поддерживает батчи)
        for i, text in enumerate(texts):
            try:
                logger.debug(f"Векторизация текста {i+1}/{len(texts)} через API")
                response = await loop.run_in_executor(
                    None,
                    lambda t=text: self.client.embeddings.create(input=t, model=self.model_name),
                )
                embedding = response.data[0].embedding
                all_embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Ошибка API при обработке текста {i+1}: {e}")
                logger.error(f"Текст (первые 100 символов): {text[:100]}...")
                raise

        logger.info(f"✅ Успешно векторизовано {len(all_embeddings)} текстов через API")
        return np.array(all_embeddings)