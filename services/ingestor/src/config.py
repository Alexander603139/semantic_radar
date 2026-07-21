import os
import datetime
# Список источников (пока статический, позже будет из user_manager)
SOURCES = [
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

# Папка для сохранения
OUTPUT_DIR = "data/articles"

# Расширения файлов, которые не являются статьями
SKIP_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.exe', '.pdf', '.zip', '.rar', '.mp4', '.avi', '.mp3', '.json', '.xml')
MIN_TEXT_LENGTH = 100
DEFAULT_TIMEOUT = 30.0

# Планировщик (по умолчанию – каждое воскресенье в 5:00)
# SCHEDULE_CRON = "0 5 * * 0"   # cron-строка
SCHEDULE_CRON = "* * * * *"   # каждую минуту. для тестов

# URL для вызова embedder (внутри Docker-сети)
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://embedder:8002/embed")
# Режим заглушки для embedder (если True – ничего не вызываем)
EMBEDDER_MOCK = os.getenv("EMBEDDER_MOCK", "True").lower() == "true"

# Порт для FastAPI
PORT = int(os.getenv("INGESTOR_PORT", 8001))

# Паттерны для определения ссылок на статьи (регулярки)
ARTICLE_URL_PATTERNS = [
    r'/news/',
    r'/story/',
    r'/article/',
    r'/post/',
    r'/entry/',
    r'/\d{4}/\d{2}/\d{2}/',  # дата
    r'/\d{6,}/',              # числовой ID (6+ цифр)
]

# Минимальная длина текста для признания статьи валидной
MIN_TEXT_LENGTH = 100