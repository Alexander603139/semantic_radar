import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from .settings import settings
from .models import RunRequest, RunResponse, TaskStatusResponse
from .tasks import run_parsing_task, tasks_store
from .scheduler import init_scheduler
from dotenv import load_dotenv
import httpx
from .routes import router
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    user_settings = await load_user_settings("admin")
    app.state.user_settings = user_settings
    sources = user_settings.get("sources", settings.SOURCES)
    cron = user_settings.get("schedule_cron", settings.SCHEDULE_CRON)
    tz = user_settings.get("timezone", settings.DEFAULT_TIMEZONE)
    init_scheduler(cron=cron, sources=sources, timezone=tz)
    logger.info(f"Loaded settings: {user_settings}")
    yield
    logger.info("Ingestor service shutting down")

app = FastAPI(lifespan=lifespan)

@app.post("/run", response_model=RunResponse)
async def run_parser(request: RunRequest, background_tasks: BackgroundTasks):
    """
    Запускает парсинг для переданного списка сайтов.
    Возвращает task_id для отслеживания статуса.
    """
    # Если sources не переданы, берём из настроек
    if request.sources is None or not request.sources:
        request.sources = app.state.user_settings.get("sources", settings.SOURCES)
    # Если limit не передан, используем дефолтный
    if request.limit is None:
        request.limit = 5
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

async def load_user_settings(user_id: str = "admin") -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{settings.STORAGE_URL}/settings/{user_id}")
        if resp.status_code == 200:
            return resp.json()
        return {"sources": settings.SOURCES, "schedule_cron": settings.SCHEDULE_CRON}

# Подключаем роутер с админскими эндпоинтами
app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)