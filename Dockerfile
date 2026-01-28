FROM python:3.11-slim

WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY kaiten_automation.py .
COPY webhook_handler.py .

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Порт для вебхук-сервера
EXPOSE 5000

# По умолчанию запускаем вебхук-сервер
CMD ["python", "webhook_handler.py"]
