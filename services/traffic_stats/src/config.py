from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # OpenPageRank
    OPR_API_KEY: str
    OPR_BASE_URL: str = "https://openpagerank.keywordseverywhere.com/v1/domains/bulk"
    OPR_TIMEOUT: int = 30  # секунд

    # Внутренний сервис storage (адрес в docker-сети)
    STORAGE_SERVICE_URL: str = "http://storage:8000"

settings = Settings()