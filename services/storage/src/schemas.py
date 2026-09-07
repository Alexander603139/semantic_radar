from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class FileType(str, Enum):
    VECTORS = "vectors"
    ARTICLES = "articles"
    REPORTS = "reports"

class FileCreate(BaseModel):
    user_id: str
    file_type: FileType
    file_key: str
    extra_metadata: Optional[Dict[str, Any]] = None

class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    file_type: FileType
    file_key: str
    version: int
    storage_path: str
    checksum: Optional[str]
    extra_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

# --- Схемы для Реестра Моделей ---
class AIModelCreate(BaseModel):
    slug: str
    name: str
    provider_type: str
    model_name: str
    dimension: int
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_path: Optional[str] = None
    requires_prefix: bool = False
    is_active: bool = True

class AIModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    provider_type: str
    base_url: Optional[str]
    api_key: Optional[str]
    model_name: str
    model_path: Optional[str]
    dimension: int
    requires_prefix: bool
    is_active: bool

# --- Схемы для Настроек ---
class UserSettingsUpdate(BaseModel):
    sources: Optional[List[str]] = None
    schedule_cron: Optional[str] = None
    context: Optional[str] = None
    threshold: Optional[float] = None
    active_model_slug: Optional[str] = None

class UserSettingsResponse(BaseModel):
    user_id: str
    sources: Optional[List[str]] = None
    schedule_cron: Optional[str] = None
    context: Optional[str] = None
    threshold: Optional[float] = None
    active_model_slug: Optional[str] = None