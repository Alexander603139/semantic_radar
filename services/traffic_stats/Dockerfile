FROM python:3.10-slim

WORKDIR /app

# Зеркало PyPI для ускорения (как в других сервисах)
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Устанавливаем зависимости
COPY services/traffic_stats/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY services/traffic_stats/src ./src

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8008"]