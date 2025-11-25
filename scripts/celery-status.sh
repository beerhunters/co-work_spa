#!/bin/bash
# Скрипт для проверки статуса Celery

echo "📊 Статус Celery Worker:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose ps celery_worker
echo ""

echo "📋 Активные задачи:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose exec celery_worker celery -A celery_app inspect active

echo ""
echo "⏰ Запланированные задачи:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose exec celery_worker celery -A celery_app inspect scheduled

echo ""
echo "📈 Статистика:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose exec celery_worker celery -A celery_app inspect stats

echo ""
echo "📝 Последние логи:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose logs --tail=20 celery_worker

