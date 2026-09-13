import logging
from typing import Dict, Any
from .settings import settings
from .strategies import BaseEmbedder, LocalHuggingFaceEmbedder, OpenAIAPIEmbedder

logger = logging.getLogger(__name__)


class EmbedderFactory:
    """
    Фабрика стратегий векторизации (Этап 6).
    
    По конфигурации модели из реестра возвращает нужный экземпляр стратегии.
    Кэширует локальные модели, чтобы не загружать их в RAM повторно.
    """

    def __init__(self):
        # Кэш загруженных локальных моделей (ключ — путь к модели)
        self._loaded_local_models: Dict[str, LocalHuggingFaceEmbedder] = {}

    def get_strategy(self, model_config: Dict[str, Any]) -> BaseEmbedder:
        """
        Возвращает экземпляр стратегии по конфигурации модели из реестра.
        
        :param model_config: Словарь с конфигурацией модели (из таблицы ai_models).
        :return: Экземпляр стратегии (LocalHuggingFaceEmbedder или OpenAIAPIEmbedder).
        :raises ValueError: Если provider_type неизвестен или отсутствует.
        """
        provider_type = model_config.get("provider_type")
        slug = model_config.get("slug", "unknown")

        if provider_type == "local_huggingface":
            return self._get_local_strategy(model_config)
        elif provider_type == "openai_api":
            return self._get_api_strategy(model_config)
        else:
            raise ValueError(
                f"Неизвестный provider_type '{provider_type}' для модели '{slug}'"
            )

    def _get_local_strategy(self, model_config: Dict[str, Any]) -> LocalHuggingFaceEmbedder:
        """Возвращает локальную стратегию с кэшированием по пути к модели."""
        model_path = model_config["model_path"]
        if model_path not in self._loaded_local_models:
            logger.info(f"🏭 Фабрика: загружаю локальную модель '{model_path}'")
            self._loaded_local_models[model_path] = LocalHuggingFaceEmbedder(model_path)
        else:
            logger.info(f"🏭 Фабрика: использую кэшированную модель '{model_path}'")
        return self._loaded_local_models[model_path]

    def _get_api_strategy(self, model_config: Dict[str, Any]) -> OpenAIAPIEmbedder:
        """Возвращает API-стратегию. Ключ берётся из env (безопасность) или из БД."""
        slug = model_config.get("slug", "unknown")
        # Ключ берём из переменных окружения (безопасность!), если нет — из БД
        api_key = settings.YA_AI_PROXY_KEY or model_config.get("api_key")
        if not api_key:
            raise ValueError(
                f"API ключ не задан для модели '{slug}' "
                f"(проверьте переменную окружения YA_AI_PROXY_KEY)"
            )
        logger.info(f"🏭 Фабрика: создаю API-стратегию для '{slug}'")
        return OpenAIAPIEmbedder(
            base_url=model_config["base_url"],
            api_key=api_key,
            model_name=model_config["model_name"],
        )