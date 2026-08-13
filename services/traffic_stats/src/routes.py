import uuid
import logging
from fastapi import APIRouter, HTTPException, status, Request

from .models import AnalyzeRequest, AnalyzeResponse, OpenPageRankResponse
from .opr_client import OPRClient
from .storage_client import StorageClient
from .exceptions import OPRClientError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_domains(request: AnalyzeRequest, req: Request):
    opr_client: OPRClient = req.app.state.opr_client
    storage_client: StorageClient = req.app.state.storage_client

    task_id = str(uuid.uuid4())
    logger.info(f"Task {task_id} started for {len(request.domains)} domains")

    try:
        opr_response: OpenPageRankResponse = await opr_client.fetch_bulk(request.domains)
    except OPRClientError as e:
        logger.error(f"Task {task_id} failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch data from OpenPageRank: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected error in task {task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    successful = sum(1 for d in opr_response.results if d.is_valid)
    failed = len(opr_response.results) - successful

    raw_dict = opr_response.model_dump()
    parsed_list = [d.model_dump() for d in opr_response.results if d.is_valid]

    try:
        await storage_client.save_task_data(task_id, raw_dict, parsed_list)
    except Exception as e:
        logger.error(f"Failed to save task {task_id} to storage: {e}")
        # В MVP не прерываем ответ клиенту при ошибке сохранения

    return AnalyzeResponse(
        task_id=task_id,
        status="completed",
        as_of=opr_response.as_of,
        total_requested=len(request.domains),
        successful=successful,
        failed=failed,
        results=opr_response.results
    )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Task retrieval from storage is not implemented yet"
    )
