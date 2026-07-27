FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY services/ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка браузера Chromium (как в успешном проекте)
RUN playwright install chromium

COPY services/ingestor/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]