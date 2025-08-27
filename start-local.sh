#!/bin/bash

echo "🚀 Запуск локальной среды разработки..."

# Проверяем наличие .env.local
if [ ! -f ".env.local" ]; then
    echo "❌ Файл .env.local не найден!"
    echo "Создайте его из примера:"
    echo "cp .env.local.example .env.local"
    echo "nano .env.local"
    exit 1
fi

# Запускаем сервисы
docker-compose -f docker-compose.local.yml --env-file .env.local up -d

echo "⏱️ Ожидание запуска сервисов..."
sleep 10

# Проверяем статус
echo "📊 Статус сервисов:"
docker-compose -f docker-compose.local.yml ps

echo ""
echo "🌐 Локальная среда запущена:"
echo "   Frontend: http://localhost"
echo "   API: http://localhost:8000/api"
echo "   Docs: http://localhost:8000/docs"
echo ""
echo "📋 Полезные команды:"
echo "   ./stop-local.sh       - остановка"
echo "   ./restart-local.sh    - перезапуск"
echo "   ./logs-local.sh       - просмотр логов"