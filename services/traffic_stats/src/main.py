import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .config import settings
from .routes import router
from .opr_client import OPRClient
from .storage_client import StorageClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: инициализируем клиенты и кладем в state приложения
    app.state.opr_client = OPRClient()
    app.state.storage_client = StorageClient(settings)
    yield
    # Shutdown: здесь можно корректно закрыть соединения, если нужно

app = FastAPI(
    title="Traffic Stats Service",
    description="Microservice for fetching domain statistics from OpenPageRank",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)