from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TopicShift(BaseModel):
    old_terms: List[str]
    new_terms: List[str]

class AnalyzeResult(BaseModel):
    drift_score: float
    shifted_topics: List[TopicShift]
    cluster_details: Dict[str, Any]

class ReportRequest(BaseModel):
    user_id: str
    analysis_result: AnalyzeResult

class ReportResponse(BaseModel):
    status: str
    report_url: str   # относительный путь к HTML
    text_summary: Optional[str] = None  # заглушка для LLM