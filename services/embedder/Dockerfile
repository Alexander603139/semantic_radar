FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# RUN pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu

# Системные зависимости (добавлен libgomp1 для работы PyTorch/Transformers на CPU)

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Установка Python-зависимостей
COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY services/embedder/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
