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
    Стратегия для моделей через OpenAI-совместимый API (Яндекс через Timeweb AI Gateway).
    Этап 5: добавлена обработка лимитов (429), серверных ошибок (5xx),
    экспоненциальная задержка и параллельный батчинг с ограничением конкурентности.
    """

    MAX_RETRIES = 3          # Максимум повторных попыток при временных ошибках
    BASE_DELAY = 1.0         # Базовая задержка для экспоненциального отката (сек)
    MAX_CONCURRENCY = 3      # Максимум параллельных запросов, чтобы не упереться в лимиты

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name

    async def _embed_single_with_retry(self, text: str, index: int, total: int) -> list:
        """Векторизует один текст с повторными попытками и экспоненциальной задержкой."""
        loop = asyncio.get_running_loop()
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"Векторизация текста {index+1}/{total} через API (попытка {attempt+1})")
                response = await loop.run_in_executor(
                    None,
                    lambda: self.client.embeddings.create(input=text, model=self.model_name),
                )
                return response.data[0].embedding
            except Exception as e:
                last_error = e
                error_str = str(e)
                # Повторяем только при временных ошибках: 429 (лимиты) и 5xx (серверные)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()
                is_server_error = any(code in error_str for code in ("500", "502", "503", "504"))

                if is_rate_limit or is_server_error:
                    delay = self.BASE_DELAY * (2 ** attempt)  # 1с -> 2с -> 4с
                    logger.warning(
                        f"Временная ошибка для текста {index+1}/{total} "
                        f"(попытка {attempt+1}): {error_str}. Повтор через {delay:.1f}с"
                    )
                    await asyncio.sleep(delay)
                else:
                    # Для ошибок 400/401 повторять бессмысленно — падаем сразу
                    logger.error(f"Ошибка API при обработке текста {index+1}: {e}")
                    logger.error(f"Текст (первые 100 символов): {text[:100]}...")
                    raise

        # Все попытки исчерпаны
        logger.error(f"❌ Все {self.MAX_RETRIES} попытки исчерпаны для текста {index+1}")
        raise last_error

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

        # Ограничиваем число параллельных запросов, чтобы не упереться в лимиты
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

        async def _limited_embed(text: str, index: int):
            async with semaphore:
                return await self._embed_single_with_retry(text, index, len(texts))

        # Отправляем запросы параллельно (с ограничением); порядок результатов сохраняется
        tasks = [_limited_embed(text, i) for i, text in enumerate(texts)]
        all_embeddings = await asyncio.gather(*tasks)

        logger.info(f"✅ Успешно векторизовано {len(all_embeddings)} текстов через API")
        return np.array(all_embeddings)