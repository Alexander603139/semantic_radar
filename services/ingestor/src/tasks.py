import asyncio
import uuid
from datetime import datetime
from typing import List
import logging
from .parser import fetch_articles_from_source
from .models import Article
from .config import OUTPUT_DIR
from .embedder_client import call_embedder
import json
import os

logger = logging.getLogger(__name__)

# Хранилище статусов задач (в памяти, для прототипа)
tasks_store = {}

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
                # Сохраняем JSON для источника (как раньше)
                source_name = site.split('/')[2]
                date_str = datetime.now().strftime('%Y-%m-%d')
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                filename = f"{source_name}_{date_str}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                data = [art.model_dump(mode='json', exclude_none=True) for art in articles]
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                logger.info(f"Сохранено {len(articles)} статей в {filepath}")
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