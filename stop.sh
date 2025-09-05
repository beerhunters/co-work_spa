#!/bin/bash

# =============================================================================
# ОСТАНОВКА всех сервисов
# =============================================================================

set -e

echo "🛑 Остановка Coworking Management System..."

# Получаем абсолютный путь к проекту
PROJECT_DIR=$(pwd)

# Определяем режим работы по переменным окружения
if [ "$BUILD_TARGET" = "production" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo "🏭 Остановка продакшн сервисов (включая certbot)..."
    docker-compose --profile production down
else
    echo "🏠 Остановка локальных сервисов..."
    docker-compose down
fi

echo "✅ Все сервисы остановлены!"
echo ""
echo "📋 Для полной очистки (включая volumes):"
echo "  docker-compose --profile production down -v"
echo "  docker-compose down -v"
echo ""
echo "🔄 Для повторного запуска используйте:"
echo "  ./start-local.sh   # Локальный режим"
echo "  ./start-prod.sh    # Продакшн режим"