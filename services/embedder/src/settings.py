from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MODEL_NAME: str = "models/all-MiniLM-L6-v2" # Модель эмбеддингов
    # VECTORS_ROOT = os.getenv("VECTORS_ROOT", "/app/data/vectors")
    VECTORS_ROOT: str = "./data/vectors" # Корневая папка для сохранения векторов
    CHUNK_SIZE: int = 256 # Максимальная длина чанка в токенах (для MiniLM ~256 слов)
    CHUNK_OVERLAP: int = 32
    PORT: int = 8002 # Порт сервиса

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()