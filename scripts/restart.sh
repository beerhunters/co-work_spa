#!/bin/bash

# =============================================================================
# ПЕРЕЗАПУСК сервисов
# =============================================================================

set -e

echo "🔄 Перезапуск Coworking Management System..."

# Определяем режим работы по переменным окружения
# Получаем директорию скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ "$BUILD_TARGET" = "production" ] || [ "$ENVIRONMENT" = "production" ]; then
    echo "🏭 Перезапуск в продакшн режиме..."
    "$SCRIPT_DIR/stop.sh"
    sleep 3
    "$SCRIPT_DIR/start-prod.sh"
else
    echo "🏠 Перезапуск в локальном режиме..."
    "$SCRIPT_DIR/stop.sh"
    sleep 3
    "$SCRIPT_DIR/start-local.sh"
fi