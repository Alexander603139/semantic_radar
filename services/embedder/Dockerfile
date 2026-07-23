FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]