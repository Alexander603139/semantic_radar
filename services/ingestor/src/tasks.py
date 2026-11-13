import asyncio
import uuid
from datetime import datetime
from typing import List
import logging
from .parser import fetch_articles_from_source, collect_links_from_source, parse_articles_from_links, DEFAULT_TIMEOUT
from .models import Article
from .settings import settings
from .embedder_client import call_embedder
from typing import List, Tuple
import json
import os
import httpx
import io

logger = logging.getLogger(__name__)

# Хранилище статусов задач (в памяти, для прототипа)
tasks_store = {}

OUTPUT_DIR = settings.OUTPUT_DIR

async def run_parsing_task(user_id: str, sources: List[str], limit: int, auto_analyze: bool = False, task_id: str = None) -> str:
    if task_id is None:
        task_id = str(uuid.uuid4())
    tasks_store[task_id] = {"status": "running", "result": None, "error": None}
    try:
        logger.info(f"Запуск задачи {task_id} для пользователя {user_id}")
        
        # ==========================================
        # ШАГ 1: СБОР ССЫЛОК (быстро)
        # ==========================================
        all_links = []
        per_source_stats = {}
        failed_sources = []
        empty_sources = []
        
        for site in sources:
            stats = {
                "links_rss": 0, "links_html": 0, "links_total": 0, "links_used": 0,
                "articles_parsed": 0, "articles_skipped": 0, "articles_error": 0,
                "fetch_method": "none"
            }
            try:
                links = await collect_links_from_source(site, limit, stats)
                if links:
                    all_links.extend(links)
                else:
                    empty_sources.append(site.split('/')[2] if '/' in site else site)
            except Exception as e:
                stats["error"] = str(e)
                failed_sources.append(site.split('/')[2] if '/' in site else site)
                logger.error(f"❌ Ошибка при сборе ссылок {site}: {e}")
            per_source_stats[site.split('/')[2] if '/' in site else site] = stats

        logger.info(f"🔗 Всего собрано ссылок: {len(all_links)}")

        # ==========================================
        # ШАГ 2: ПАРСИНГ СТАТЕЙ (параллельно)
        # ==========================================
        all_articles = []
        articles_by_source = {}
        
        if all_links:
            logger.info("⏳ Начинаем параллельный парсинг статей...")
            dummy_stats = {}
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                all_articles = await parse_articles_from_links(all_links, client, dummy_stats)
            logger.info(f"✅ Спарсено статей: {len(all_articles)}")

        # Распределяем статьи по источникам
        from urllib.parse import urlparse
        for art in all_articles:
            source_name = art.source or "unknown"
            articles_by_source.setdefault(source_name, []).append(art)

        # Обновляем articles_parsed в per_source_stats
        for site_name, stats in per_source_stats.items():
            if site_name in articles_by_source:
                stats["articles_parsed"] = len(articles_by_source[site_name])

        total_collected = len(all_articles)
        logger.info(f"📊 Всего собрано статей: {total_collected}")
        if failed_sources:
            logger.warning(f"⚠️ Недоступно сайтов: {len(failed_sources)} ({', '.join(failed_sources)})")
        if empty_sources:
            logger.warning(f"⚠️ Пустые сайты (нет статей): {len(empty_sources)} ({', '.join(empty_sources)})")
        
        # ==========================================
        # ШАГ 2: СЕМАНТИЧЕСКАЯ ФИЛЬТРАЦИЯ (Этап 4)
        # ==========================================
        filter_status = "skipped_no_context"
        filter_stats = {}
        if all_articles:
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
                                "articles": [art.model_dump(mode='json', exclude_none=True) for art in all_articles]
                            }
                        )
                        filter_resp.raise_for_status()
                        filter_data = filter_resp.json()

                    filter_status = "applied"
                    filter_stats = {
                        "context": context,
                        "threshold": threshold,
                        "total_received": filter_data.get("total_received"),
                        "total_passed": filter_data.get("total_passed"),
                        "total_filtered": filter_data.get("total_filtered"),
                    }
                    logger.info(
                        f"✅ Фильтр: получено {filter_data['total_received']}, "
                        f"прошло {filter_data['total_passed']}, отклонено {filter_data['total_filtered']}"
                    )
                    
                    from .models import Article
                    all_articles = [Article(**art) for art in filter_data["articles"]]
                    articles_by_source = {}

                    for art in all_articles:
                        source_name = art.source or "unknown"
                        if source_name not in articles_by_source:
                            articles_by_source[source_name] = []
                        articles_by_source[source_name].append(art)
                    
                except Exception as e:
                    filter_status = "failed"
                    filter_stats = {"error": str(e), "context": context, "threshold": threshold}
                    logger.error(f"❌ Ошибка при вызове context_filter: {e}. Продолжаем без фильтрации.")
            else:
                logger.info("ℹ️ Контекст не задан, фильтрация пропущена.")
        else:
            logger.info("⚠️ Нет статей для обработки.")


        # ==========================================
        # ШАГ 2.5: ДЕДУПЛИКАЦИЯ (Уровень 5)
        # ==========================================
        if all_articles:
            unique_articles, dropped_count = deduplicate_articles(all_articles)
            if dropped_count > 0:
                logger.info(f"🧹 Дедупликация: удалено {dropped_count} дубликатов, осталось {len(unique_articles)} статей.")
                all_articles = unique_articles
                # Пересобираем articles_by_source после дедупликации
                articles_by_source = {}
                for art in all_articles:
                    source_name = art.source or "unknown"
                    articles_by_source.setdefault(source_name, []).append(art)

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
        # ШАГ 4: Вызов embedder
        # ==========================================
        if all_articles:
            success = await call_embedder(user_id, all_articles)
            if not success:
                logger.warning(f"Embedder не смог обработать статьи для {user_id}, но парсинг выполнен.")
        
        # ==========================================
        # ШАГ 5: АВТОМАТИЧЕСКИЙ АНАЛИЗ И ОТЧЁТ
        # ==========================================
        if all_articles and auto_analyze:
            logger.info(f"Запуск автоматического анализа и генерации отчёта для {user_id}")
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    analyze_resp = await client.post(
                        "http://analyzer:8004/analyze",
                        json={"user_id": user_id, "weeks": 2}
                    )
                    analyze_resp.raise_for_status()
                    analysis_data = analyze_resp.json()
                    
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
            "sources_processed": len(sources),
            "failed_sources": failed_sources,
            "empty_sources": empty_sources, 
            "per_source": per_source_stats,
            "filter_status": filter_status,
            "filter_stats": filter_stats,
            "total_links": len(all_links),
        }
        logger.info(f"Задача {task_id} завершена: собрано {total_collected}, после фильтра {len(all_articles)}")
        
    except Exception as e:
        logger.error(f"Ошибка в задаче {task_id}: {e}")
        tasks_store[task_id]["status"] = "failed"
        tasks_store[task_id]["error"] = str(e)
    return task_id

def deduplicate_articles(articles: List[Article]) -> Tuple[List[Article], int]:
    """
    Удаляет дубликаты по похожести заголовка (difflib) или по началу текста (hash).
    Возвращает (уникальные_статьи, количество_удаленных).
    """
    import difflib
    import hashlib
    import re
    
    unique = []
    dropped = 0
    
    for art in articles:
        is_dup = False
        
        # Нормализация заголовка (убираем пунктуацию и лишние пробелы)
        title_norm = re.sub(r'[^\w\s]', '', art.title.lower()).strip()
        
        # Хэш первых 500 символов нормализованного текста
        body_snippet = re.sub(r'\s+', ' ', art.body[:500].lower()).strip()
        body_hash = hashlib.md5(body_snippet.encode('utf-8')).hexdigest()
        
        for u in unique:
            u_title_norm = re.sub(r'[^\w\s]', '', u.title.lower()).strip()
            
            # 1. Проверка по заголовку
            ratio = difflib.SequenceMatcher(None, title_norm, u_title_norm).ratio()
            if ratio > 0.85:  # 85% сходства достаточно
                is_dup = True
                logger.info(f"    Дубликат по заголовку (ratio={ratio:.2f}): '{art.title}' ≈ '{u.title}'")
                break
                
            # 2. Проверка по тексту
            u_body_snippet = re.sub(r'\s+', ' ', u.body[:500].lower()).strip()
            u_body_hash = hashlib.md5(u_body_snippet.encode('utf-8')).hexdigest()
            if body_hash == u_body_hash:
                is_dup = True
                logger.info(f"    Дубликат по тексту: '{art.title}' == '{u.title}'")
                break
                
        if is_dup:
            dropped += 1
        else:
            unique.append(art)
            
    return unique, dropped

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