FROM python:3.10-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY src ./src

# Переменные окружения и порт
ENV PYTHONPATH=/app
EXPOSE 8000

# Запуск
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]