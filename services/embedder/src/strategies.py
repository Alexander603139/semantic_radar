import logging
import numpy as np
import asyncio
from abc import ABC, abstractmethod
from typing import List
from sentence_transformers import SentenceTransformer
from openai import OpenAI

logger = logging.getLogger(__name__)

class BaseEmbedder(ABC):
    @abstractmethod
    async def embed_texts(self, texts: List[str], requires_prefix: bool = False) -> np.ndarray:
        pass

class LocalHuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, model_path: str):
        logger.info(f"Загрузка локальной модели {model_path}...")
        self.model = SentenceTransformer(model_path)
        logger.info(f"Модель {model_path} успешно загружена в RAM")

    async def embed_texts(self, texts: List[str], requires_prefix: bool = False) -> np.ndarray:
        if requires_prefix:
            texts = [f"passage: {t}" for t in texts]
        loop = asyncio.get_running_loop()
        # run_in_executor предотвращает блокировку event loop'а во время CPU-вычислений
        embeddings = await loop.run_in_executor(
            None, 
            lambda: self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        )
        return embeddings

class OpenAIAPIEmbedder(BaseEmbedder):
    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model_name = model_name

    async def embed_texts(self, texts: List[str], requires_prefix: bool = False) -> np.ndarray:
        if requires_prefix:
            texts = [f"passage: {t}" for t in texts]
        
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
                    lambda t=text: self.client.embeddings.create(input=t, model=self.model_name)
                )
                # Берём первый (и единственный) эмбеддинг из ответа
                embedding = response.data[0].embedding
                all_embeddings.append(embedding)
            except Exception as e:
                logger.error(f"Ошибка API при обработке текста {i+1}: {e}")
                logger.error(f"Текст (первые 100 символов): {text[:100]}...")
                raise
                
        logger.info(f"✅ Успешно векторизовано {len(all_embeddings)} текстов через API")
        return np.array(all_embeddings)