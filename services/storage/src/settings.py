from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # S3 параметры – все из переменных окружения
    S3_ENDPOINT: str = Field(..., env="S3_ENDPOINT")
    S3_ACCESS_KEY: str = Field(..., env="S3_ACCESS_KEY")
    S3_SECRET_KEY: str = Field(..., env="S3_SECRET_KEY")
    S3_BUCKET_NAME: str = Field(..., env="S3_BUCKET_NAME")
    S3_REGION: str = Field("ru-1", env="S3_REGION")   # опционально

    # PostgreSQL
    POSTGRES_DSN: str = Field(..., env="POSTGRES_DSN")

    # Порт сервиса
    PORT: int = Field(8007, env="STORAGE_PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()