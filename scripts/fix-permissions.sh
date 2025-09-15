#!/bin/bash

# =============================================================================
# СКРИПТ ИСПРАВЛЕНИЯ ПРАВ ДОСТУПА
# =============================================================================

set -e

echo "🔧 Применение необходимых прав доступа для Coworking Management System..."

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

echo "📁 Исправление прав для директорий данных..."

# 1. Создаем необходимые директории если их нет
mkdir -p data avatars ticket_photos newsletter_photos logs config
mkdir -p data/backups

# 2. Устанавливаем правильного владельца для директорий данных
echo "👤 Установка владельца для директорий данных..."
sudo chown -R coworking:coworking data avatars ticket_photos newsletter_photos logs config

# 3. Устанавливаем права доступа для директорий данных (777 для совместимости с Docker)
echo "🔐 Установка прав доступа для директорий данных..."
chmod -R 777 data avatars ticket_photos newsletter_photos logs config

# 4. Создаем лог-файл с правильными правами если его нет
if [ ! -f "logs/app.log" ]; then
    touch logs/app.log
fi
chmod 666 logs/app.log

echo "🔒 Исправление прав доступа для SSL сертификатов..."

# 5. Проверяем наличие SSL сертификатов
if [ -d "/etc/letsencrypt" ]; then
    echo "📜 Найдена директория Let's Encrypt, применяем права доступа..."
    
    # Устанавливаем права для чтения SSL сертификатов
    sudo chmod 755 /etc/letsencrypt/live 2>/dev/null || true
    sudo chmod 755 /etc/letsencrypt/archive 2>/dev/null || true
    
    # Читаем DOMAIN_NAME из .env если файл существует
    if [ -f ".env" ]; then
        DOMAIN_NAME=$(grep "^DOMAIN_NAME=" .env | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        
        if [ ! -z "$DOMAIN_NAME" ] && [ -d "/etc/letsencrypt/live/$DOMAIN_NAME" ]; then
            echo "🌐 Применяем права для домена: $DOMAIN_NAME"
            
            # Устанавливаем права для приватного ключа
            sudo chmod 644 /etc/letsencrypt/archive/$DOMAIN_NAME/privkey*.pem 2>/dev/null || true
            
            echo "✅ Права для SSL сертификатов домена $DOMAIN_NAME установлены"
        else
            echo "⚠️ Домен $DOMAIN_NAME не найден или не указан в .env"
        fi
    else
        echo "⚠️ Файл .env не найден, пропускаем настройку SSL"
    fi
else
    echo "ℹ️ Let's Encrypt не установлен, пропускаем настройку SSL"
fi

echo "🐋 Проверка Docker Compose конфигурации..."

# 6. Проверяем наличие user mapping в docker-compose.yml
if ! grep -q "user: \"1000:1000\"" docker-compose.yml; then
    echo "🔄 Добавляем user mapping в docker-compose.yml..."
    
    # Создаем резервную копию
    cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d_%H%M%S)
    
    # Добавляем user mapping для web сервиса
    sed -i '/^  web:/,/^  [a-z]/ { /target: \${BUILD_TARGET.*}/a \    user: "1000:1000"
}' docker-compose.yml
    
    # Добавляем user mapping для bot сервиса
    sed -i '/^  bot:/,/^  [a-z]/ { /target: \${BUILD_TARGET.*}/a \    user: "1000:1000"
}' docker-compose.yml
    
    echo "✅ User mapping добавлен в docker-compose.yml"
else
    echo "✅ User mapping уже присутствует в docker-compose.yml"
fi

echo ""
echo "🎉 Все права доступа успешно применены!"
echo ""
echo "📋 Что было сделано:"
echo "  ✅ Созданы необходимые директории"
echo "  ✅ Установлен владелец coworking:coworking для директорий данных"
echo "  ✅ Установлены права 777 для директорий данных (совместимость с Docker)"
echo "  ✅ Установлены права 666 для лог-файла"
if [ -d "/etc/letsencrypt" ]; then
    echo "  ✅ Установлены права доступа для SSL сертификатов"
fi
echo "  ✅ Добавлен user mapping в docker-compose.yml"
echo ""
echo "🚀 Теперь можно запускать: ./scripts/start-prod.sh"

