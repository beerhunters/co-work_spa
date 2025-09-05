#!/bin/bash

# =============================================================================
# ОЧИСТКА системы от старых данных и контейнеров
# =============================================================================

set -e

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

echo "🧹 Очистка Coworking Management System"
echo "====================================="

# Функция подтверждения
confirm() {
    read -p "$1 (y/N): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Остановка всех сервисов
if confirm "🛑 Остановить все сервисы?"; then
    echo "Остановка сервисов..."
    docker-compose --profile production down 2>/dev/null || true
    docker-compose down 2>/dev/null || true
fi

# Удаление volumes
if confirm "💾 Удалить все volumes (ВНИМАНИЕ: это удалит все данные!)?"; then
    echo "Удаление volumes..."
    docker-compose --profile production down -v 2>/dev/null || true
    docker-compose down -v 2>/dev/null || true
fi

# Очистка неиспользуемых Docker образов
if confirm "🐳 Удалить неиспользуемые Docker образы?"; then
    echo "Очистка неиспользуемых образов..."
    docker image prune -f
fi

# Очистка неиспользуемых контейнеров
if confirm "📦 Удалить остановленные контейнеры?"; then
    echo "Очистка контейнеров..."
    docker container prune -f
fi

# Очистка неиспользуемых сетей
if confirm "🌐 Удалить неиспользуемые сети?"; then
    echo "Очистка сетей..."
    docker network prune -f
fi

# Полная очистка системы Docker
if confirm "⚠️ ВНИМАНИЕ: Выполнить полную очистку Docker системы?"; then
    echo "Полная очистка Docker системы..."
    docker system prune -af
fi

# Очистка логов
if confirm "📝 Очистить файлы логов?"; then
    echo "Очистка логов..."
    rm -rf logs/* 2>/dev/null || true
    echo "Логи очищены"
fi

# Очистка временных файлов приложения
if confirm "🗑️ Очистить временные файлы приложения?"; then
    echo "Очистка временных файлов..."
    rm -rf data/temp/* 2>/dev/null || true
    rm -rf data/cache/* 2>/dev/null || true
    echo "Временные файлы очищены"
fi

echo ""
echo "✅ Очистка завершена!"
echo ""
echo "📋 Для повторного запуска используйте:"
echo "  ./scripts/start-local.sh   # Локальный режим"
echo "  ./scripts/start-prod.sh    # Продакшн режим"