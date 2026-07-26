FROM python:3.11-slim

WORKDIR /app

# Установка CPU-версии PyTorch (легкая, без CUDA)
RUN pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu

COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/embedder/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]