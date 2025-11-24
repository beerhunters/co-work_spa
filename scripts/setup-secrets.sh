#!/bin/bash

# ==============================================================================
# Setup Secrets Script
# ==============================================================================
# Автоматически генерирует и создает файлы секретов для приложения
# Использование: ./scripts/setup-secrets.sh [--force]
# ==============================================================================

set -e  # Exit on error

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Директория секретов
SECRETS_DIR="./secrets"
FORCE=false

# Парсинг аргументов
if [[ "$1" == "--force" ]]; then
    FORCE=true
fi

echo -e "${GREEN}🔐 Setup Secrets Script${NC}"
echo "================================"

# Создать директорию если не существует
mkdir -p "$SECRETS_DIR"

# Функция для генерации случайного секрета
generate_secret() {
    openssl rand -hex 32
}

# Функция для создания файла секрета
create_secret_file() {
    local name=$1
    local file="$SECRETS_DIR/${name}.txt"

    # Проверить существование
    if [[ -f "$file" ]] && [[ "$FORCE" != true ]]; then
        echo -e "${YELLOW}⚠️  $name уже существует (используйте --force для перезаписи)${NC}"
        return
    fi

    # Генерировать или запросить значение
    if [[ "$2" == "generate" ]]; then
        local value=$(generate_secret)
        echo "$value" > "$file"
        echo -e "${GREEN}✅ $name создан (сгенерирован)${NC}"
    else
        read -sp "Введите значение для $name: " value
        echo ""
        if [[ -z "$value" ]]; then
            echo -e "${RED}❌ Пустое значение, пропускаем $name${NC}"
            return
        fi
        echo "$value" > "$file"
        echo -e "${GREEN}✅ $name создан${NC}"
    fi

    # Установить права доступа
    chmod 600 "$file"
}

echo ""
echo "Создание секретов..."
echo ""

# Генерация автоматических секретов
create_secret_file "SECRET_KEY" "generate"
create_secret_file "SECRET_KEY_JWT" "generate"

# Секреты требующие ввода
echo ""
echo "Теперь введите значения для внешних сервисов:"
echo ""

create_secret_file "BOT_TOKEN" "manual"
create_secret_file "YOKASSA_SECRET_KEY" "manual"
create_secret_file "SMTP_PASSWORD" "manual"
create_secret_file "ADMIN_PASSWORD" "manual"

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Secrets setup complete!${NC}"
echo ""
echo "Созданные файлы:"
ls -lh "$SECRETS_DIR"/*.txt 2>/dev/null || echo "Нет созданных секретов"
echo ""
echo -e "${YELLOW}⚠️  ВАЖНО:${NC}"
echo "  - Проверьте что $SECRETS_DIR добавлен в .gitignore"
echo "  - Никогда не коммитьте секреты в Git"
echo "  - В production используйте Docker secrets или vault"
echo ""
