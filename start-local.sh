#!/bin/bash

# =============================================================================
# ЛОКАЛЬНЫЙ ЗАПУСК для разработки
# =============================================================================

set -e

echo "🏠 Запуск Coworking Management System в локальном режиме..."

# Получаем абсолютный путь к проекту
PROJECT_DIR=$(pwd)

# Экспортируем переменные окружения для локального режима
export BUILD_TARGET="development"
export ENVIRONMENT="development"  
export DEBUG="true"

# URL конфигурация для localhost
export API_BASE_URL_INTERNAL="http://web:8000"
export API_BASE_URL_EXTERNAL="http://localhost:8000/api"
export FRONTEND_URL="http://localhost"
export CORS_ORIGINS="http://localhost,http://localhost:3000,http://localhost:5173"

# Порты для локального режима
export WEB_PORT="8000"
export FRONTEND_HTTP_PORT="80"
export FRONTEND_HTTPS_PORT="443"

# Пути проекта
export PROJECT_DIR="$PROJECT_DIR"

# SSL отключен для локального режима
export SSL_CERTS_PATH="/dev/null"
export SSL_WEBROOT_PATH="/dev/null"
export DOMAIN_NAME="localhost"

# Настройки для разработки
export LOG_LEVEL="DEBUG"
export LOG_FORMAT="text"
export CACHE_DEFAULT_TTL="300"
export BACKUP_ENABLED="false"

# Ресурсы для разработки (меньше)
export WEB_MEMORY_LIMIT="512M"
export WEB_MEMORY_RESERVATION="256M" 
export REDIS_MAXMEMORY="256mb"
export REDIS_MEMORY_LIMIT="256M"
export REDIS_MEMORY_RESERVATION="128M"

echo "📋 Конфигурация локального режима:"
echo "  BUILD_TARGET: $BUILD_TARGET"
echo "  API_BASE_URL: $API_BASE_URL_EXTERNAL"
echo "  FRONTEND_URL: $FRONTEND_URL"
echo "  PROJECT_DIR: $PROJECT_DIR"
echo "  WEB_PORT: $WEB_PORT"
echo ""

# Создаем необходимые директории
echo "📁 Создание директорий для данных..."
mkdir -p data avatars ticket_photos newsletter_photos logs config

# Запускаем Docker Compose
echo "🚀 Запуск сервисов..."
docker-compose up -d --build

# Ждем запуска сервисов
echo "⏱️ Ожидание запуска сервисов..."
sleep 10

# Проверяем статус
echo "🏥 Проверка статуса сервисов:"
docker-compose ps

echo ""
echo "✅ Локальная среда запущена!"
echo ""
echo "🌐 Доступные URL:"
echo "  📱 Frontend:        http://localhost"
echo "  🔧 API:             http://localhost:8000/api" 
echo "  📚 API Docs:        http://localhost:8000/docs"
echo "  🔍 Redis:           localhost:6379"
echo ""
echo "📋 Полезные команды:"
echo "  docker-compose logs -f          # Просмотр логов"
echo "  docker-compose logs -f web      # Логи API"
echo "  docker-compose logs -f bot      # Логи бота"  
echo "  docker-compose logs -f frontend # Логи фронтенда"
echo "  docker-compose down             # Остановка"
echo ""
echo "🎯 Для продакшена используйте: ./start-prod.sh"