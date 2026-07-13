import asyncio
import json
import os
from datetime import datetime
from .config import SOURCES, OUTPUT_DIR
from .parser import fetch_articles_from_source
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def save_articles(articles, source_name):
    """Сохраняет список статей в один JSON-файл по источнику и дате."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime('%Y-%m-%d')
    filename = f"{source_name}_{date_str}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    data = [article.model_dump(mode='json', exclude_none=True) for article in articles]
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"Сохранено {len(articles)} статей в {filepath}")

async def main():
    print("Запуск ingestor (асинхронный)...")
    for source in SOURCES:
        articles = await fetch_articles_from_source(source, limit=5)  # по 5 для теста
        if articles:
            await save_articles(articles, source.split('/')[2])
        else:
            print(f"Не удалось извлечь статьи из {source}")

if __name__ == "__main__":
    asyncio.run(main())