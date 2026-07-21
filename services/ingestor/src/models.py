from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Article(BaseModel):
    source: str
    url: str
    title: str
    body: str
    published_at: Optional[datetime] = None
    scraped_at: datetime = datetime.now()

# Модели для API

class RunRequest(BaseModel):
    user_id: str = "test_user"          # временно, позже из JWT
    sources: List[str]                  # список URL сайтов
    limit: int = 5                      # количество статей на сайт

class RunResponse(BaseModel):
    task_id: str
    status: str                         # "started"
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str                         # "pending", "running", "completed", "failed"
    result: Optional[dict] = None       # результаты или ошибка
    error: Optional[str] = None