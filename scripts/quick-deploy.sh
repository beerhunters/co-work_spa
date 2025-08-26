#!/bin/bash

# 🚀 СКРИПТ БЫСТРОГО РАЗВЕРТЫВАНИЯ
# Для использования на уже настроенном сервере

set -e

echo "🚀 Быстрое развертывание Coworking Management System..."

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка наличия .env
if [ ! -f ".env" ]; then
    print_error "Файл .env не найден!"
    print_status "Создайте его командой: cp .env.production .env"
    print_status "И отредактируйте необходимые параметры"
    exit 1
fi

# Проверка ключевых параметров
if grep -q "your-telegram-bot-token-from-botfather" .env; then
    print_error "BOT_TOKEN не настроен в .env файле!"
    exit 1
fi

if grep -q "your-super-secure-password-here" .env; then
    print_warning "Рекомендуется изменить ADMIN_PASSWORD в .env файле!"
fi

# Получение IP из .env для отображения
CURRENT_IP=$(grep "API_BASE_URL" .env | cut -d'=' -f2 | sed 's|http://||' | sed 's|:8000||' | head -n1)

print_status "Остановка существующих контейнеров..."
docker-compose -f docker-compose.production.yml down 2>/dev/null || true

print_status "Создание необходимых директорий..."
mkdir -p data avatars ticket_photos newsletter_photos logs config
chmod -R 755 data avatars ticket_photos newsletter_photos logs config

print_status "Сборка образов..."
docker-compose -f docker-compose.production.yml build --no-cache

print_status "Запуск сервисов..."
docker-compose -f docker-compose.production.yml up -d

print_status "Ожидание запуска сервисов..."
sleep 15

print_status "Проверка статуса сервисов..."
docker-compose -f docker-compose.production.yml ps

# Проверка работоспособности
print_status "Проверка работоспособности..."
sleep 5

API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ || echo "000")

if [ "$API_STATUS" = "200" ]; then
    print_status "✅ API работает (код: $API_STATUS)"
else
    print_error "❌ API недоступен (код: $API_STATUS)"
fi

if [ "$FRONTEND_STATUS" = "200" ]; then
    print_status "✅ Frontend работает (код: $FRONTEND_STATUS)"
else
    print_error "❌ Frontend недоступен (код: $FRONTEND_STATUS)"
fi

# Отображение логов при ошибках
if [ "$API_STATUS" != "200" ] || [ "$FRONTEND_STATUS" != "200" ]; then
    print_warning "Показываем последние логи для диагностики:"
    docker-compose -f docker-compose.production.yml logs --tail=20
fi

echo ""
print_status "🎉 Развертывание завершено!"
echo ""
echo "🌐 Система доступна по адресам:"
if [ -n "$CURRENT_IP" ]; then
    echo "   Frontend: http://$CURRENT_IP"
    echo "   API: http://$CURRENT_IP:8000"
    echo "   API Docs: http://$CURRENT_IP:8000/docs"
else
    echo "   Frontend: http://localhost"
    echo "   API: http://localhost:8000"
    echo "   API Docs: http://localhost:8000/docs"
fi
echo ""
echo "👤 Данные для входа:"
ADMIN_LOGIN=$(grep "ADMIN_LOGIN" .env | cut -d'=' -f2)
echo "   Логин: ${ADMIN_LOGIN:-admin}"
echo "   Пароль: (как указан в ADMIN_PASSWORD в .env)"
echo ""
echo "📊 Полезные команды:"
echo "   ./check-status.sh     - проверка статуса"
echo "   ./backup-system.sh    - создание бэкапа"
echo "   docker-compose -f docker-compose.production.yml logs -f"
echo ""
print_status "✨ Система готова к использованию!"