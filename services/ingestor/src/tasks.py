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

# async def run_parsing_task(user_id: str, sources: List[str], limit: int, auto_analyze: bool = False) -> str:
#     task_id = str(uuid.uuid4())
#     tasks_store[task_id] = {"status": "running", "result": None, "error": None}
#     try:
#         logger.info(f"Запуск задачи {task_id} для пользователя {user_id}")
#         all_articles = []
#         for site in sources:
#             articles = await fetch_articles_from_source(site, limit=limit)
#             if articles:
#                 all_articles.extend(articles)
#                 source_name = site.split('/')[2]
#                 await save_articles_to_storage(user_id, articles, source_name)
#             else:
#                 logger.warning(f"Не найдено статей для {site}")
        
#         # Вызов embedder (всегда, если есть статьи)
#         if all_articles:
#             success = await call_embedder(user_id, all_articles)
#             if not success:
#                 logger.warning(f"Embedder не смог обработать статьи для {user_id}, но парсинг выполнен.")
        
#         # --- АВТОМАТИЧЕСКИЙ АНАЛИЗ И ОТЧЁТ (только для запуска по расписанию) ---
#         if all_articles and auto_analyze:
#             logger.info(f"Запуск автоматического анализа и генерации отчёта для {user_id}")
#             try:
#                 async with httpx.AsyncClient(timeout=60.0) as client:
#                     # 1. Анализ
#                     analyze_resp = await client.post(
#                         "http://analyzer:8004/analyze",
#                         json={"user_id": user_id, "weeks": 2}
#                     )
#                     analyze_resp.raise_for_status()
#                     analysis_data = analyze_resp.json()
#                     logger.info(f"Анализ выполнен успешно для {user_id}")
                    
#                     # 2. Отчёт
#                     report_resp = await client.post(
#                         "http://reporter:8005/generate",
#                         json={"user_id": user_id, "analysis_result": analysis_data}
#                     )
#                     report_resp.raise_for_status()
#                     report_data = report_resp.json()
#                     logger.info(f"Отчёт сгенерирован: {report_data.get('report_url')}")
#             except Exception as e:
#                 logger.error(f"Ошибка при автоматическом анализе/отчёте для {user_id}: {e}")
        
#         tasks_store[task_id]["status"] = "completed"
#         tasks_store[task_id]["result"] = {
#             "total_articles": len(all_articles),
#             "sources_processed": len(sources)
#         }
#         logger.info(f"Задача {task_id} завершена")
#     except Exception as e:
#         logger.error(f"Ошибка в задаче {task_id}: {e}")
#         tasks_store[task_id]["status"] = "failed"
#         tasks_store[task_id]["error"] = str(e)
#     return task_id

async def run_parsing_task(user_id: str, sources: List[str], limit: int, auto_analyze: bool = False) -> str:
    task_id = str(uuid.uuid4())
    tasks_store[task_id] = {"status": "running", "result": None, "error": None}
    try:
        logger.info(f"Запуск задачи {task_id} для пользователя {user_id}")
        
        # ==========================================
        # ШАГ 1: Собираем ВСЕ статьи без сохранения
        # (чтобы можно было фильтровать ДО записи в storage)
        # ==========================================
        all_articles = []
        articles_by_source = {}  # Для последующей группировки
        
        for site in sources:
            articles = await fetch_articles_from_source(site, limit=limit)
            if articles:
                all_articles.extend(articles)
                source_name = site.split('/')[2]
                articles_by_source[source_name] = articles
                logger.info(f"📥 Собрано {len(articles)} статей с {source_name}")
            else:
                logger.warning(f"Не найдено статей для {site}")
        
        total_collected = len(all_articles)
        logger.info(f"📊 Всего собрано статей: {total_collected}")
        
        # ==========================================
        # ШАГ 2: СЕМАНТИЧЕСКАЯ ФИЛЬТРАЦИЯ (Этап 4)
        # ==========================================
        if all_articles:
            # 2.1 Читаем актуальные настройки пользователя (контекст и порог)
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    settings_resp = await client.get(f"{settings.STORAGE_URL}/settings/{user_id}")
                    settings_resp.raise_for_status()
                    user_settings = settings_resp.json()
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось загрузить настройки из storage: {e}. Продолжаем без фильтрации.")
                    user_settings = {}
            
            context = (user_settings.get("context") or "").strip()
            threshold = float(user_settings.get("threshold", 0.6))
            
            # 2.2 Если контекст задан, применяем фильтр
            if context:
                logger.info(f"🎯 Применяем семантический фильтр: контекст='{context}', порог={threshold}")
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        filter_resp = await client.post(
                            "http://context_filter:8010/filter",
                            json={
                                "user_id": user_id,
                                "context": context,
                                "threshold": threshold,
                                "articles": [art.model_dump(mode='json', exclude_none=True, default=str) for art in all_articles]
                            }
                        )
                        filter_resp.raise_for_status()
                        filter_data = filter_resp.json()
                    
                    logger.info(
                        f"✅ Фильтр: получено {filter_data['total_received']}, "
                        f"прошло {filter_data['total_passed']}, отклонено {filter_data['total_filtered']}"
                    )
                    
                    # 2.3 Заменяем all_articles на отфильтрованный список
                    from .models import Article
                    all_articles = [Article(**art) for art in filter_data["articles"]]
                    
                    # 2.4 Пересчитываем группировку по источникам (для корректного сохранения)
                    articles_by_source = {}
                    for art in all_articles:
                        source_name = art.source or "unknown"
                        if source_name not in articles_by_source:
                            articles_by_source[source_name] = []
                        articles_by_source[source_name].append(art)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при вызове context_filter: {e}. Продолжаем без фильтрации.")
            else:
                logger.info("ℹ️ Контекст не задан, фильтрация пропущена.")
        else:
            logger.info("⚠️ Нет статей для обработки.")
        
        # ==========================================
        # ШАГ 3: Сохраняем ТОЛЬКО прошедшие фильтр статьи
        # ==========================================
        if all_articles:
            for source_name, source_articles in articles_by_source.items():
                await save_articles_to_storage(user_id, source_articles, source_name)
            logger.info(f"💾 В storage сохранено {len(all_articles)} отфильтрованных статей")
        else:
            logger.info("⚠️ После фильтрации не осталось статей. Сохранение пропущено.")
        
        # ==========================================
        # ШАГ 4: Вызов embedder (векторизация чанков)
        # ==========================================
        if all_articles:
            success = await call_embedder(user_id, all_articles)
            if not success:
                logger.warning(f"Embedder не смог обработать статьи для {user_id}, но парсинг выполнен.")
        
        # ==========================================
        # ШАГ 5: АВТОМАТИЧЕСКИЙ АНАЛИЗ И ОТЧЁТ (только по расписанию)
        # ==========================================
        if all_articles and auto_analyze:
            logger.info(f"Запуск автоматического анализа и генерации отчёта для {user_id}")
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # 1. Анализ
                    analyze_resp = await client.post(
                        "http://analyzer:8004/analyze",
                        json={"user_id": user_id, "weeks": 2}
                    )
                    analyze_resp.raise_for_status()
                    analysis_data = analyze_resp.json()
                    logger.info(f"Анализ выполнен успешно для {user_id}")
                    
                    # 2. Отчёт
                    report_resp = await client.post(
                        "http://reporter:8005/generate",
                        json={"user_id": user_id, "analysis_result": analysis_data}
                    )
                    report_resp.raise_for_status()
                    report_data = report_resp.json()
                    logger.info(f"Отчёт сгенерирован: {report_data.get('report_url')}")
            except Exception as e:
                logger.error(f"Ошибка при автоматическом анализе/отчёте для {user_id}: {e}")
        
        tasks_store[task_id]["status"] = "completed"
        tasks_store[task_id]["result"] = {
            "total_collected": total_collected,
            "total_articles": len(all_articles),
            "filtered_count": total_collected - len(all_articles),
            "sources_processed": len(sources)
        }
        logger.info(f"Задача {task_id} завершена: собрано {total_collected}, после фильтра {len(all_articles)}")
        
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
    # json_data = json.dumps(
    #     [art.model_dump(mode='json', exclude_none=True, default=str) for art in articles],
    #     ensure_ascii=False,
    #     indent=2
    # )
    json_data = json.dumps(
        [art.model_dump(mode='json', exclude_none=True) for art in articles],
        ensure_ascii=False,
        indent=2,
        default=str
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
            # with open(filepath, 'w', encoding='utf-8') as f:
            #     json.dump(
            #         [art.model_dump(mode='json', exclude_none=True, default=str) for art in articles],
            #         f,
            #         ensure_ascii=False,
            #         indent=2,
            #         default=str
            #     )
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(
                    [art.model_dump(mode='json', exclude_none=True) for art in articles],
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str
                )
            logger.info(f"Статьи сохранены локально (fallback): {filepath}")
            return False