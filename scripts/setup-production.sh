#!/bin/bash

# 🚀 СКРИПТ АВТОМАТИЧЕСКОЙ НАСТРОЙКИ PRODUCTION СЕРВЕРА
# Этот скрипт автоматизирует весь процесс настройки

set -e  # Остановка при любой ошибке

echo "🚀 Начинаем настройку Coworking Management System на production сервере..."

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
   print_status "  su - coworking"
   print_status "Затем запустите: ./setup-production.sh"
   exit 1
fi

# Проверка sudo доступа
if ! sudo -n true 2>/dev/null; then
    print_error "Пользователь $USER не имеет sudo доступа!"
    print_status "Добавьте пользователя в группу sudo:"
    print_status "  usermod -aG sudo $USER"
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
    sudo apt install -y curl wget git nano htop unzip software-properties-common
elif check_command yum; then
    sudo yum update -y
    sudo yum install -y curl wget git nano htop unzip
elif check_command dnf; then
    sudo dnf update -y
    sudo dnf install -y curl wget git nano htop unzip
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
elif check_command firewall-cmd; then
    sudo firewall-cmd --permanent --add-service=ssh
    sudo firewall-cmd --permanent --add-port=80/tcp
    sudo firewall-cmd --permanent --add-port=443/tcp
    sudo firewall-cmd --permanent --add-port=8000/tcp
    sudo firewall-cmd --reload
fi

# 6. Проверка, что мы находимся в директории проекта
if [ ! -f "docker-compose.production.yml" ] || [ ! -f ".env.production.example" ]; then
    print_error "Скрипт должен запускаться из корневой директории проекта!"
    print_status "Убедитесь, что вы находитесь в папке с файлами docker-compose.production.yml и .env.production.example"
    print_status "Например: cd ~/co-work_spa && ./scripts/setup-production.sh"
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

# 9. Настройка переменных окружения
if [ ! -f ".env.production" ]; then
    print_status "Создание файла конфигурации..."
    if [ -f ".env.production.example" ]; then
        cp .env.production.example .env.production
    else
        print_error "Файл .env.production.example не найден!"
        exit 1
    fi
    
    # Запрос домена
    echo ""
    print_status "Настройка SSL сертификата..."
    read -p "Введите ваш домен (например: example.com): " DOMAIN_NAME
    read -p "Введите email для Let's Encrypt уведомлений: " SSL_EMAIL
    
    if [ -n "$DOMAIN_NAME" ] && [ -n "$SSL_EMAIL" ]; then
        sed -i "s/your-domain.com/$DOMAIN_NAME/g" .env.production
        sed -i "s/your-email@example.com/$SSL_EMAIL/g" .env.production
        sed -i "s|/opt/coworking|$PROJECT_DIR|g" .env.production
        print_status "Домен установлен: $DOMAIN_NAME"
        print_status "Email установлен: $SSL_EMAIL"
    else
        print_warning "Домен или email не указаны. Отредактируйте .env.production вручную."
    fi
    
    # Генерация безопасных ключей
    SECRET_KEY=$(openssl rand -hex 32)
    SECRET_JWT_KEY=$(openssl rand -hex 32)
    
    sed -i "s/your-super-secret-key-here/$SECRET_KEY/g" .env.production
    sed -i "s/your-jwt-secret-key-here/$SECRET_JWT_KEY/g" .env.production
    
    print_status "Секретные ключи сгенерированы и установлены"
    
    print_warning "ВАЖНО! Отредактируйте .env.production файл и укажите:"
    print_warning "- BOT_TOKEN (получите у @BotFather)"
    print_warning "- ADMIN_TELEGRAM_ID (узнайте у @userinfobot)" 
    print_warning "- ADMIN_PASSWORD (установите надежный пароль)"
    print_warning "- Другие необходимые API ключи"
else
    print_status "Файл .env.production уже существует"
fi

# 10. Создание скриптов управления
print_status "Создание скриптов управления..."

# Скрипт проверки статуса
cat > check-status.sh << 'EOF'
#!/bin/bash
echo "🏥 Статус сервисов:"
docker-compose -f docker-compose.production.yml --env-file .env.production ps

echo -e "\n📊 Использование ресурсов:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo -e "\n🔍 Последние логи (ERROR/CRITICAL):"
docker-compose -f docker-compose.production.yml --env-file .env.production logs --tail=20 | grep -E "(ERROR|CRITICAL)" || echo "Ошибок не найдено"

echo -e "\n🌐 Проверка доступности:"
curl -s -o /dev/null -w "API Health: %{http_code}\n" http://localhost:8000/ || echo "API недоступен"
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost/ || echo "Frontend недоступен"

# Проверка SSL сертификата если есть домен
if [ -f ".env.production" ]; then
    DOMAIN=$(grep "DOMAIN_NAME=" .env.production | cut -d'=' -f2)
    if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "your-domain.com" ]; then
        echo -e "\n🔒 Проверка SSL сертификата:"
        curl -s -o /dev/null -w "HTTPS Status: %{http_code}\n" https://$DOMAIN || echo "HTTPS недоступен"
        echo "SSL cert expires: $(openssl s_client -servername $DOMAIN -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d'=' -f2 || echo 'Не удается проверить')"
    fi
fi
EOF

chmod +x check-status.sh

# Скрипт бэкапа
cat > backup-system.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="\$PROJECT_DIR/backups"
DATE=$(date +"%Y%m%d_%H%M%S")

mkdir -p $BACKUP_DIR

echo "📦 Создание бэкапа системы..."

# Бэкап конфигурации
cp .env $BACKUP_DIR/env_backup_$DATE

# Архивация данных
tar -czf $BACKUP_DIR/data_backup_$DATE.tar.gz \
    data/ logs/ config/ \
    --exclude='*.log' \
    --exclude='logs/app.log.*' 2>/dev/null || true

# Бэкап базы данных через контейнер
docker-compose -f docker-compose.production.yml --env-file .env.production exec -T web python -c "
import sys
sys.path.append('/app')
try:
    from utils.backup_manager import create_backup
    import asyncio
    asyncio.run(create_backup())
    print('✅ Бэкап базы данных создан')
except Exception as e:
    print(f'❌ Ошибка бэкапа БД: {e}')
" 2>/dev/null || echo "⚠️ Бэкап БД пропущен (контейнер не запущен)"

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*_backup_*.tar.gz" -mtime +30 -delete 2>/dev/null || true

echo "✅ Бэкап завершен: $BACKUP_DIR/data_backup_$DATE.tar.gz"
ls -lh $BACKUP_DIR/data_backup_$DATE.tar.gz 2>/dev/null || true
EOF

chmod +x backup-system.sh

# Скрипт обновления
cat > update-system.sh << 'EOF'
#!/bin/bash
echo "🔄 Начинаем обновление системы..."

# Создание бэкапа перед обновлением
echo "📦 Создание бэкапа..."
./backup-system.sh

# Остановка сервисов
echo "⏹️ Остановка сервисов..."
docker-compose -f docker-compose.production.yml --env-file .env.production down

# Получение обновлений
echo "⬇️ Загрузка обновлений..."
git stash push -m "Pre-update stash $(date)"
git pull origin main
git stash pop || echo "⚠️ Конфликты при восстановлении изменений"

# Пересборка и перезапуск
echo "🔨 Пересборка образов..."
docker-compose -f docker-compose.production.yml --env-file .env.production build --no-cache

echo "🚀 Запуск сервисов..."
docker-compose -f docker-compose.production.yml --env-file .env.production up -d

# Проверка статуса
echo "⏱️ Ожидание запуска сервисов..."
sleep 15
./check-status.sh

echo "✅ Обновление завершено!"
EOF

chmod +x update-system.sh

# Скрипты быстрого запуска/остановки
cat > start.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск Coworking Management System..."
docker-compose -f docker-compose.production.yml --env-file .env.production up -d
echo "⏱️ Ожидание запуска сервисов..."
sleep 10
./check-status.sh
EOF

cat > stop.sh << 'EOF'
#!/bin/bash
echo "⏹️ Остановка Coworking Management System..."
docker-compose -f docker-compose.production.yml --env-file .env.production down
echo "✅ Сервисы остановлены"
EOF

cat > restart.sh << 'EOF'
#!/bin/bash
echo "🔄 Перезапуск Coworking Management System..."
./stop.sh
sleep 5
./start.sh
EOF

cat > logs.sh << 'EOF'
#!/bin/bash
if [ "$1" = "" ]; then
    echo "📋 Все логи:"
    docker-compose -f docker-compose.production.yml --env-file .env.production logs -f
else
    echo "📋 Логи сервиса $1:"
    docker-compose -f docker-compose.production.yml --env-file .env.production logs -f $1
fi
EOF

chmod +x start.sh stop.sh restart.sh logs.sh

# 11. Создание systemd сервиса
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
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml --env-file .env.production up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml --env-file .env.production down
TimeoutStartSec=0
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable coworking.service

# 12. Настройка автоматических бэкапов
print_status "Настройка автоматических бэкапов..."
(crontab -l 2>/dev/null | grep -v "backup-system.sh"; echo "0 2 * * * $PROJECT_DIR/backup-system.sh >> $PROJECT_DIR/logs/backup.log 2>&1") | crontab - || true

# 13. Финальная проверка
print_status "Проверка настройки Docker группы..."
if groups $USER | grep -q docker; then
    print_status "✅ Пользователь $USER добавлен в группу docker"
else
    print_warning "⚠️ Пользователь $USER НЕ в группе docker. Требуется перелогиниться!"
fi

# Завершение
echo ""
print_status "🎉 Настройка сервера завершена!"
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ:"
echo "1. Отредактируйте файл .env.production:"
echo "   nano .env.production"
echo ""
echo "2. Обязательно укажите в .env.production:"
echo "   - BOT_TOKEN=ваш_токен_бота"
echo "   - ADMIN_TELEGRAM_ID=ваш_telegram_id"
echo "   - ADMIN_PASSWORD=надежный_пароль"
echo ""
echo "3. Получите SSL сертификаты (если используете домен):"
echo "   ./setup-ssl.sh"
echo ""
echo "4. Запустите систему:"
echo "   docker-compose -f docker-compose.production.yml --env-file .env.production up -d"
echo ""
echo "5. Проверьте статус:"
echo "   ./check-status.sh"
echo ""
echo "📁 Полезные команды:"
echo "   ./start.sh            - запуск системы"
echo "   ./stop.sh             - остановка системы"
echo "   ./restart.sh          - перезапуск системы"
echo "   ./check-status.sh     - проверка статуса"
echo "   ./logs.sh [service]   - просмотр логов"
echo "   ./backup-system.sh    - создание бэкапа"
echo "   ./update-system.sh    - обновление системы"
echo ""
print_status "🌐 После запуска система будет доступна на:"

# Определяем URL на основе настроек
if [ -f ".env.production" ] && grep -q "DOMAIN_NAME=" .env.production; then
    DOMAIN=$(grep "DOMAIN_NAME=" .env.production | cut -d'=' -f2)
    if [ -n "$DOMAIN" ] && [ "$DOMAIN" != "your-domain.com" ]; then
        echo "   Frontend: https://$DOMAIN"
        echo "   API: https://$DOMAIN/api"
        echo "   Docs: https://$DOMAIN/docs"
        echo ""
        print_warning "Не забудьте получить SSL сертификат: ./setup-ssl.sh"
    else
        if [ -n "$EXTERNAL_IP" ]; then
            echo "   Frontend: http://$EXTERNAL_IP"
            echo "   API: http://$EXTERNAL_IP:8000"
            echo "   Docs: http://$EXTERNAL_IP:8000/docs"
        else
            echo "   Frontend: http://your_server_ip"
            echo "   API: http://your_server_ip:8000"
            echo "   Docs: http://your_server_ip:8000/docs"
        fi
    fi
else
    if [ -n "$EXTERNAL_IP" ]; then
        echo "   Frontend: http://$EXTERNAL_IP"
        echo "   API: http://$EXTERNAL_IP:8000"
        echo "   Docs: http://$EXTERNAL_IP:8000/docs"
    else
        echo "   Frontend: http://your_server_ip"
        echo "   API: http://your_server_ip:8000"
        echo "   Docs: http://your_server_ip:8000/docs"
    fi
fi
echo ""
print_warning "⚠️ Если добавлен в группу docker - ПЕРЕЛОГИНЬТЕСЬ для применения изменений!"
echo ""
print_status "✨ Удачного деплоя!"