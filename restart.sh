#!/bin/bash

# =============================================================================
# ПЕРЕЗАПУСК сервисов
# =============================================================================

set -e

echo "🔄 Перезапуск Coworking Management System..."

# Определяем режим работы по переменным окружения
if [ "$BUILD_TARGET" = "production" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo "🏭 Перезапуск в продакшн режиме..."
    ./stop.sh
    sleep 3
    ./start-prod.sh
else
    echo "🏠 Перезапуск в локальном режиме..."
    ./stop.sh
    sleep 3
    ./start-local.sh
fi