FROM python:3.11-slim

WORKDIR /app

# Настройка зеркала PyPI (Tsinghua)
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Установка CPU-версии torch без CUDA-зависимостей (уменьшает размер на ~2 ГБ)
RUN pip install --no-cache-dir torch==2.3.0 --index-url https://download.pytorch.org/whl/cpu --no-deps

COPY services/embedder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/embedder/src/ ./src/

ENV PYTHONPATH=/app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002"]