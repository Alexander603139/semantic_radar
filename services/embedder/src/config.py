import os

# Модель эмбеддингов
MODEL_NAME = "models/all-MiniLM-L6-v2"

# Корневая папка для сохранения векторов
# VECTORS_ROOT = os.getenv("VECTORS_ROOT", "/app/data/vectors")
VECTORS_ROOT = os.getenv("VECTORS_ROOT", "./data/vectors")

# Максимальная длина чанка в токенах (для MiniLM ~256 слов)
CHUNK_SIZE = 256
CHUNK_OVERLAP = 32

# Порт сервиса
PORT = int(os.getenv("EMBEDDER_PORT", 8002))