# Storage — сервис хранения файлов и управления данными

Центральный сервис хранения: принимает файлы от других сервисов (статьи, векторы, отчёты), сохраняет их в **облачное хранилище S3** (Timeweb Cloud), а метаданные — в **PostgreSQL**. Управляет настройками пользователей и реестром AI-моделей. Обеспечивает изоляцию векторов разных моделей в S3 и фильтрацию по модели.

> **Важно:** начиная с фичи «Мульти-модельность», векторы изолируются в S3 по префиксу `model_slug` (Этап 8), а эндпоинты `/list` и `/vectors/count` поддерживают фильтрацию по модели (Этапы 9–10). Это предотвращает смешивание векторов разной размерности.

## Структура проекта

```
services/storage/
├── src/
│   ├── __init__.py
│   ├── settings.py       # конфигурация (S3, PostgreSQL, порт)
│   ├── database.py       # SQLAlchemy engine, сессии, Base
│   ├── models.py         # SQLAlchemy-модели (FileRecord, UserSettings, AIModel)
│   ├── schemas.py        # Pydantic-схемы запроса/ответа
│   ├── crud.py           # CRUD-операции с БД
│   ├── routes.py         # эндпоинты (файлы, настройки, модели)
│   ├── s3_client.py      # клиент S3 (boto3)
│   ├── config.py         # (пустой, зарезервирован)
│   ├── file_manager.py   # (пустой, зарезервирован)
│   ├── main.py           # FastAPI приложение, миграции, сидирование
│   └── migrations/       # (пустая, миграции автоматические в main.py)
├── Dockerfile
├── requirements.txt
└── README.md
```

## Установка и запуск локально

### Требования

- Python 3.11+
- PostgreSQL (локально или в Docker)
- Доступ к S3-совместимому хранилищу (Timeweb Cloud S3) с ключами

### Шаги

1. Клонировать репозиторий.
2. Создать виртуальное окружение и активировать:
   ```bash
   python -m venv venv
   source venv/bin/activate  # или venv\Scripts\activate для Windows
   ```
3. Установить зависимости:
   ```bash
   pip install -r services/storage/requirements.txt
   ```
4. Настроить переменные окружения (см. таблицу ниже) или создать `.env` в корне сервиса.
5. Запустить сервис:
   ```bash
   python -m services.storage.src.main
   ```

По умолчанию сервер запускается на порту **8007**.

## Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `S3_ENDPOINT` | URL S3-эндпоинта (Timeweb Cloud) | (обязательно) |
| `S3_ACCESS_KEY` | Access Key для S3 | (обязательно) |
| `S3_SECRET_KEY` | Secret Key для S3 | (обязательно) |
| `S3_BUCKET_NAME` | Имя бакета в S3 | (обязательно) |
| `S3_REGION` | Регион S3 | `ru-1` |
| `POSTGRES_DSN` | Строка подключения к PostgreSQL | (обязательно) |
| `STORAGE_PORT` | Порт для FastAPI | `8007` |

## Таблицы в БД

### `files` (FileRecord)
Хранит метаданные всех файлов. Сами файлы лежат в S3 по пути `storage_path`.

| Поле | Тип | Описание |
|---|---|---|
| `id` | String(36) | UUID, первичный ключ |
| `user_id` | String(50) | Идентификатор пользователя |
| `file_type` | String(50) | Тип файла: `vectors`, `articles`, `reports` |
| `file_key` | String(255) | Имя файла |
| `version` | Integer | Версия (по умолчанию 1) |
| `storage_path` | String(500) | Путь к файлу в S3 |
| `checksum` | String(64) | MD5-чексумма файла |
| `extra_metadata` | JSON | Произвольные метаданные (для векторов: `chunk_count`, `source_count`, `model_slug`, `model_name`) |
| `deleted_at` | DateTime | Мягкое удаление (если не `NULL` — файл считается удалённым) |

### `user_settings` (UserSettings)
Настройки пользователя: источники парсинга, расписание, активная модель, контекст.

| Поле | Тип | Описание |
|---|---|---|
| `user_id` | String(50) | Первичный ключ |
| `sources` | JSON | Список сайтов для парсинга |
| `schedule_cron` | String(100) | Cron-строка расписания |
| `context` | Text | Контекст парсинга (для будущего семантического фильтра) |
| `threshold` | Float | Порог сходства (по умолчанию 0.6) |
| `active_model_slug` | String(100) | Активная модель эмбеддингов |
| `last_fallback_event` | JSON | Последнее событие fallback |

### `ai_models` (AIModel)
Реестр доступных моделей эмбеддингов.

| Поле | Тип | Описание |
|---|---|---|
| `id` | String(36) | UUID, первичный ключ |
| `slug` | String(100) | Уникальный идентификатор модели |
| `name` | String(255) | Отображаемое имя |
| `provider_type` | String(50) | `local_huggingface` или `openai_api` |
| `base_url` | String(500) | URL API (для облачных моделей) |
| `api_key` | String(500) | API-ключ (для облачных моделей) |
| `model_name` | String(255) | Имя модели |
| `model_path` | String(500) | Путь к весам (для локальных моделей) |
| `dimension` | Integer | Размерность вектора |
| `requires_prefix` | Boolean | Нужны ли префиксы `passage:`/`query:` |
| `is_active` | Boolean | Активна ли модель |

## API

### Файлы

#### POST /upload
Загружает файл в S3 и создаёт запись в БД.

**Параметры (form-data):**
- `user_id` (обязательно)
- `file_type` (обязательно): `vectors`, `articles`, `reports`
- `file_key` (обязательно): имя файла
- `file` (обязательно): сам файл
- `metadata` (опционально): JSON-строка с метаданными
- `model_slug` (опционально): для изоляции векторов в S3 (Этап 8)

**Ответ:** объект `FileResponse` с `id`, `storage_path`, метаданными.

> **Изоляция векторов:** если передан `model_slug` и `file_type=vectors`, файл сохраняется в S3 по пути `{user_id}/vectors/{model_slug}/{file_key}`. Это обеспечивает физическое разделение векторов разных моделей.

#### GET /download/{file_id}
Скачивает файл из S3 по его `id`.

#### GET /list
Возвращает список файлов пользователя.

**Параметры (query):**
- `user_id` (обязательно)
- `file_type` (опционально): фильтр по типу
- `model_slug` (опционально): фильтр по модели в `extra_metadata` (Этап 10)
- `limit` (по умолчанию 100)

#### DELETE /delete_all
Удаляет все файлы указанного типа для пользователя (мягкое удаление + удаление из S3).

**Параметры (query):**
- `user_id` (обязательно)
- `file_type` (обязательно)

**Ответ:** `{"status": "ok", "deleted_count": N}`

#### DELETE /{file_id}
Удаляет один файл по `id` (мягкое удаление + удаление из S3).

**Ответ:** `{"status": "deleted"}`

### Настройки

#### GET /settings/{user_id}
Возвращает настройки пользователя. Если настроек нет — создаёт запись со значениями по умолчанию.

**Ответ:**
```json
{
  "user_id": "admin",
  "sources": ["https://lenta.ru"],
  "schedule_cron": "0 5 * * *",
  "context": null,
  "threshold": 0.6,
  "active_model_slug": "e5-base-local",
  "last_fallback_event": null
}
```

#### POST /settings/{user_id}
Обновляет настройки пользователя. Обновляются только переданные поля.

**Запрос:** объект `UserSettingsUpdate` (все поля опциональны):
```json
{
  "sources": ["https://lenta.ru"],
  "schedule_cron": "0 5 * * *",
  "context": "искусственный интеллект в медицине",
  "threshold": 0.65,
  "active_model_slug": "yandex-doc-v2",
  "last_fallback_event": {"timestamp": "...", "from_model": "...", "to_model": "..."}
}
```

### Реестр моделей

#### GET /ai-models
Возвращает список моделей.

**Параметры (query):**
- `is_active` (опционально): фильтр по активности

#### POST /ai-models
Добавляет новую модель в реестр.

**Запрос:** объект `AIModelCreate`:
```json
{
  "slug": "my-model",
  "name": "My Model",
  "provider_type": "local_huggingface",
  "model_name": "some-model",
  "dimension": 384,
  "model_path": "/app/models/some-model",
  "requires_prefix": false,
  "is_active": true
}
```

#### GET /vectors/count
Возвращает количество неудалённых векторов пользователя (опционально — по модели).

**Параметры (query):**
- `user_id` (обязательно)
- `model_slug` (опционально): фильтр по модели

**Ответ:**
```json
{
  "user_id": "admin",
  "model_slug": null,
  "count": 5
}
```

### Служебные

#### GET /health
Проверка работоспособности сервиса.

**Ответ:** `{"status": "ok"}`

## Автоматические миграции и сидирование

При старте контейнера выполняется следующая последовательность:

1. **`Base.metadata.create_all(bind=engine)`** — создаёт таблицы, которых ещё нет (включая `ai_models`).
2. **`run_migrations()`** — добавляет новые колонки в существующую таблицу `user_settings` без Alembic:
   - `context` (TEXT)
   - `threshold` (FLOAT, по умолчанию 0.6)
   - `active_model_slug` (VARCHAR(100), по умолчанию `e5-base-local`)
   - `last_fallback_event` (JSONB)
3. **`seed_initial_models()`** — заполняет реестр `ai_models` тремя стартовыми моделями, если таблица пустая:
   - `e5-base-local` (локальная, `intfloat/multilingual-e5-base`, 768-мерная, с префиксами)
   - `yandex-doc-v2` (API, `yandex/text-embeddings-v2-doc`, 256-мерная)
   - `minilm-local` (локальная, `all-MiniLM-L6-v2`, 384-мерная)

> **Примечание:** папка `migrations/` пустая — миграции выполняются автоматически при старте, без Alembic.

## Особенности реализации

- **Мягкое удаление** — файлы не удаляются из БД физически, а помечаются `deleted_at`. Все запросы (`get_files`, `get_file_record`, `count_vectors`) фильтруют по `deleted_at IS NULL`.
- **Изоляция векторов по модели** — при загрузке векторов с `model_slug` файл сохраняется в отдельную папку S3 (`{user_id}/vectors/{model_slug}/...`), а `model_slug` гарантированно добавляется в `extra_metadata`.
- **Фильтрация по модели** — эндпоинты `/list` и `/vectors/count` поддерживают опциональный параметр `model_slug` для фильтрации по модели в `extra_metadata`.
- **S3 через boto3** — интеграция с Timeweb Cloud S3 через стандартный клиент `boto3` с кастомным `endpoint_url`.

## Интеграция с другими сервисами

- **`ingestor`** — сохраняет статьи (`file_type=articles`) через `POST /upload`.
- **`embedder`** — сохраняет векторы (`file_type=vectors`) через `POST /upload`, читает реестр моделей через `GET /ai-models` и настройки пользователя через `GET /settings/{user_id}`.
- **`analyzer`** — получает список векторов через `GET /list?model_slug=...` (с фильтрацией по активной модели) и скачивает файлы через `GET /download/{file_id}`.
- **`reporter`** — сохраняет отчёты (`file_type=reports`) через `POST /upload`.
- **Админ-панель** — отображает статьи, векторы, отчёты через `GET /list`, управляет моделями и настройками.

## Беклог (дальнейшие улучшения)

### Архитектура

- Перейти на Alembic для управления миграциями вместо автоматических `ALTER TABLE`.
- Добавить версионирование файлов (поле `version` уже есть, но логика версионирования не реализована).
- Реализовать физическое удаление файлов из S3 при удалении из БД (сейчас при мягком удалении файл остаётся в S3).

### Безопасность

- Добавить JWT-авторизацию (проверка токена через `user_manager`).
- Шифрование `api_key` в таблице `ai_models` (сейчас хранится в открытом виде).

### Производительность

- Добавить пагинацию в эндпоинт `/list` (сейчас ограничен `limit`).
- Индексация `extra_metadata` для ускорения фильтрации по `model_slug` на больших объёмах.

### Функциональность

- Поддержка дополнительных типов файлов (расширение `FileType`).
- API для переименования и перемещения файлов.

## Используемые технологии

- **FastAPI** — веб-фреймворк
- **SQLAlchemy** — ORM для PostgreSQL
- **psycopg2-binary** — драйвер PostgreSQL
- **boto3** — клиент для S3 (Timeweb Cloud)
- **Pydantic / pydantic-settings** — валидация данных и конфигурация
- **python-multipart** — обработка form-data для загрузки файлов

## Лицензия

Проект разрабатывается как коммерческий продукт. Все права защищены.