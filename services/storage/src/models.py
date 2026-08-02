from sqlalchemy import Column, String, DateTime, Integer, Text, JSON, Enum
from sqlalchemy.sql import func
from .database import Base
import enum

class FileType(enum.Enum):
    VECTORS = "vectors"
    ARTICLES = "articles"
    REPORTS = "reports"

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(String(50), nullable=False, index=True)
    file_type = Column(Enum(FileType), nullable=False)
    file_key = Column(String(255), nullable=False)  # уникальный идентификатор файла в рамках пользователя
    version = Column(Integer, nullable=False, default=1)
    storage_path = Column(String(500), nullable=False)  # путь в S3
    checksum = Column(String(64), nullable=True)
    metadata = Column(JSON, nullable=True)  # произвольные метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)