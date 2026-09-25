from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # URL сервиса embedder для векторизации
    EMBEDDER_URL: str = Field("http://embedder:8002", env="EMBEDDER_URL")
    
    # URL сервиса storage (для чтения настроек пользователя)
    STORAGE_URL: str = Field("http://storage:8007", env="STORAGE_URL")
    
    # Порт сервиса
    PORT: int = Field(8010, env="CONTEXT_FILTER_PORT")
    
    # Порог сходства по умолчанию
    DEFAULT_THRESHOLD: float = Field(0.6, env="DEFAULT_THRESHOLD")
    
    # Размер батча для векторизации
    BATCH_SIZE: int = Field(32, env="BATCH_SIZE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()