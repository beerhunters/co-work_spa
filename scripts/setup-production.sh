#!/bin/bash

# 🚀 СКРИПТ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ PRODUCTION СЕРВЕРА
# Этот скрипт автоматизирует весь процесс настройки для новой унифицированной архитектуры

set -e  # Остановка при любой ошибке

echo "🚀 Начинаем настройку Coworking Management System на production сервере..."
echo "   Используется новая унифицированная архитектура с environment-specific скриптами"
echo ""

# Получаем абсолютный путь к проекту (на уровень выше от scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Переходим в корневую директорию проекта
cd "$PROJECT_DIR"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода статуса
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root
if [[ $EUID -eq 0 ]]; then
   print_error "Этот скрипт не должен запускаться от имени root!"
   print_status "Создайте отдельного пользователя:"
   print_status "  adduser coworking"
   print_status "  usermod -aG sudo coworking" 
   print_status "  usermod -aG docker coworking"
   print_status "  su - coworking"
   print_status "Затем запустите: ./setup-production.sh"
   exit 1
fi

# Проверка sudo доступа
if ! sudo -n true 2>/dev/null; then
    print_error "Пользователь $USER не имеет sudo доступа!"
    print_status "Добавьте пользователя в группу sudo:"
    print_status "  sudo usermod -aG sudo $USER"
    print_status "Затем перелогиньтесь и повторите попытку"
    exit 1
fi

# Функция проверки команды
check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# 1. Обновление системы
print_status "Обновление системы..."
if check_command apt; then
    sudo apt update && sudo apt upgrade -y
    sudo apt install -y curl wget git nano htop unzip software-properties-common openssl
elif check_command yum; then
    sudo yum update -y
    sudo yum install -y curl wget git nano htop unzip openssl
elif check_command dnf; then
    sudo dnf update -y
    sudo dnf install -y curl wget git nano htop unzip openssl
else
    print_error "Неподдерживаемая система пакетов!"
    exit 1
fi

# 2. Установка Docker
if ! check_command docker; then
    print_status "Установка Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    print_status "Docker установлен. ВНИМАНИЕ: Требуется перелогиниться для активации группы docker!"
else
    print_status "Docker уже установлен: $(docker --version)"
fi

# 3. Установка Docker Compose
if ! check_command docker-compose; then
    print_status "Установка Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    print_status "Docker Compose уже установлен: $(docker-compose --version)"
fi

# 4. Настройка Docker для production
print_status "Настройка Docker для production..."
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

sudo systemctl restart docker || true
sudo systemctl enable docker || true

# Проверка логина в Docker Hub
print_status "Проверка авторизации Docker Hub..."
if ! docker info >/dev/null 2>&1; then
    print_warning "Docker недоступен (возможно требуется перелогин для применения группы docker)"
    print_status "После перелогина выполните: docker login"
elif docker pull hello-world:latest >/dev/null 2>&1; then
    docker rmi hello-world:latest >/dev/null 2>&1
    print_status "Доступ к Docker Hub работает"
else
    print_warning "Возможны проблемы с Docker Hub. При необходимости выполните: docker login"
fi

# 5. Настройка firewall
print_status "Настройка firewall..."
if check_command ufw; then
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw allow 8000/tcp
    sudo ufw --force enable
    print_status "UFW firewall настроен (разрешены порты: SSH, 80, 443, 8000)"
elif check_command firewall-cmd; then
    sudo firewall-cmd --permanent --add-service=ssh
    sudo firewall-cmd --permanent --add-port=80/tcp
    sudo firewall-cmd --permanent --add-port=443/tcp
    sudo firewall-cmd --permanent --add-port=8000/tcp
    sudo firewall-cmd --reload
    print_status "Firewall настроен (разрешены порты: SSH, 80, 443, 8000)"
else
    print_warning "Firewall не найден. Убедитесь, что порты 80, 443, 8000 открыты!"
fi

# 6. Проверка, что мы находимся в директории проекта
if [ ! -f "docker-compose.yml" ] || [ ! -f ".env" ]; then
    print_error "Скрипт должен запускаться из корневой директории проекта!"
    print_status "Убедитесь, что вы находитесь в папке с файлами docker-compose.yml и .env"
    print_status "Например:"
    print_status "  git clone <your-repo-url> coworking"
    print_status "  cd coworking"
    print_status "  ./setup-production.sh"
    exit 1
fi

PROJECT_DIR=$(pwd)
print_status "Работаем в директории: $PROJECT_DIR"

# 7. Обновление репозитория (если это git репозиторий)
if [ -d ".git" ]; then
    print_status "Обновление репозитория..."
    git pull origin main || print_warning "Не удалось обновить репозиторий (возможно есть локальные изменения)"
else
    print_status "Проект не является git репозиторием, пропускаем обновление"
fi

# 8. Создание необходимых директорий
print_status "Создание директорий для данных..."
mkdir -p data avatars ticket_photos newsletter_photos logs config
chmod -R 755 data avatars ticket_photos newsletter_photos logs config
print_status "Созданы директории: data/, avatars/, ticket_photos/, newsletter_photos/, logs/, config/"

# 9. Настройка переменных окружения
print_status "Настройка переменных окружения..."

# Создание резервной копии .env если нужно
if [ -f ".env" ]; then
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    print_status "Создана резервная копия .env файла"
fi

# Запрос домена и email
echo ""
print_status "Настройка SSL и домена..."
read -p "Введите ваш домен (например: example.com, или оставьте пустым для localhost): " DOMAIN_NAME
if [ -n "$DOMAIN_NAME" ]; then
    read -p "Введите email для Let's Encrypt уведомлений: " SSL_EMAIL
fi

# Обновление DOMAIN_NAME в .env
if [ -n "$DOMAIN_NAME" ]; then
    if grep -q "^DOMAIN_NAME=" .env; then
        sed -i "s/^DOMAIN_NAME=.*/DOMAIN_NAME=$DOMAIN_NAME/" .env
    else
        echo "DOMAIN_NAME=$DOMAIN_NAME" >> .env
    fi
    print_status "Домен установлен: $DOMAIN_NAME"
else
    DOMAIN_NAME="localhost"
    print_status "Используется localhost (без SSL)"
fi

# Генерация безопасных ключей если они не установлены
if grep -q "your-super-secret-key-change-in-production" .env; then
    print_status "Генерация безопасных ключей..."
    SECRET_KEY=$(openssl rand -hex 32)
    SECRET_JWT_KEY=$(openssl rand -hex 32)
    
    sed -i "s/your-super-secret-key-change-in-production/$SECRET_KEY/" .env
    sed -i "s/your-super-secret-key-change-in-production/$SECRET_JWT_KEY/" .env
    print_status "Секретные ключи сгенерированы и установлены"
fi

# 10. Информация о настройке
echo ""
print_warning "ВАЖНО! Отредактируйте .env файл и проверьте следующие параметры:"
print_warning "- BOT_TOKEN (получите у @BotFather)"
print_warning "- ADMIN_TELEGRAM_ID (узнайте у @userinfobot)" 
print_warning "- ADMIN_PASSWORD (установите надежный пароль)"
print_warning "- YOKASSA_* (настройки платежной системы)"
print_warning "- RUBITIME_* (настройки внешней системы бронирования)"
echo ""

# 11. Установка прав на скрипты
print_status "Установка прав на управляющие скрипты..."
chmod +x scripts/*.sh
print_status "Установлены права на выполнение для всех .sh файлов в папке scripts/"

# 12. Создание systemd сервиса для автозапуска
print_status "Создание systemd сервиса для автозапуска..."
sudo tee /etc/systemd/system/coworking.service > /dev/null <<EOF
[Unit]
Description=Coworking Management System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/scripts/start-prod.sh
ExecStop=$PROJECT_DIR/scripts/stop.sh
TimeoutStartSec=0
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable coworking.service
print_status "Systemd сервис создан и включен для автозапуска"

# 13. Настройка автоматических бэкапов
print_status "Настройка автоматических бэкапов..."
# Создаем cron задачу для ежедневного бэкапа в 2:00
(crontab -l 2>/dev/null | grep -v "coworking backup"; echo "0 2 * * * cd $PROJECT_DIR && docker-compose exec -T web python -c \"import sys; sys.path.append('/app'); from utils.backup_manager import create_backup; import asyncio; asyncio.run(create_backup())\" >> $PROJECT_DIR/logs/backup.log 2>&1") | crontab - || true
print_status "Автоматические бэкапы настроены (ежедневно в 2:00)"

# 14. Проверка групп пользователя
print_status "Проверка настройки групп пользователя..."
if groups $USER | grep -q docker; then
    print_status "✅ Пользователь $USER добавлен в группу docker"
else
    print_warning "⚠️ Пользователь $USER НЕ в группе docker. Требуется перелогиниться!"
    print_status "Выполните: sudo usermod -aG docker $USER && su - $USER"
fi

if groups $USER | grep -q sudo; then
    print_status "✅ Пользователь $USER имеет sudo права"
else
    print_warning "⚠️ Пользователь $USER НЕ имеет sudo права"
fi

# 15. Завершение и инструкции
echo ""
echo "🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉"
print_status "       НАСТРОЙКА PRODUCTION СЕРВЕРА ЗАВЕРШЕНА!"
echo "🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉"
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo ""
echo "1. 📝 ОБЯЗАТЕЛЬНО отредактируйте .env файл:"
echo "   nano .env"
echo ""
echo "2. 🔑 Проверьте и установите следующие параметры в .env:"
echo "   ✓ BOT_TOKEN=ваш_токен_от_BotFather"
echo "   ✓ ADMIN_TELEGRAM_ID=ваш_telegram_id"
echo "   ✓ ADMIN_PASSWORD=надежный_пароль"
echo "   ✓ SECRET_KEY (уже сгенерирован)"
echo "   ✓ SECRET_KEY_JWT (уже сгенерирован)"
echo "   ✓ DOMAIN_NAME=$DOMAIN_NAME"
echo ""

if [ "$DOMAIN_NAME" != "localhost" ]; then
    echo "3. 🔒 Получите SSL сертификаты:"
    echo "   ./scripts/setup-ssl.sh"
    echo ""
fi

echo "4. 🚀 Запустите систему:"
echo "   ./scripts/start-prod.sh"
echo ""
echo "5. 🏥 Проверьте статус:"
echo "   ./scripts/status.sh"
echo ""
echo "📁 ДОСТУПНЫЕ КОМАНДЫ:"
echo "   ./scripts/start-prod.sh       - запуск в продакшн режиме"
echo "   ./scripts/start-local.sh      - запуск в локальном режиме"
echo "   ./scripts/stop.sh             - остановка всех сервисов"
echo "   ./scripts/restart.sh          - перезапуск сервисов"
echo "   ./scripts/status.sh           - проверка статуса системы"
echo "   ./scripts/logs.sh [service]   - просмотр логов"
echo "   ./scripts/cleanup.sh          - полная очистка системы"
echo ""
echo "🌐 ПОСЛЕ ЗАПУСКА СИСТЕМА БУДЕТ ДОСТУПНА НА:"

# Определяем URL на основе настроек
if [ "$DOMAIN_NAME" != "localhost" ] && [ -n "$DOMAIN_NAME" ]; then
    if [ -n "$SSL_EMAIL" ]; then
        echo "   🔒 Frontend: https://$DOMAIN_NAME"
        echo "   🔒 API: https://$DOMAIN_NAME/api"
        echo "   🔒 Docs: https://$DOMAIN_NAME/docs"
        echo ""
        print_warning "   Не забудьте получить SSL сертификат: ./scripts/setup-ssl.sh"
    else
        echo "   📱 Frontend: http://$DOMAIN_NAME"
        echo "   🔧 API: http://$DOMAIN_NAME:8000/api"
        echo "   📚 Docs: http://$DOMAIN_NAME:8000/docs"
    fi
else
    # Пытаемся определить внешний IP
    EXTERNAL_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipecho.net/plain 2>/dev/null || echo "your_server_ip")
    echo "   📱 Frontend: http://$EXTERNAL_IP"
    echo "   🔧 API: http://$EXTERNAL_IP:8000/api"
    echo "   📚 Docs: http://$EXTERNAL_IP:8000/docs"
fi

echo ""
echo "⚠️ ВАЖНЫЕ НАПОМИНАНИЯ:"
if ! groups $USER | grep -q docker; then
    print_warning "   🔄 ПЕРЕЛОГИНЬТЕСЬ для применения прав группы docker:"
    print_warning "      exit && ssh user@server"
fi
print_warning "   🐳 Выполните docker login если требуется доступ к приватным образам"
print_warning "   🔐 Измените пароли по умолчанию в .env файле"
print_warning "   🔥 Настройте backup стратегию для продакшена"
echo ""
echo "🎯 АВТОМАТИЗАЦИЯ:"
echo "   ✅ Systemd сервис: sudo systemctl start coworking"
echo "   ✅ Автозапуск при перезагрузке: включен"  
echo "   ✅ Автоматические бэкапы: настроены (2:00 каждый день)"
echo ""
print_status "✨ Готово к продакшн деплою! Удачи! ✨"
echo ""