import logging
import uuid
from fastapi import FastAPI
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from .routes import router
from .settings import settings
from .database import engine, Base
from .models import AIModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    """Автоматически добавляет новые колонки в существующие таблицы (без Alembic)."""
    inspector = inspect(engine)
    if 'user_settings' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('user_settings')]
        with engine.connect() as conn:
            if 'context' not in columns:
                conn.execute(text("ALTER TABLE user_settings ADD COLUMN context TEXT"))
            if 'threshold' not in columns:
                conn.execute(text("ALTER TABLE user_settings ADD COLUMN threshold FLOAT DEFAULT 0.6"))
            if 'active_model_slug' not in columns:
                conn.execute(text("ALTER TABLE user_settings ADD COLUMN active_model_slug VARCHAR(100) DEFAULT 'e5-base-local'"))
            conn.commit()
            logger.info("✅ user_settings table migrated successfully")

def seed_initial_models():
    """Заполняет реестр AI-моделей при первом запуске."""
    with Session(engine) as db:
        if db.query(AIModel).count() == 0:
            initial_models = [
                AIModel(
                    id=str(uuid.uuid4()), slug="e5-base-local", name="E5 Base (Локальная)",
                    provider_type="local_huggingface", model_name="intfloat/multilingual-e5-base",
                    model_path="/app/models/multilingual-e5-base", dimension=768,
                    requires_prefix=True, is_active=True
                ),
                AIModel(
                    id=str(uuid.uuid4()), slug="yandex-doc-v2", name="Yandex Doc V2 (Timeweb API)",
                    provider_type="openai_api", model_name="yandex/text-embeddings-v2-doc",
                    base_url="https://api.timeweb.ai/v1", dimension=256,
                    requires_prefix=False, is_active=True
                ),
                AIModel(
                    id=str(uuid.uuid4()), slug="minilm-local", name="MiniLM (Пре-фильтр)",
                    provider_type="local_huggingface", model_name="all-MiniLM-L6-v2",
                    model_path="/app/models/all-MiniLM-L6-v2", dimension=384,
                    requires_prefix=False, is_active=True
                )
            ]
            db.add_all(initial_models)
            db.commit()
            logger.info("✅ Seeded 3 initial AI models into registry")

# Порядок запуска при старте контейнера:
Base.metadata.create_all(bind=engine) # Создаст новую таблицу ai_models
run_migrations()                      # Добавит колонки в старую user_settings
seed_initial_models()                 # Заполнит реестр моделями

app = FastAPI(title="Storage Service")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)