FROM python:3.11-slim

WORKDIR /app

# Настройка зеркала PyPI (Tsinghua)
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

COPY services/storage/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/storage/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8007"]