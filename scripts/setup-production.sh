#!/bin/bash

# 🚀 СКРИПТ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ PRODUCTION СЕРВЕРА
# Максимально простой и надежный деплой

set -e  # Остановка при любой ошибке

echo "🚀 Настройка Coworking Management System на production сервере..."
echo ""

# Получаем абсолютный путь к проекту
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_step() {
    echo -e "${BLUE}📋 $1${NC}"
}

# ЭТАП 1: Проверки системы
print_step "ЭТАП 1: Проверка системы и прав доступа"

# Проверка, что не root
if [[ $EUID -eq 0 ]]; then
   print_error "Скрипт запущен от root!"
   print_info "Для безопасности создайте отдельного пользователя:"
   echo ""
   echo "  adduser coworking"
   echo "  usermod -aG sudo coworking"
   echo "  su - coworking"
   echo ""
   print_info "Затем повторите: ./scripts/setup-production.sh"
   exit 1
fi

print_status "Пользователь не root - ОК"

# Проверка sudo
if ! sudo -n true 2>/dev/null; then
    print_error "Нет sudo прав!"
    print_info "Выполните: sudo usermod -aG sudo $(whoami)"
    print_info "Затем перелогиньтесь: exit && ssh user@server"
    exit 1
fi

print_status "Sudo права есть - ОК"

# Определение ОС
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$ID
    print_status "Операционная система: $PRETTY_NAME"
else
    print_error "Не удается определить операционную систему"
    exit 1
fi

# ЭТАП 2: Установка Docker
print_step "ЭТАП 2: Установка и настройка Docker"

if command -v docker &> /dev/null; then
    print_status "Docker уже установлен"
    docker --version
else
    print_info "Устанавливаем Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    print_status "Docker установлен"
fi

# Проверка Docker Compose
print_info "Проверяем Docker Compose..."

# Проверяем доступные варианты
if docker compose version > /dev/null 2>&1; then
    print_status "Docker Compose v2 (встроенный) доступен"
    docker compose version
elif command -v docker-compose &> /dev/null; then
    print_status "Docker Compose v1 найден"
    docker-compose --version
    
    # Проверяем версию
    COMPOSE_VERSION=$(docker-compose --version 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+' | head -1)
    MAJOR_VERSION=$(echo "$COMPOSE_VERSION" | cut -d. -f1)
    
    if [[ "$MAJOR_VERSION" -lt "2" ]] 2>/dev/null; then
        print_info "Устанавливаем современную версию Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
        print_status "Docker Compose обновлен до современной версии"
        docker-compose --version
    else
        print_status "Версия Docker Compose подходящая: $COMPOSE_VERSION"
    fi
else
    print_info "Устанавливаем Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    print_status "Docker Compose установлен"
    docker-compose --version
fi

# Добавление пользователя в группу docker
if groups "$USER" | grep &>/dev/null '\bdocker\b'; then
    print_status "Пользователь уже в группе docker"
    NEED_RELOGIN=false
else
    print_info "Добавляем пользователя в группу docker..."
    sudo usermod -aG docker "$USER"
    print_warning "Потребуется перелогиниться после завершения скрипта!"
    NEED_RELOGIN=true
fi

# Настройка Docker daemon
print_info "Настраиваем Docker daemon..."
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "log-driver": "json-file", 
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

sudo systemctl restart docker
sudo systemctl enable docker
print_status "Docker настроен"

# ЭТАП 3: Настройка системы
print_step "ЭТАП 3: Настройка системы"

# Обновление пакетов
print_info "Обновляем систему..."
sudo apt update && sudo apt upgrade -y

# Установка необходимых пакетов
print_info "Устанавливаем необходимые пакеты..."
sudo apt install -y curl wget git nano htop unzip fail2ban ufw

# Настройка firewall
print_info "Настраиваем firewall..."
sudo ufw --force enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
print_status "Firewall настроен (порты 22, 80, 443)"

# Настройка fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
print_status "Fail2ban активирован"

# ЭТАП 4: Подготовка проекта
print_step "ЭТАП 4: Настройка проекта"

# Создание директорий
print_info "Создаем директории для данных..."
mkdir -p data logs avatars ticket_photos newsletter_photos config
print_status "Директории созданы"

# Настройка .env файла
if [[ ! -f .env ]]; then
    if [[ -f .env.example ]]; then
        print_info "Создаем .env из .env.example..."
        cp .env.example .env
        
        # Настройка для продакшена
        sed -i 's/BUILD_TARGET=development/BUILD_TARGET=production/' .env
        sed -i 's/ENVIRONMENT=development/ENVIRONMENT=production/' .env
        sed -i 's/DEBUG=true/DEBUG=false/' .env
        
        # Генерация секретных ключей
        print_info "Генерируем безопасные ключи..."
        SECRET_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
        JWT_KEY=$(python3 -c "import os; print(os.urandom(32).hex())")
        
        sed -i "s/your-secret-key-change-me/$SECRET_KEY/" .env
        sed -i "s/your-jwt-secret-key-change-me/$JWT_KEY/" .env
        
        print_status ".env файл создан с безопасными ключами"
    else
        print_error ".env.example не найден!"
        exit 1
    fi
else
    print_status ".env файл уже существует"
fi

# Создание управляющих скриптов
print_info "Создаем управляющие скрипты..."

# Скрипт запуска продакшена
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск Coworking System в продакшен режиме..."
./scripts/start-prod.sh
EOF
chmod +x start.sh

# Скрипт остановки
cat > stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Остановка Coworking System..."
docker-compose down
echo "✅ Система остановлена"
EOF
chmod +x stop.sh

# Скрипт проверки статуса
cat > status.sh << 'EOF'
#!/bin/bash
echo "📊 Статус Coworking System:"
./scripts/status.sh
EOF
chmod +x status.sh

# Скрипт просмотра логов
cat > logs.sh << 'EOF'
#!/bin/bash
if [ -n "$1" ]; then
    echo "📋 Логи сервиса $1:"
    docker-compose logs -f "$1"
else
    echo "📋 Логи всех сервисов:"
    docker-compose logs -f
fi
EOF
chmod +x logs.sh

# Скрипт рестарта
cat > restart.sh << 'EOF'
#!/bin/bash
echo "🔄 Перезапуск Coworking System..."
docker-compose down
./scripts/start-prod.sh
EOF
chmod +x restart.sh

print_status "Управляющие скрипты созданы"

# ЭТАП 5: Финальная настройка
print_step "ЭТАП 5: Финальная настройка"

# Права доступа
print_info "Настраиваем права доступа..."
chmod +x scripts/*.sh
print_status "Права настроены"

# Проверка Docker Compose
print_info "Проверяем docker-compose.yml..."

# Проверяем разные способы вызова docker compose
if docker compose version > /dev/null 2>&1; then
    # Новый синтаксис (Docker Compose v2)
    COMPOSE_CMD="docker compose"
elif docker-compose --version > /dev/null 2>&1; then
    # Старый синтаксис (Docker Compose v1)  
    COMPOSE_CMD="docker-compose"
else
    print_error "Docker Compose не найден!"
    exit 1
fi

print_info "Используется команда: $COMPOSE_CMD"

# Устанавливаем минимальные переменные для проверки конфигурации
export BUILD_TARGET=production
export ENVIRONMENT=production
export DEBUG=false
export HOST=0.0.0.0
export PORT=8000
export API_BASE_URL_EXTERNAL=https://example.com/api
export API_BASE_URL_INTERNAL=http://web:8000
export FRONTEND_URL=https://example.com
export DOMAIN_NAME=example.com
export BOT_TOKEN=test_token
export ADMIN_TELEGRAM_ID=123456789
export BOT_LINK=https://t.me/test_bot
export INVITE_LINK=https://t.me/test_bot
export GROUP_ID=123456789
export FOR_LOGS=123456789
export SECRET_KEY=test_secret_key_for_config_check
export SECRET_KEY_JWT=test_jwt_secret_key_for_config_check
export ADMIN_LOGIN=admin
export ADMIN_PASSWORD=admin
export CORS_ORIGINS=http://localhost
export ACCESS_TOKEN_EXPIRE_HOURS=24
export YOKASSA_ACCOUNT_ID=test_account
export YOKASSA_SECRET_KEY=test_secret
export RUBITIME_API_KEY=test_api_key
export RUBITIME_BASE_URL=https://rubitime.ru/api2/
export RUBITIME_BRANCH_ID=12595
export RUBITIME_COOPERATOR_ID=25786
export REDIS_URL=redis://redis:6379/0
export APP_NAME="Coworking API"
export APP_VERSION="1.0.0"

print_info "Проверяем конфигурацию docker-compose с тестовыми переменными..."
if $COMPOSE_CMD config > /dev/null 2>&1; then
    print_status "Docker Compose конфигурация корректна"
else
    print_warning "Проверка docker-compose.yml показала предупреждения"
    print_info "Это нормально для первичной настройки - конфигурация будет проверена при запуске"
    print_info "Убедитесь, что все переменные в .env файле заполнены корректно"
fi

# Обновляем скрипты для использования правильной команды
print_info "Обновляем управляющие скрипты..."

# Обновленный скрипт остановки
cat > stop.sh << EOF
#!/bin/bash
echo "🛑 Остановка Coworking System..."
$COMPOSE_CMD down
echo "✅ Система остановлена"
EOF
chmod +x stop.sh

# Обновленный скрипт просмотра логов
cat > logs.sh << EOF
#!/bin/bash
if [ -n "\$1" ]; then
    echo "📋 Логи сервиса \$1:"
    $COMPOSE_CMD logs -f "\$1"
else
    echo "📋 Логи всех сервисов:"
    $COMPOSE_CMD logs -f
fi
EOF
chmod +x logs.sh

# Обновленный скрипт рестарта
cat > restart.sh << EOF
#!/bin/bash
echo "🔄 Перезапуск Coworking System..."
$COMPOSE_CMD down
./scripts/start-prod.sh
EOF
chmod +x restart.sh

# Вывод итогов
echo ""
echo "🎉 Настройка production сервера завершена!"
echo ""
print_step "СЛЕДУЮЩИЕ ШАГИ:"
echo ""

if [[ $NEED_RELOGIN == true ]]; then
    print_warning "1. ОБЯЗАТЕЛЬНО перелогиньтесь для применения прав docker:"
    echo "   exit"
    echo "   ssh $(whoami)@$(hostname -I | awk '{print $1}')"
    echo ""
fi

print_info "2. Настройте .env файл:"
echo "   nano .env"
echo ""
echo "   Обязательно заполните:"
echo "   - BOT_TOKEN=ваш_токен_бота"
echo "   - ADMIN_TELEGRAM_ID=ваш_telegram_id"  
echo "   - ADMIN_PASSWORD=безопасный_пароль"
echo "   - DOMAIN_NAME=ваш_домен.com (если есть)"
echo ""

print_info "3. (Опционально) Настройте SSL:"
echo "   ./scripts/setup-ssl.sh"
echo ""

print_info "4. Запустите систему:"
echo "   ./start.sh"
echo ""

print_status "Готовые команды для управления:"
echo "   ./start.sh     - Запуск"
echo "   ./stop.sh      - Остановка"
echo "   ./restart.sh   - Перезапуск"
echo "   ./status.sh    - Проверка статуса"
echo "   ./logs.sh      - Просмотр логов"
echo ""

if [[ $NEED_RELOGIN == true ]]; then
    print_warning "⚠️  НЕ ЗАБУДЬТЕ ПЕРЕЛОГИНИТЬСЯ!"
fi