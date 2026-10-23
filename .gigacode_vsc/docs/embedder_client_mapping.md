# Маппинг body → text при вызове embedder

## Где находится embedder_client.py

Файл **существует** и находится здесь:
services/ingestor/src/embedder_client.py


## Как происходит преобразование

Маппинг выполняется **вручную в `embedder_client.py`** (строка 28) — при формировании JSON-пэйлоа:

```python
# ingestor/src/embedder_client.py, строки 22-34
payload = {
    "user_id": user_id,
    "articles": [
        {
            "id": f"{art.source}_{art.published_at or art.scraped_at}",
            "title": art.title,
            "text": art.body,        # ← ЗДЕСЬ: body → text
            "source": art.source,
            "published_at": art.published_at.isoformat() if art.published_at else None
        }
        for art in articles
    ]
}
Почему два разных поля
Каждая служба имеет свою модель Article с немного разными контрактами:

Служба	Модель	Поле с текстом
Ingestor	ingestor.models.Article	body: str
Embedder	embedder.models.Article	text: str
Это не одна и та же модель — они определены в разных сервисах и не синхронизируются.

Схема потока данных
Ingestor
  │ Article(body="...")
  │
  ▼
embedder_client.call_embedder(user_id, articles)
  │ Маппинг: art.body → "text"
  ▼
POST http://embedder:8002/embed
  │ {articles: [{text: "..."}]}
  ▼
Embedder API (routes.py)
  │ EmbedRequest.articles как Article(text="...")
  ▼
process_articles(request.articles)
  │ embedder.models.Article.text
  ▼
file_id, chunk_count

Полный путь вызова
Ingestor парсит статьи → Article(body="...")
tasks.py (строка 128) вызывает call_embedder(user_id, all_articles)
embedder_client.py (строки 22-34) формирует JSON, преобразуя body → text
Отправляет POST http://embedder:8002/embed
Embedder принимает в EmbedRequest.articles как Article(text="...")
process_articles в embedder.py работает с полем text
Поддержка MOCK
Также есть поддержка мока (строки 15-17) — если в .env ingestor установлен EMBEDDER_MOCK=true, реальный вызов embedder пропускается и возвращается True сразу. Это полезно для изолированного тестирования ingestor.