from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, Boolean, Float
from sqlalchemy.sql import func
from .database import Base
import enum

class FileType(enum.Enum):
    VECTORS = "vectors"
    ARTICLES = "articles"
    REPORTS = "reports"

class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(String(50), primary_key=True, index=True)
    sources = Column(JSON, nullable=False, default=list)
    schedule_cron = Column(String(100), nullable=True, default="0 5 * * *")
    
    # НОВЫЕ ПОЛЯ (для мульти-модельности и контекста)
    context = Column(Text, nullable=True)
    threshold = Column(Float, nullable=True, default=0.6)
    active_model_slug = Column(String(100), nullable=True, default="e5-base-local")
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(50), nullable=False, index=True)
    file_type = Column(String(50), nullable=False)
    file_key = Column(String(255), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    storage_path = Column(String(500), nullable=False)
    checksum = Column(String(64), nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

# НОВАЯ ТАБЛИЦА: Реестр AI-моделей
class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(String(36), primary_key=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    provider_type = Column(String(50), nullable=False) # 'local_huggingface' или 'openai_api'
    base_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    model_name = Column(String(255), nullable=False)
    model_path = Column(String(500), nullable=True)
    dimension = Column(Integer, nullable=False)
    requires_prefix = Column(Boolean, default=False) # Нужно ли добавлять 'passage:' / 'query:'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())