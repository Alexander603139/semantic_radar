from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
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