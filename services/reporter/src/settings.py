import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REPORTS_ROOT: str = "./data/reports"   # пока оставим для локального резерва
    PLOTLY_TEMPLATE: str = "plotly_white"
    PORT: int = 8005
    STORAGE_URL: str = os.getenv("STORAGE_URL", "http://storage:8007")  # <-- добавьте

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()