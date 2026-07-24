from fastapi import APIRouter, HTTPException
import logging
from .models import AnalyzeRequest, AnalyzeResponse
from .analyzer import analyze_user

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    try:
        result = analyze_user(request.user_id, request.weeks)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return AnalyzeResponse(
            drift_score=result["drift_score"],
            shifted_topics=result["shifted_topics"],
            cluster_details=result["cluster_details"]
        )
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}")
        raise HTTPException(status_code=500, detail=str(e))