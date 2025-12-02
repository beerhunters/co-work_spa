#!/bin/bash

# =============================================================================
# ЛОКАЛЬНЫЙ ЗАПУСК для разработки
# =============================================================================

set -e

echo "🏠 Запуск Coworking Management System в локальном режиме..."

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

# Экспортируем переменные окружения для локального режима
export BUILD_TARGET="development"
export ENVIRONMENT="development"  
export DEBUG="true"

# URL конфигурация для localhost
export API_BASE_URL_INTERNAL="http://web:8000"
export API_BASE_URL_EXTERNAL="http://localhost/api"
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

# Парсинг аргументов командной строки
SKIP_BUILD=false
for arg in "$@"; do
  case $arg in
    --skip-build)
      SKIP_BUILD=true
      shift
      ;;
    --help|-h)
      echo "Использование: $0 [--skip-build] [--help]"
      echo ""
      echo "Опции:"
      echo "  --skip-build    Пропустить сборку образов (использовать существующие)"
      echo "  --help, -h      Показать эту справку"
      exit 0
      ;;
  esac
done

# Умная проверка необходимости пересборки
NEED_BASE_BUILD=false
NEED_SERVICES_BUILD=false

if [ "$SKIP_BUILD" = false ]; then
  echo "🔍 Проверка необходимости пересборки..."

  # Проверяем изменения в requirements.txt
  if [ -f "requirements.txt" ]; then
    # Проверяем, существует ли образ python-deps
    if [ -z "$(docker images -q co-work_spa-python-deps 2>/dev/null)" ]; then
      echo "  ⚠️  Образ python-deps не найден - требуется сборка базы"
      NEED_BASE_BUILD=true
    else
      # Проверяем, изменился ли requirements.txt с момента последней сборки
      LAST_BUILD_TIME=$(docker inspect -f '{{ .Created }}' co-work_spa-python-deps 2>/dev/null || echo "0")
      REQUIREMENTS_TIME=$(stat -f "%m" requirements.txt 2>/dev/null || stat -c "%Y" requirements.txt 2>/dev/null)

      if [ "$REQUIREMENTS_TIME" -gt "$(date -j -f "%Y-%m-%dT%H:%M:%S" "$LAST_BUILD_TIME" +%s 2>/dev/null || echo 0)" ]; then
        echo "  📦 Обнаружены изменения в requirements.txt"
        NEED_BASE_BUILD=true
      fi
    fi
  fi

  # Проверяем изменения в frontend/package.json
  if [ -f "frontend/package.json" ]; then
    if [ -z "$(docker images -q co-work_spa-frontend 2>/dev/null)" ]; then
      echo "  ⚠️  Образ frontend не найден - требуется сборка"
      NEED_SERVICES_BUILD=true
    fi
  fi

  # Проверяем существование образов сервисов
  for service in web bot frontend; do
    if [ -z "$(docker images -q co-work_spa-$service 2>/dev/null)" ]; then
      echo "  ⚠️  Образ $service не найден - требуется сборка"
      NEED_SERVICES_BUILD=true
      break
    fi
  done

  # Выполняем сборку если необходимо
  if [ "$NEED_BASE_BUILD" = true ]; then
    echo ""
    echo "🔨 Сборка базовых образов (base + python-deps)..."
    docker-compose --profile base-build build base python-deps
    NEED_SERVICES_BUILD=true  # Если обновили базу, нужно пересобрать сервисы
  fi

  if [ "$NEED_SERVICES_BUILD" = true ]; then
    echo ""
    echo "🔨 Сборка образов сервисов (web, bot, frontend)..."
    docker-compose build web bot frontend
  else
    echo "  ✅ Образы актуальны, пересборка не требуется"
  fi

  echo ""
else
  echo "⏭️  Пропуск сборки (флаг --skip-build)"
  echo ""
fi

# Создаем необходимые директории
echo "📁 Создание директорий для данных..."
mkdir -p data avatars ticket_photos newsletter_photos logs config

# Запускаем Docker Compose
echo "🚀 Запуск сервисов..."
docker-compose up -d

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
echo "  ./scripts/start-local.sh --skip-build   # Быстрый запуск без пересборки"
echo "  docker-compose logs -f                   # Просмотр логов"
echo "  docker-compose logs -f web               # Логи API"
echo "  docker-compose logs -f bot               # Логи бота"
echo "  docker-compose logs -f frontend          # Логи фронтенда"
echo "  docker-compose down                      # Остановка"
echo ""
echo "🎯 Для продакшена используйте: ./scripts/start-prod.sh"