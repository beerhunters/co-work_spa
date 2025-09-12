#!/bin/bash

# 🚀 QUICK DEPLOY - Быстрый деплой Coworking Management System одной командой
# Поддерживает как root, так и обычного пользователя

set -e

echo "🚀 Быстрый деплой Coworking Management System"
echo "   Автоматическая настройка production сервера"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

print_header() {
    echo -e "${PURPLE}[DEPLOY]${NC} $1"
}

# Проверяем права пользователя
if [[ $EUID -eq 0 ]]; then
    print_header "Запущено от имени ROOT - полная автоматическая настройка"

    # Проверяем наличие root-setup.sh
    if [ -f "scripts/root-setup.sh" ]; then
        print_step "Запуск автоматической настройки от root..."
        chmod +x scripts/root-setup.sh
        ./scripts/root-setup.sh
    else
        print_step "Скрипт root-setup.sh не найден, выполняем базовую настройку..."

        # Базовая настройка если нет root-setup.sh
        print_status "Обновление системы..."
        if command -v apt &> /dev/null; then
            apt update -y && apt install -y curl git sudo
        elif command -v yum &> /dev/null; then
            yum update -y && yum install -y curl git sudo
        elif command -v dnf &> /dev/null; then
            dnf update -y && dnf install -y curl git sudo
        fi

        # Создание пользователя
        USERNAME="coworking"
        if ! id "$USERNAME" &>/dev/null; then
            print_status "Создание пользователя $USERNAME..."
            adduser --disabled-password --gecos "Coworking User" $USERNAME 2>/dev/null || useradd -m $USERNAME
            echo "$USERNAME:$(openssl rand -base64 12)" | chpasswd
            usermod -aG sudo $USERNAME 2>/dev/null || usermod -aG wheel $USERNAME
        fi

        # Копирование проекта
        USER_HOME="/home/$USERNAME"
        PROJECT_DIR="$USER_HOME/coworking-system"
        mkdir -p "$PROJECT_DIR"
        cp -rf "$(pwd)"/* "$PROJECT_DIR/"
        chown -R $USERNAME:$USERNAME "$PROJECT_DIR"
        chmod +x "$PROJECT_DIR"/scripts/*.sh

        print_status "Переключение на пользователя $USERNAME..."
        su - $USERNAME -c "cd coworking-system && ./scripts/setup-production.sh"
    fi

else
    print_header "Запущено от обычного пользователя - настройка приложения"

    # Проверяем sudo доступ
    if ! sudo -n true 2>/dev/null; then
        print_error "Пользователь $USER не имеет sudo доступа!"
        print_status "Решение:"
        print_status "1. Попросите администратора добавить вас в группу sudo:"
        print_status "   sudo usermod -aG sudo $USER"
        print_status "2. Или запустите от root: sudo ./quick-deploy.sh"
        exit 1
    fi

    # Запуск основного скрипта настройки
    if [ -f "scripts/setup-production.sh" ]; then
        print_step "Запуск настройки production сервера..."
        chmod +x scripts/setup-production.sh
        ./scripts/setup-production.sh
    else
        print_error "Скрипт scripts/setup-production.sh не найден!"
        print_status "Убедитесь, что вы находитесь в корневой директории проекта"
        exit 1
    fi
fi

echo ""
echo "✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅"
print_header "           БЫСТРЫЙ ДЕПЛОЙ ЗАВЕРШЕН!"
echo "✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅"
echo ""

# Определяем где находится проект
if [[ $EUID -eq 0 ]]; then
    PROJECT_PATH="/home/coworking/coworking-system"
    print_status "Проект установлен в: $PROJECT_PATH"
    print_status "Пользователь: coworking"
else
    PROJECT_PATH="$(pwd)"
    print_status "Проект в: $PROJECT_PATH"
    print_status "Пользователь: $USER"
fi

echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo ""

if [[ $EUID -eq 0 ]]; then
    echo "1. 🔐 Переключитесь на рабочего пользователя:"
    echo "   su - coworking"
    echo ""
    echo "2. 📝 Настройте конфигурацию:"
    echo "   cd coworking-system"
    echo "   nano .env"
    echo ""
else
    echo "1. 📝 Настройте конфигурацию:"
    echo "   nano .env"
    echo ""
fi

echo "2. 🚀 Запустите систему:"
echo "   ./scripts/start-prod.sh"
echo ""
echo "3. 🏥 Проверьте статус:"
echo "   ./scripts/status.sh"
echo ""

# Получение внешнего IP для отображения ссылок
EXTERNAL_IP=$(curl -s -m 5 ifconfig.me 2>/dev/null || curl -s -m 5 ipecho.net/plain 2>/dev/null || echo "your_server_ip")

echo "🌐 ПОСЛЕ ЗАПУСКА СИСТЕМА БУДЕТ ДОСТУПНА:"
if [ "$EXTERNAL_IP" != "your_server_ip" ]; then
    echo "   📱 Frontend: http://$EXTERNAL_IP"
    echo "   🔧 API: http://$EXTERNAL_IP:8000/api"
    echo "   📚 Docs: http://$EXTERNAL_IP:8000/docs"
else
    echo "   📱 Frontend: http://your_server_ip"
    echo "   🔧 API: http://your_server_ip:8000/api"
    echo "   📚 Docs: http://your_server_ip:8000/docs"
fi
echo ""

echo "🔧 ПОЛЕЗНЫЕ КОМАНДЫ:"
echo "   ./scripts/logs.sh          - Просмотр логов"
echo "   ./scripts/restart.sh       - Перезапуск системы"
echo "   ./scripts/stop.sh          - Остановка системы"
echo "   ./scripts/cleanup.sh       - Полная очистка"
echo ""

print_status "🎉 Готово к использованию!"
echo ""