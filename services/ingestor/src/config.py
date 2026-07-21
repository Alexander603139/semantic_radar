import os
# Список источников (пока статический, позже будет из user_manager)
SOURCES = [
    "https://lenta.ru",
    "https://ria.ru",
    "https://tass.ru",
]

# Папка для сохранения
OUTPUT_DIR = "data/articles"

# Расширения файлов, которые не являются статьями
SKIP_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.exe', '.pdf', '.zip', '.rar', '.mp4', '.avi', '.mp3', '.json', '.xml')
MIN_TEXT_LENGTH = 100
DEFAULT_TIMEOUT = 30.0

# Планировщик (по умолчанию – каждое воскресенье в 5:00)
SCHEDULE_CRON = "0 5 * * 0"   # cron-строка
# SCHEDULE_CRON = "* * * * *"   # каждую минуту. для тестов

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
    r'/\d{4}/\d{2}/\d{2}/',  # дата в URL
    r'/post/',
    r'/\d+-\d+-\d+/',        # другой вариант даты
]

# Минимальная длина текста для признания статьи валидной
MIN_TEXT_LENGTH = 100