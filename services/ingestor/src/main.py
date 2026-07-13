import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from .config import PORT
from .models import RunRequest, RunResponse, TaskStatusResponse
from .tasks import run_parsing_task, tasks_store
from .scheduler import init_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт планировщика при запуске приложения
    init_scheduler()
    logger.info("Ingestor service started")
    yield
    # Здесь можно добавить остановку планировщика, если нужно
    logger.info("Ingestor service shutting down")

app = FastAPI(lifespan=lifespan)

@app.post("/run", response_model=RunResponse)
async def run_parser(request: RunRequest, background_tasks: BackgroundTasks):
    """
    Запускает парсинг для переданного списка сайтов.
    Возвращает task_id для отслеживания статуса.
    """
    if not request.sources:
        raise HTTPException(status_code=400, detail="Список источников не может быть пустым")
    # Запускаем задачу в фоне
    task_id = await run_parsing_task(
        user_id=request.user_id,
        sources=request.sources,
        limit=request.limit
    )
    return RunResponse(task_id=task_id, status="started", message="Задача поставлена в очередь")

@app.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str):
    """Возвращает статус задачи"""
    if task_id not in tasks_store:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    info = tasks_store[task_id]
    return TaskStatusResponse(
        task_id=task_id,
        status=info["status"],
        result=info.get("result"),
        error=info.get("error")
    )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)