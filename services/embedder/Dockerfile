FROM python:3.10-slim

WORKDIR /app

# Установка CPU-версии torch без CUDA-зависимостей (уменьшает размер на ~2 ГБ)
RUN pip install --no-cache-dir torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu --no-deps

COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/embedder/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]