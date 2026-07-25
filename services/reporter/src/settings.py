from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    REPORTS_ROOT: str = "./data/reports"
    PLOTLY_TEMPLATE: str = "plotly_white"   # или "seaborn"
    PORT: int = 8005

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()