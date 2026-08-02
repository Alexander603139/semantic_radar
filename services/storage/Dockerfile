FROM python:3.11-slim

WORKDIR /app

COPY services/storage/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/storage/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]