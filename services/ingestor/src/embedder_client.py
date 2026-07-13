import httpx
import logging
from .config import EMBEDDER_URL, EMBEDDER_MOCK

logger = logging.getLogger(__name__)

async def call_embedder(user_id: str, articles: list) -> bool:
    """
    Отправляет статьи в embedder для векторизации.
    Возвращает True при успехе, иначе False.
    """
    if EMBEDDER_MOCK:
        logger.info(f"[MOCK] Embedder вызван для user_id={user_id}, статей={len(articles)}")
        return True

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Формируем данные для отправки
            payload = {
                "user_id": user_id,
                "articles": [
                    {
                        "id": f"{art.source}_{art.published_at or art.scraped_at}",
                        "title": art.title,
                        "text": art.body,
                        "source": art.source,
                        "published_at": art.published_at.isoformat() if art.published_at else None
                    }
                    for art in articles
                ]
            }
            resp = await client.post(EMBEDDER_URL, json=payload)
            if resp.status_code == 200:
                logger.info(f"Embedder успешно обработал {len(articles)} статей для {user_id}")
                return True
            else:
                logger.error(f"Embedder вернул ошибку: {resp.status_code} - {resp.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при вызове embedder: {e}")
        return False