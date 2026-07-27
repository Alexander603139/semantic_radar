FROM python:3.11-slim

WORKDIR /app

COPY services/reporter/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/reporter/src/ ./src/

ENV PYTHONPATH=/app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8005"]