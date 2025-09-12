#!/bin/bash

# =============================================================================
# СТАТУС СЕРВИСОВ
# =============================================================================

set -e

echo "🏥 Статус Coworking Management System"
echo "===================================="
echo ""

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

# Определяем команду Docker Compose
if docker compose version > /dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif docker-compose --version > /dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose не найден!"
    exit 1
fi

# Показываем статус всех контейнеров
echo "📊 Статус контейнеров:"
$COMPOSE_CMD ps

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
REDIS_STATUS=$($COMPOSE_CMD exec -T redis redis-cli ping 2>/dev/null || echo "FAIL")
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
echo "  ./scripts/logs.sh [service] [follow]  # Просмотр логов"
echo "  ./scripts/restart.sh                  # Перезапуск"
echo "  ./scripts/stop.sh                     # Остановка"
echo "  $COMPOSE_CMD exec web bash  # Подключиться к API контейнеру"
echo "  $COMPOSE_CMD exec bot bash  # Подключиться к Bot контейнеру"