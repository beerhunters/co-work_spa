#!/bin/bash

# 🚀 ROOT SETUP SCRIPT - Автоматическая настройка сервера от root
# Этот скрипт должен запускаться ПЕРВЫМ от имени root

set -e

echo "🚀 Автоматическая настройка Production сервера (ROOT этап)"
echo "   Coworking Management System - Unified Architecture"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Проверка что запущено от root
if [[ $EUID -ne 0 ]]; then
   print_error "Этот скрипт должен запускаться от имени root!"
   print_status "Используйте: sudo ./scripts/root-setup.sh"
   exit 1
fi

# Получаем информацию о текущей директории
CURRENT_DIR="$(pwd)"
print_status "Текущая директория: $CURRENT_DIR"

# Проверка что мы находимся в проекте
if [ ! -f "docker-compose.yml" ] && [ ! -f ".env" ] && [ ! -d "scripts" ]; then
    print_error "Скрипт должен запускаться из корневой директории проекта!"
    print_status "Убедитесь, что вы находитесь в папке с docker-compose.yml и scripts/"
    exit 1
fi

# Функция проверки команды
check_command() {
    command -v $1 &> /dev/null
}

# Проверка системных требований
print_step "Проверка системных требований..."

# Проверка RAM (минимум 1GB, рекомендуется 2GB)
TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM" -lt 1024 ]; then
    print_warning "Мало RAM: ${TOTAL_RAM}MB (рекомендуется минимум 2048MB)"
    print_warning "Производительность может быть низкой"
else
    print_status "RAM: ${TOTAL_RAM}MB ✅"
fi

# Проверка свободного места (минимум 5GB)
AVAILABLE_SPACE=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
if [ "$AVAILABLE_SPACE" -lt 5 ]; then
    print_error "Недостаточно свободного места: ${AVAILABLE_SPACE}GB"
    print_error "Требуется минимум 5GB свободного места"
    exit 1
else
    print_status "Свободное место: ${AVAILABLE_SPACE}GB ✅"
fi

# Определение дистрибутива
print_step "Определение операционной системы..."
if [ -f /etc/os-release ]; then
    source /etc/os-release
    OS=$NAME
    VER=$VERSION_ID
    print_status "Операционная система: $OS $VER"
else
    print_error "Не удалось определить операционную систему"
    exit 1
fi

# Обновление системы
print_step "Обновление системы..."
if check_command apt; then
    print_status "Используется APT package manager..."
    apt update -y
    apt upgrade -y
    apt install -y curl wget git nano htop unzip software-properties-common openssl sudo ufw
elif check_command yum; then
    print_status "Используется YUM package manager..."
    yum update -y
    yum install -y curl wget git nano htop unzip openssl sudo firewalld
elif check_command dnf; then
    print_status "Используется DNF package manager..."
    dnf update -y
    dnf install -y curl wget git nano htop unzip openssl sudo firewalld
else
    print_error "Неподдерживаемый менеджер пакетов!"
    exit 1
fi

# Создание swap файла если его нет (для серверов с малым количеством RAM)
print_step "Настройка swap файла..."
if [ "$TOTAL_RAM" -lt 2048 ] && [ ! -f /swapfile ]; then
    print_status "Создание swap файла 2GB для улучшения производительности..."
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1024 count=2097152
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    print_status "Swap файл создан и активирован ✅"
elif [ -f /swapfile ]; then
    print_status "Swap файл уже существует ✅"
else
    print_status "Достаточно RAM, swap файл не требуется ✅"
fi

# Создание пользователя coworking
print_step "Создание пользователя для приложения..."

USERNAME="coworking"
USER_HOME="/home/$USERNAME"

if id "$USERNAME" &>/dev/null; then
    print_status "Пользователь $USERNAME уже существует ✅"
else
    print_status "Создание пользователя $USERNAME..."

    # Генерируем безопасный пароль
    USER_PASSWORD=$(openssl rand -base64 16)

    # Создаем пользователя
    adduser --disabled-password --gecos "Coworking System User" $USERNAME
    echo "$USERNAME:$USER_PASSWORD" | chpasswd

    # Добавляем в группу sudo
    usermod -aG sudo $USERNAME

    # Сохраняем пароль для администратора
    echo "# Данные пользователя $USERNAME" > /root/coworking-user-info.txt
    echo "Username: $USERNAME" >> /root/coworking-user-info.txt
    echo "Password: $USER_PASSWORD" >> /root/coworking-user-info.txt
    echo "Home: $USER_HOME" >> /root/coworking-user-info.txt
    echo "Created: $(date)" >> /root/coworking-user-info.txt
    chmod 600 /root/coworking-user-info.txt

    print_status "Пользователь $USERNAME создан ✅"
    print_status "Пароль сохранен в /root/coworking-user-info.txt"
fi

# Создание директории проекта в домашней папке пользователя
PROJECT_DIR="$USER_HOME/coworking-system"
print_step "Копирование проекта в $PROJECT_DIR..."

if [ -d "$PROJECT_DIR" ]; then
    print_status "Проект уже существует в $PROJECT_DIR"
    print_status "Обновляем файлы..."
    cp -rf "$CURRENT_DIR"/* "$PROJECT_DIR/"
    # Сохраняем .env если он был
    if [ -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env" "$PROJECT_DIR/.env.backup.$(date +%Y%m%d_%H%M%S)"
    fi
else
    print_status "Создание директории проекта..."
    mkdir -p "$PROJECT_DIR"
    cp -rf "$CURRENT_DIR"/* "$PROJECT_DIR/"
fi

# Установка правильных прав на файлы
chown -R $USERNAME:$USERNAME "$PROJECT_DIR"
chmod +x "$PROJECT_DIR"/scripts/*.sh

print_status "Проект скопирован и права установлены ✅"

# Настройка базового firewall
print_step "Настройка firewall..."
if check_command ufw; then
    # UFW (Ubuntu/Debian)
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw allow 8000/tcp
    ufw --force enable
    print_status "UFW firewall настроен ✅"
elif check_command firewall-cmd; then
    # Firewalld (CentOS/RHEL/Fedora)
    systemctl start firewalld
    systemctl enable firewalld
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --permanent --add-port=80/tcp
    firewall-cmd --permanent --add-port=443/tcp
    firewall-cmd --permanent --add-port=8000/tcp
    firewall-cmd --reload
    print_status "Firewalld настроен ✅"
else
    print_warning "Firewall не найден. Убедитесь, что порты 22, 80, 443, 8000 открыты!"
fi

# Настройка SSH для безопасности (опционально)
print_step "Улучшение безопасности SSH..."
SSH_CONFIG="/etc/ssh/sshd_config"

if [ -f "$SSH_CONFIG" ]; then
    # Создаем резервную копию
    cp "$SSH_CONFIG" "$SSH_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"

    # Разрешаем пользователю coworking подключаться по SSH
    if ! grep -q "^AllowUsers" "$SSH_CONFIG"; then
        echo "AllowUsers root $USERNAME" >> "$SSH_CONFIG"
        print_status "SSH доступ настроен для root и $USERNAME"
    fi

    # Можно добавить другие настройки безопасности
    # sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' "$SSH_CONFIG"  # Отключить root после настройки
fi

# Получение внешнего IP для информации
print_step "Определение внешнего IP адреса..."
EXTERNAL_IP=$(curl -s -m 10 ifconfig.me 2>/dev/null || curl -s -m 10 ipecho.net/plain 2>/dev/null || echo "не_определен")
if [ "$EXTERNAL_IP" != "не_определен" ]; then
    print_status "Внешний IP адрес: $EXTERNAL_IP ✅"
else
    print_warning "Не удалось определить внешний IP адрес"
fi

# Финальный этап - переключение на пользователя и продолжение установки
echo ""
echo "🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯"
print_status "       ROOT ЭТАП ЗАВЕРШЕН УСПЕШНО!"
echo "🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯🎯"
echo ""
print_status "✅ Система обновлена"
print_status "✅ Пользователь $USERNAME создан"
print_status "✅ Проект скопирован в $PROJECT_DIR"
print_status "✅ Firewall настроен"
print_status "✅ Права доступа установлены"
echo ""

echo "📋 СЛЕДУЮЩИЙ ЭТАП - НАСТРОЙКА ПРИЛОЖЕНИЯ:"
echo ""
print_step "Автоматически переключаемся на пользователя $USERNAME..."
echo ""

# Автоматически продолжаем установку от имени пользователя
if [ -f "$PROJECT_DIR/scripts/setup-production.sh" ]; then
    print_status "Запускаем основной скрипт установки..."
    echo "   Команда: su - $USERNAME -c 'cd coworking-system && ./scripts/setup-production.sh'"
    echo ""

    # Переключаемся на пользователя и продолжаем
    su - $USERNAME -c "cd coworking-system && ./scripts/setup-production.sh"

    echo ""
    echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
    print_status "       АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВЕРШЕНА!"
    echo "🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
    echo ""

    echo "📋 ФИНАЛЬНЫЕ ШАГИ:"
    echo ""
    echo "1. 🔐 Переключитесь на пользователя $USERNAME:"
    echo "   su - $USERNAME"
    echo ""
    echo "2. 📝 Отредактируйте конфигурацию:"
    echo "   cd coworking-system"
    echo "   nano .env"
    echo ""
    echo "3. 🚀 Запустите систему:"
    echo "   ./scripts/start-prod.sh"
    echo ""

    if [ "$EXTERNAL_IP" != "не_определен" ]; then
        echo "🌐 ПОСЛЕ ЗАПУСКА СИСТЕМА БУДЕТ ДОСТУПНА:"
        echo "   📱 Frontend: http://$EXTERNAL_IP"
        echo "   🔧 API: http://$EXTERNAL_IP:8000/api"
        echo "   📚 Docs: http://$EXTERNAL_IP:8000/docs"
        echo ""
    fi

    echo "👤 ДАННЫЕ ПОЛЬЗОВАТЕЛЯ (сохранены в /root/coworking-user-info.txt):"
    echo "   Username: $USERNAME"
    echo "   SSH: ssh $USERNAME@$EXTERNAL_IP"
    echo ""

    print_status "✨ Установка завершена! ✨"

else
    print_error "Скрипт setup-production.sh не найден!"
    print_status "РУЧНЫЕ ДЕЙСТВИЯ:"
    print_status "1. su - $USERNAME"
    print_status "2. cd coworking-system"
    print_status "3. ./scripts/setup-production.sh"
fi

echo ""