FROM python:3.10-slim
WORKDIR /app
RUN pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu
COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/embedder/src/ ./src/
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]
