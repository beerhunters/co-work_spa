#!/bin/bash

# =============================================================================
# ПРОСМОТР ЛОГОВ
# =============================================================================

set -e

SERVICE=${1:-all}
FOLLOW=${2:-false}

echo "📋 Просмотр логов для: $SERVICE"

# Функция для показа доступных сервисов
show_help() {
    echo ""
    echo "📖 Использование: ./logs.sh [service] [follow]"
    echo ""
    echo "Доступные сервисы:"
    echo "  all        - все сервисы (по умолчанию)"
    echo "  web        - API сервер"
    echo "  bot        - Telegram бот"
    echo "  frontend   - Frontend"
    echo "  redis      - Redis кэш"
    echo "  certbot    - SSL сертификаты (только для продакшена)"
    echo ""
    echo "Параметры:"
    echo "  follow     - следить за логами в реальном времени"
    echo ""
    echo "Примеры:"
    echo "  ./logs.sh web          # Показать логи API"
    echo "  ./logs.sh bot follow   # Следить за логами бота"
    echo "  ./logs.sh all follow   # Следить за всеми логами"
}

# Проверяем параметры
case $SERVICE in
    help|--help|-h)
        show_help
        exit 0
        ;;
    all|web|bot|frontend|redis|certbot)
        # Валидные сервисы
        ;;
    *)
        echo "❌ Неизвестный сервис: $SERVICE"
        show_help
        exit 1
        ;;
esac

# Формируем команду
if [ "$SERVICE" = "all" ]; then
    CMD="docker-compose logs"
else
    CMD="docker-compose logs $SERVICE"
fi

# Добавляем флаг follow если нужно
if [ "$FOLLOW" = "follow" ] || [ "$FOLLOW" = "-f" ]; then
    CMD="$CMD -f"
fi

echo "🔍 Выполняется: $CMD"
echo "   (Для выхода нажмите Ctrl+C)"
echo ""

# Выполняем команду
eval $CMD