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
        
        all_embeddings = []
        batch_size = 20  # Безопасный размер батча для API, чтобы не упереться в лимиты токенов
        loop = asyncio.get_running_loop()
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            try:
                response = await loop.run_in_executor(
                    None, 
                    lambda: self.client.embeddings.create(input=batch, model=self.model_name)
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Ошибка API при обработке батча {i//batch_size}: {e}")
                raise
                
        return np.array(all_embeddings)