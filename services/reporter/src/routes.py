from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import logging
from .models import ReportRequest, ReportResponse
from .reporter import generate_report, generate_text_summary
from .settings import settings
import os

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/generate", response_model=ReportResponse)
async def generate_report_endpoint(request: ReportRequest):
    try:
        # Конвертируем Pydantic-модель в dict для обработки
        analysis_data = request.analysis_result.dict()
        file_id = await generate_report(request.user_id, analysis_data)

        # Генерируем текстовое резюме (заглушка или вызов YandexGPT)
        text_summary = generate_text_summary(
            analysis_data.get("shifted_topics", []),
            analysis_data.get("drift_score", 0.0)
        )

        # Возвращаем URL для доступа к отчёту через Nginx (прокси на storage)
        report_url = f"/reports/{file_id}"

        return ReportResponse(
            status="ok",
            report_url=report_url,
            text_summary=text_summary
        )
    except Exception as e:
        logger.error(f"Ошибка генерации отчёта: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{user_id}/{filename}")
async def get_report(user_id: str, filename: str):
    """Отдаёт HTML-файл отчёта."""
    safe_filename = os.path.basename(filename)  # защита от path traversal
    filepath = os.path.join(settings.REPORTS_ROOT, f"user_{user_id}", safe_filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return FileResponse(filepath, media_type="text/html")