#!/bin/bash

# =============================================================================
# СТАТУС СЕРВИСОВ
# =============================================================================

set -e

echo "🏥 Статус Coworking Management System"
echo "===================================="
echo ""

# Показываем статус всех контейнеров
echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "🔍 Проверка доступности сервисов:"

# Проверяем API
echo -n "  API (http://localhost:8000): "
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>/dev/null || echo "FAIL")
if [ "$API_STATUS" = "200" ]; then
    echo "✅ Доступен (HTTP $API_STATUS)"
else
    echo "❌ Недоступен (HTTP $API_STATUS)"
fi

# Проверяем Frontend
echo -n "  Frontend (http://localhost): "
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "FAIL")
if [ "$FRONTEND_STATUS" = "200" ] || [ "$FRONTEND_STATUS" = "301" ]; then
    echo "✅ Доступен (HTTP $FRONTEND_STATUS)"
else
    echo "❌ Недоступен (HTTP $FRONTEND_STATUS)"
fi

# Проверяем Redis
echo -n "  Redis (localhost:6379): "
REDIS_STATUS=$(docker-compose exec -T redis redis-cli ping 2>/dev/null || echo "FAIL")
if [ "$REDIS_STATUS" = "PONG" ]; then
    echo "✅ Доступен"
else
    echo "❌ Недоступен"
fi

echo ""
echo "💾 Использование дискового пространства:"
echo "Volumes:"
du -sh data/ avatars/ ticket_photos/ newsletter_photos/ logs/ config/ 2>/dev/null || echo "  Директории не созданы"

echo ""
echo "🐳 Docker статистика:"
docker system df

echo ""
echo "📋 Полезные команды:"
echo "  ./logs.sh [service] [follow]  # Просмотр логов"
echo "  ./restart.sh                  # Перезапуск"
echo "  ./stop.sh                     # Остановка"
echo "  docker-compose exec web bash  # Подключиться к API контейнеру"
echo "  docker-compose exec bot bash  # Подключиться к Bot контейнеру"