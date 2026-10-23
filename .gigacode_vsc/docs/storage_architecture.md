# Архитектура хранилища файлов

## Двойное хранение: S3 + PostgreSQL

Файлы (статьи, векторы, отчёты) хранятся **и в S3-совместимом объектном хранилище, и в PostgreSQL**. Это разделение ответственности:

| Что хранится | Где | Зачем |
|---|---|---|
| Бинарные файлы (Parquet-векторы, HTML-отчёты, статьи) | **S3** (объектное хранилище) | Эффективное хранение больших бинарных данных |
| Метаданные файлов (user_id, file_type, file_key, storage_path, checksum, extra_metadata) | **PostgreSQL** (таблица `files`) | Быстрый поиск, фильтрация, связи |
| Настройки пользователей (источники, cron, active_model_slug) | **PostgreSQL** (таблица `user_settings`) | Реляционные данные, транзакции |
| Реестр AI-моделей | **PostgreSQL** (таблица `ai_models`) | Справочник моделей |

## Схема потока данных
graph LR
    A[Embedder / Reporter / Ingestor] -->|POST /upload| B[Storage Service :8007]
    B -->|put_object| C[(S3 / MinIO)]
    B -->|INSERT| D[(PostgreSQL — table: files)]
    
    A -->|GET /download/{id}| B
    B -->|get_object| C
    B -->|SELECT| D
    
    B -->|delete_object| C
    B -->|DELETE| D


## Реализация S3 (s3_client.py)

```python
s3_client = boto3.client(
    's3',
    endpoint_url=settings.S3_ENDPOINT,   # S3_ENDPOINT из .env
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
)
Параметры S3 берутся из .env через pydantic-settings:

Переменная	Назначение
S3_ENDPOINT	URL S3-совместимого хранилища
S3_ACCESS_KEY / S3_SECRET_KEY	Ключи доступа
S3_BUCKET_NAME	Имя бакета
S3_REGION	Регион (по умолчанию ru-1)
Ответ на вопрос: S3 или локальный диск?
Файлы хранятся в S3 (объектное хранилище), а не на локальном диске и не внутри PostgreSQL. PostgreSQL хранит только метаданные (пути к файлам, checksum, типы, метки).

S3-совместимое хранилище настраивается через переменные окружения — это может быть MinIO (локально) или Yandex Object Storage (продакшн).

Комментарий «для изоляции в S3 (Этап 8)» — реализовано?
Да, это уже реализовано. Комментарий в embedder.py (строка 225) и routes.py (строка 32) относится к Этапу 8 — мульти-модельной изоляции векторов в S3.

# embedder.py, строка 225
'model_slug': used_model_slug,  # ← для изоляции в S3 (Этап 8)

# routes.py, строки 38-42
if model_slug and file_type == schemas.FileType.VECTORS:
    s3_key = f"{user_id}/{file_type.value}/{model_slug}/{file_key}"
else:
    s3_key = f"{user_id}/{file_type.value}/{file_key}"
Что это значит на практике:

Векторы от разных моделей физически лежат в разных папках S3-бакета:

bucket/
└── {user_id}/
    └── vectors/
        ├── e5-base-local/
        │   └── 2026-10-13.parquet
        ├── gpt-embeddings/
        │   └── 2026-10-13.parquet
        └── claude-embeddings/
            └── 2026-10-13.parquet
- Это позволяет хранить векторы от разных моделей без пересечений и легко фильтровать по `model_slug`.

### Итог

1. **Файлы хранятся в S3** (объектное хранилище), а не на локальном диске и не внутри PostgreSQL.
2. **PostgreSQL** хранит только метаданные (пути к файлам, checksum, типы, метки).
3. **Изоляция векторов по моделям в S3 уже реализована** (Этап 8).
4. S3-совместимое хранилище настраивается через переменные окружения.