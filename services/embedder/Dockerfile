FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Системные зависимости (как в успешном проекте)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей (torch, sentence-transformers и др.)
COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY services/embedder/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]