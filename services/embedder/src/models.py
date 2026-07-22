from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Article(BaseModel):
    id: str
    title: str
    text: str
    source: str
    published_at: Optional[datetime] = None

class EmbedRequest(BaseModel):
    user_id: str
    articles: List[Article]

class EmbedResponse(BaseModel):
    status: str
    vectors_file: str
    chunk_count: int