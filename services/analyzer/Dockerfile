FROM python:3.10-slim
WORKDIR /app
COPY services/analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/analyzer/src/ ./src/
ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004"]