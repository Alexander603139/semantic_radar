import asyncio
import uuid
from datetime import datetime
from typing import List
import logging
from .parser import fetch_articles_from_source
from .models import Article
from .settings import settings
from .embedder_client import call_embedder
import json
import os
import httpx
import io

logger = logging.getLogger(__name__)

# Хранилище статусов задач (в памяти, для прототипа)
tasks_store = {}

OUTPUT_DIR = settings.OUTPUT_DIR

async def run_parsing_task(user_id: str, sources: List[str], limit: int) -> str:
    task_id = str(uuid.uuid4())
    tasks_store[task_id] = {"status": "running", "result": None, "error": None}
    try:
        logger.info(f"Запуск задачи {task_id} для пользователя {user_id}")
        all_articles = []
        for site in sources:
            articles = await fetch_articles_from_source(site, limit=limit)
            if articles:
                all_articles.extend(articles)
                
                # # Сохраняем JSON для источника (как раньше)
                # source_name = site.split('/')[2]
                # date_str = datetime.now().strftime('%Y-%m-%d')
                # os.makedirs(OUTPUT_DIR, exist_ok=True)
                # filename = f"{source_name}_{date_str}.json"
                # filepath = os.path.join(OUTPUT_DIR, filename)
                # data = [art.model_dump(mode='json', exclude_none=True) for art in articles]
                # with open(filepath, 'w', encoding='utf-8') as f:
                #     json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                # logger.info(f"Сохранено {len(articles)} статей в {filepath}")


                # Сохраняем статьи в storage
                source_name = site.split('/')[2]
                await save_articles_to_storage(user_id, articles, source_name)
            else:
                logger.warning(f"Не найдено статей для {site}")

        # Вызов embedder
        if all_articles:
            success = await call_embedder(user_id, all_articles)
            if not success:
                logger.warning(f"Embedder не смог обработать статьи для {user_id}, но парсинг выполнен.")

        tasks_store[task_id]["status"] = "completed"
        tasks_store[task_id]["result"] = {
            "total_articles": len(all_articles),
            "sources_processed": len(sources)
        }
        logger.info(f"Задача {task_id} завершена")
    except Exception as e:
        logger.error(f"Ошибка в задаче {task_id}: {e}")
        tasks_store[task_id]["status"] = "failed"
        tasks_store[task_id]["error"] = str(e)
    return task_id

async def save_articles_to_storage(user_id: str, articles: List[Article], source_name: str) -> bool:
    """
    Сохраняет статьи в storage через API.
    Возвращает True при успехе, иначе False.
    """
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{source_name}_{date_str}.json"
    
    # Формируем JSON
    json_data = json.dumps(
        [art.model_dump(mode='json', exclude_none=True, default=str) for art in articles],
        ensure_ascii=False,
        indent=2
    )
    file_bytes = io.BytesIO(json_data.encode('utf-8'))
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        files = {'file': (filename, file_bytes, 'application/json')}
        data = {
            'user_id': user_id,
            'file_type': 'articles',
            'file_key': filename,
            'metadata': json.dumps({"source": source_name, "count": len(articles)})
        }
        try:
            resp = await client.post(
                f"{settings.STORAGE_URL}/upload",
                files=files,
                data=data
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Статьи сохранены в storage: file_id={result.get('id')}, статей={len(articles)}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения статей в storage: {e}")
            # fallback: сохранить локально
            os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(settings.OUTPUT_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(
                    [art.model_dump(mode='json', exclude_none=True, default=str) for art in articles],
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str
                )
            logger.info(f"Статьи сохранены локально (fallback): {filepath}")
            return False