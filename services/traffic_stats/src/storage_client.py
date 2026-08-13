import logging
from .config import Settings

logger = logging.getLogger(__name__)

class StorageClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.STORAGE_SERVICE_URL

    async def save_task_data(self, task_id: str, raw_response: dict, parsed_data: list[dict]):
        """
        Отправляет данные во внутренний storage-сервис.
        """
        payload = {
            "task_id": task_id,
            "service_name": "traffic_stats",
            "raw": raw_response,
            "parsed": parsed_data
        }
        
        # Заглушка для MVP. Здесь будет реальный HTTP-запрос к storage сервису,
        # когда мы согласуем его внутренний API контракт.
        logger.info(f"Mocking save to storage for task {task_id}. Payload size: {len(str(payload))} bytes")
        
        # async with httpx.AsyncClient() as client:
        #     await client.post(f"{self.base_url}/internal/save_task", json=payload)