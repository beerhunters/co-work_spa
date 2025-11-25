#!/bin/bash
# Скрипт для очистки очереди Celery от старых задач

echo "🧹 Очистка очереди Celery..."

# Остановка celery worker
echo "⏸️  Остановка Celery worker..."
docker-compose stop celery_worker

# Очистка всех задач в Redis
echo "🗑️  Очистка задач в Redis..."
docker-compose exec redis redis-cli FLUSHDB

# Или более безопасный вариант - только очистка очереди Celery
# docker-compose exec redis redis-cli DEL celery

echo "✅ Очередь очищена!"

# Перезапуск celery worker
echo "🔄 Перезапуск Celery worker..."
docker-compose up -d celery_worker

echo "✅ Celery worker перезапущен!"
echo ""
echo "📊 Проверка статуса:"
docker-compose ps celery_worker

