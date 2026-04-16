FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Источник копирования
COPY . .

# Команда по умолчанию: запуск полного конвейера
ENTRYPOINT ["python", "pipeline.py"]
CMD ["run"]
