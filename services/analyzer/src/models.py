from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class AnalyzeRequest(BaseModel):
    user_id: str
    weeks: int = 2  # сколько недель сравнивать (текущая и предыдущая)

class TopicShift(BaseModel):
    old_terms: List[str]
    new_terms: List[str]

class AnalyzeResponse(BaseModel):
    drift_score: float                 # 0..1, насколько сильно изменилось распределение
    shifted_topics: List[TopicShift]   # список сместившихся тем с терминами
    cluster_details: Dict[str, Any]    # дополнительная информация (количество кластеров и т.п.)