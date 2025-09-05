#!/bin/bash

# =============================================================================
# ПРОДАКШН ЗАПУСК с SSL и оптимизацией
# =============================================================================

set -e

echo "🌐 Запуск Coworking Management System в продакшн режиме..."

# Проверяем, что не запущено от root
if [[ $EUID -eq 0 ]]; then
   echo "❌ Не запускайте этот скрипт от имени root!"
   echo "Используйте обычного пользователя с правами docker"
   exit 1
fi

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

# Проверяем наличие .env файла
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    echo "Создайте и настройте .env файл с вашими конфигурациями"
    exit 1
fi

# Читаем DOMAIN_NAME из .env
DOMAIN_NAME=$(grep "^DOMAIN_NAME=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
if [ -z "$DOMAIN_NAME" ]; then
    echo "❌ DOMAIN_NAME не установлен в .env файле!"
    echo "Добавьте строку: DOMAIN_NAME=your-domain.com"
    exit 1
fi

# Экспортируем переменные окружения для продакшена
export BUILD_TARGET="production"
export ENVIRONMENT="production"
export DEBUG="false"

# URL конфигурация для продакшена
export API_BASE_URL_INTERNAL="http://web:8000"
export API_BASE_URL_EXTERNAL="https://$DOMAIN_NAME/api"
export FRONTEND_URL="https://$DOMAIN_NAME"
export CORS_ORIGINS="https://$DOMAIN_NAME"

# Порты для продакшена
export WEB_PORT="8000"
export FRONTEND_HTTP_PORT="80"
export FRONTEND_HTTPS_PORT="443"

# Пути проекта и SSL
export PROJECT_DIR="$PROJECT_DIR"
export SSL_CERTS_PATH="/etc/letsencrypt"
export SSL_WEBROOT_PATH="/var/www/certbot"
export DOMAIN_NAME="$DOMAIN_NAME"

# Настройки для продакшена
export LOG_LEVEL="INFO"
export LOG_FORMAT="json"
export CACHE_DEFAULT_TTL="600"
export BACKUP_ENABLED="true"

# Ресурсы для продакшена (больше)
export WEB_MEMORY_LIMIT="1G"
export WEB_MEMORY_RESERVATION="512M"
export REDIS_MAXMEMORY="512mb"
export REDIS_MEMORY_LIMIT="512M"
export REDIS_MEMORY_RESERVATION="256M"

echo "📋 Конфигурация продакшн режима:"
echo "  BUILD_TARGET: $BUILD_TARGET"
echo "  DOMAIN_NAME: $DOMAIN_NAME"
echo "  API_BASE_URL: $API_BASE_URL_EXTERNAL"
echo "  FRONTEND_URL: $FRONTEND_URL"
echo "  PROJECT_DIR: $PROJECT_DIR"
echo "  SSL_CERTS: $SSL_CERTS_PATH"
echo ""

# Создаем необходимые директории
echo "📁 Создание директорий для данных..."
mkdir -p data avatars ticket_photos newsletter_photos logs config
chmod -R 755 data avatars ticket_photos newsletter_photos logs config

# Проверяем наличие SSL сертификатов
if [ ! -d "$SSL_CERTS_PATH/live/$DOMAIN_NAME" ]; then
    echo "⚠️ SSL сертификаты не найдены для домена $DOMAIN_NAME"
    echo "Запустите сначала: ./setup-ssl.sh"
    echo "Или запускайте без SSL, пока не настроите сертификаты"
    
    read -p "Продолжить без SSL? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Настройте SSL сертификаты и повторите запуск"
        exit 1
    fi
    
    echo "⚠️ Запуск БЕЗ SSL сертификатов"
    export SSL_CERTS_PATH="/dev/null"
    export SSL_WEBROOT_PATH="/dev/null"
fi

# Запускаем Docker Compose с профилем production (включает certbot)
echo "🚀 Запуск продакшн сервисов..."
docker-compose --profile production up -d --build

# Ждем запуска сервисов
echo "⏱️ Ожидание запуска сервисов..."
sleep 15

# Проверяем статус
echo "🏥 Проверка статуса сервисов:"
docker-compose ps

echo ""
echo "🔍 Проверка доступности:"

# Проверяем API
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "FAIL")
if [ "$API_STATUS" = "200" ]; then
    echo "  ✅ API доступен (HTTP 200)"
else
    echo "  ❌ API недоступен (HTTP $API_STATUS)"
fi

# Проверяем Frontend HTTP
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ || echo "FAIL")
if [ "$FRONTEND_STATUS" = "301" ] || [ "$FRONTEND_STATUS" = "200" ]; then
    echo "  ✅ Frontend HTTP доступен (HTTP $FRONTEND_STATUS)"
else
    echo "  ❌ Frontend HTTP недоступен (HTTP $FRONTEND_STATUS)"
fi

# Проверяем HTTPS если есть SSL
if [ -d "$SSL_CERTS_PATH/live/$DOMAIN_NAME" ] && [ "$SSL_CERTS_PATH" != "/dev/null" ]; then
    HTTPS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN_NAME/ || echo "FAIL")
    if [ "$HTTPS_STATUS" = "200" ]; then
        echo "  ✅ HTTPS доступен (HTTP $HTTPS_STATUS)"
    else
        echo "  ❌ HTTPS недоступен (HTTP $HTTPS_STATUS)"
    fi
fi

echo ""
echo "✅ Продакшн среда запущена!"
echo ""
echo "🌐 Доступные URL:"
if [ -d "$SSL_CERTS_PATH/live/$DOMAIN_NAME" ] && [ "$SSL_CERTS_PATH" != "/dev/null" ]; then
    echo "  🔒 Frontend:        https://$DOMAIN_NAME"
    echo "  🔒 API:             https://$DOMAIN_NAME/api"
    echo "  🔒 API Docs:        https://$DOMAIN_NAME/docs"
else
    echo "  📱 Frontend:        http://$DOMAIN_NAME (или http://YOUR_SERVER_IP)"
    echo "  🔧 API:             http://$DOMAIN_NAME:8000/api"
    echo "  📚 API Docs:        http://$DOMAIN_NAME:8000/docs"
fi
echo ""
echo "📋 Полезные команды:"
echo "  docker-compose logs -f                    # Просмотр логов"
echo "  docker-compose --profile production ps    # Статус сервисов"
echo "  docker-compose --profile production down  # Остановка"
echo "  ./setup-ssl.sh                            # Настройка SSL"
echo ""
echo "🏠 Для локальной разработки используйте: ./start-local.sh"

# Показываем информацию о SSL сертификате
if [ -d "$SSL_CERTS_PATH/live/$DOMAIN_NAME" ] && [ "$SSL_CERTS_PATH" != "/dev/null" ]; then
    echo ""
    echo "🔒 Информация о SSL сертификате:"
    CERT_EXPIRY=$(openssl x509 -enddate -noout -in "$SSL_CERTS_PATH/live/$DOMAIN_NAME/cert.pem" 2>/dev/null | cut -d'=' -f2 || echo "Не удается получить информацию")
    echo "   Срок действия: $CERT_EXPIRY"
fi