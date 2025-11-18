#!/bin/bash
#
# Скрипт деплоя на Production с автоматической миграцией
# Использование: ./scripts/deploy-with-migration.sh
#

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка что мы в корне проекта
if [ ! -f "docker-compose.yml" ]; then
    error "Запустите скрипт из корня проекта!"
    exit 1
fi

echo ""
echo "============================================================"
echo "  ДЕПЛОЙ НА PRODUCTION С МИГРАЦИЕЙ"
echo "============================================================"
echo ""

# 1. Проверка git статуса
info "Проверка git статуса..."
if [ -n "$(git status --porcelain)" ]; then
    warning "Есть незакоммиченные изменения!"
    git status --short
    read -p "Продолжить? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        error "Деплой отменен"
        exit 1
    fi
fi

# 2. Обновление кода
info "Обновление кода из репозитория..."
git pull origin main || {
    error "Ошибка git pull"
    exit 1
}
success "Код обновлен"

# 3. Остановка сервисов
info "Остановка сервисов..."
docker-compose stop web celery_worker bot || {
    error "Ошибка остановки сервисов"
    exit 1
}
success "Сервисы остановлены"

# 4. Создание бэкапа БД (дополнительный)
info "Создание дополнительного бэкапа БД..."
BACKUP_DIR="./data/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/pre_deploy_${TIMESTAMP}.db"

if [ -f "./data/coworking.db" ]; then
    cp ./data/coworking.db "$BACKUP_FILE"
    success "Бэкап создан: $BACKUP_FILE"
else
    warning "База данных не найдена, бэкап пропущен"
fi

# 5. Миграция БД
info "Запуск миграции базы данных..."
docker-compose run --rm web python migrations/migrate_email_tracking.py --auto-confirm

if [ $? -ne 0 ]; then
    error "❌ Миграция не удалась!"
    warning "Восстановление из бэкапа..."

    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" ./data/coworking.db
        success "БД восстановлена из бэкапа"
    fi

    error "Деплой прерван. Проверьте логи миграции."
    exit 1
fi
success "Миграция завершена успешно"

# 6. Пересборка контейнеров
info "Пересборка контейнеров..."
docker-compose build web celery_worker bot || {
    error "Ошибка сборки контейнеров"
    exit 1
}
success "Контейнеры собраны"

# 7. Обновление зависимостей (опционально)
if [ -f "requirements.txt" ]; then
    info "Проверка зависимостей..."
    docker-compose run --rm web pip list --outdated || true
fi

# 8. Запуск сервисов
info "Запуск сервисов..."
docker-compose up -d || {
    error "Ошибка запуска сервисов"
    exit 1
}
success "Сервисы запущены"

# 9. Ожидание готовности
info "Ожидание готовности сервисов (30 сек)..."
sleep 30

# 10. Проверка статуса
info "Проверка статуса сервисов..."
docker-compose ps

# 11. Проверка логов
info "Проверка логов на ошибки..."
docker-compose logs --tail=20 web | grep -i error || true

# 12. Проверка health endpoint
info "Проверка health endpoint..."
if command -v curl &> /dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        success "API отвечает (HTTP $HTTP_CODE)"
    else
        warning "API не отвечает или недоступен (HTTP $HTTP_CODE)"
    fi
else
    warning "curl не установлен, пропуск проверки health"
fi

# 13. Итоговый отчет
echo ""
echo "============================================================"
success "✅ ДЕПЛОЙ ЗАВЕРШЕН УСПЕШНО!"
echo "============================================================"
echo ""
info "Резюме:"
echo "  - Код обновлен из репозитория"
echo "  - Миграция БД выполнена"
echo "  - Бэкап сохранен: $BACKUP_FILE"
echo "  - Сервисы перезапущены"
echo ""
info "Следующие шаги:"
echo "  1. Проверьте работу приложения"
echo "  2. Отправьте тестовое email письмо"
echo "  3. Проверьте логи: docker-compose logs -f web"
echo "  4. Удалите старые бэкапы при необходимости"
echo ""
info "Откат в случае проблем:"
echo "  docker-compose stop web celery_worker"
echo "  cp $BACKUP_FILE ./data/coworking.db"
echo "  docker-compose up -d"
echo ""
