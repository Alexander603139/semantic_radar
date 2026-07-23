from pydantic_settings import BaseSettings
from typing import List, Tuple

class Settings(BaseSettings):
    # Основные настройки
    SOURCES: List[str] = [
        "https://nn.rbc.ru/",
        "https://www.mk.ru/",
        "https://news.mail.ru/",
        "https://www.gazeta.ru/", 
        "https://tass.ru/",
        "https://lenta.ru/",
        "https://ria.ru/",
        "https://www.vesti.ru/",
        "https://iz.ru/",
        "https://www.interfax.ru/",
        "https://ura.news/",
        "https://www.vedomosti.ru/",
        "https://www.forbes.ru/",
        "https://asafov.ru/",
        "https://colonelcassad.livejournal.com/",
        "https://www.mn.ru/",
        "https://www.nnov.kp.ru/",
    ]

    OUTPUT_DIR: str = "data/articles"
    SKIP_EXTENSIONS: Tuple[str, ...] = (
        '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',
        '.exe', '.pdf', '.zip', '.rar', '.mp4', '.avi',
        '.mp3', '.json', '.xml'
    )
    MIN_TEXT_LENGTH: int = 100
    DEFAULT_TIMEOUT: float = 30.0

    # Планировщик (по умолчанию – каждое воскресенье в 5:00)
    # Для тестов можно изменить на "* * * * *"
    # SCHEDULE_CRON: str = "0 5 * * 0"
    SCHEDULE_CRON: str = "* * * * *"

    # Настройки интеграции с embedder
    EMBEDDER_URL: str = "http://localhost:8002/embed"
    EMBEDDER_MOCK: bool = False

    # Порт для FastAPI
    PORT: int = 8001

    # Паттерны для определения ссылок на статьи (регулярки)
    ARTICLE_URL_PATTERNS: List[str] = [
        r'/news/',
        r'/story/',
        r'/article/',
        r'/post/',
        r'/entry/',
        r'/\d{4}/\d{2}/\d{2}/',   # дата в URL
        r'/\d{6,}/',              # числовой ID (6+ цифр)
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()