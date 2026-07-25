FROM python:3.11-slim

WORKDIR /app

# Установка Playwright и браузера
RUN pip install playwright && playwright install chromium

COPY services/ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ingestor/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]