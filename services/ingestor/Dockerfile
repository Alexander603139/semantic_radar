FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

COPY services/ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright

COPY services/ingestor/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]