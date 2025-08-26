# 🚀 ПОЛНОЕ РУКОВОДСТВО ПО РАЗВЕРТЫВАНИЮ НА PRODUCTION СЕРВЕРЕ

## 📋 Содержание
- [Подготовка сервера](#-подготовка-сервера)
- [Установка зависимостей](#-установка-зависимостей)
- [Настройка проекта](#-настройка-проекта)
- [Развертывание приложения](#-развертывание-приложения)
- [Настройка HTTPS](#-настройка-https)
- [Мониторинг и обслуживание](#-мониторинг-и-обслуживание)
- [Решение проблем](#-решение-проблем)

---

## 🖥️ Подготовка сервера

### Системные требования
- **ОС**: Ubuntu 20.04+ / CentOS 8+ / Debian 11+
- **RAM**: минимум 2GB, рекомендуется 4GB+
- **CPU**: 2+ ядра
- **Диск**: минимум 20GB свободного места
- **Сеть**: статический IP-адрес

### 1️⃣ Обновление системы

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
# или для новых версий
sudo dnf update -y
```

### 2️⃣ Установка базовых пакетов

```bash
# Ubuntu/Debian
sudo apt install -y curl wget git nano htop unzip software-properties-common

# CentOS/RHEL
sudo yum install -y curl wget git nano htop unzip
```

### 3️⃣ Настройка firewall

```bash
# UFW (Ubuntu)
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp
sudo ufw --force enable

# firewalld (CentOS)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

---

## 📦 Установка зависимостей

### 1️⃣ Установка Docker

```bash
# Удаление старых версий
sudo apt remove docker docker-engine docker.io containerd runc

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Проверка установки
docker --version
```

### 2️⃣ Установка Docker Compose

```bash
# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker-compose --version
```

### 3️⃣ Настройка Docker для production

```bash
# Создание конфигурации Docker daemon
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "storage-driver": "overlay2"
}
EOF

# Перезапуск Docker
sudo systemctl restart docker
sudo systemctl enable docker
```

---

## ⚙️ Настройка проекта

### 1️⃣ Клонирование репозитория

```bash
# Создание директории для проекта
sudo mkdir -p /opt/coworking
sudo chown $USER:$USER /opt/coworking
cd /opt/coworking

# Клонирование проекта
git clone https://github.com/beerhunters/co-work_spa.git .

# Установка прав доступа
sudo chown -R $USER:$USER /opt/coworking
chmod -R 755 /opt/coworking
```

### 2️⃣ Настройка переменных окружения

```bash
# Копирование production конфигурации
cp .env.production .env

# Редактирование конфигурации
nano .env
```

**🚨 ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ следующие значения в .env:**

```bash
# Замените YOUR_SERVER_IP на ваш реальный IP адрес
YOUR_SERVER_IP=123.456.789.100  # Ваш реальный IP

# Генерация безопасных ключей
SECRET_KEY=$(openssl rand -hex 32)
SECRET_KEY_JWT=$(openssl rand -hex 32)

# Установите надежный пароль администратора
ADMIN_PASSWORD=your_super_secure_password_here

# Ваш Telegram Bot Token (получить у @BotFather)
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# ID вашего Telegram аккаунта (узнать у @userinfobot)
ADMIN_TELEGRAM_ID=123456789
```

### 3️⃣ Автоматическая настройка IP адреса

Создайте скрипт для автоматической настройки IP:

```bash
# Создание скрипта настройки
cat > setup-ip.sh << 'EOF'
#!/bin/bash

# Получение внешнего IP автоматически
EXTERNAL_IP=$(curl -s ifconfig.me)
echo "🌐 Обнаружен внешний IP: $EXTERNAL_IP"

# Замена в .env файле
sed -i "s/YOUR_SERVER_IP/$EXTERNAL_IP/g" .env

echo "✅ IP адрес обновлен в конфигурации"
echo "📋 Проверьте настройки:"
grep -E "(API_BASE_URL|FRONTEND_URL|CORS_ORIGINS)" .env
EOF

chmod +x setup-ip.sh
./setup-ip.sh
```

### 4️⃣ Создание необходимых директорий

```bash
# Создание директорий для данных
mkdir -p data avatars ticket_photos newsletter_photos logs config

# Установка прав доступа
chmod -R 755 data avatars ticket_photos newsletter_photos logs config
```

---

## 🚀 Развертывание приложения

### 1️⃣ Сборка и запуск

```bash
# Сборка образов для production
docker-compose -f docker-compose.production.yml build --no-cache

# Запуск сервисов
docker-compose -f docker-compose.production.yml up -d

# Проверка статуса
docker-compose -f docker-compose.production.yml ps
```

### 2️⃣ Проверка работоспособности

```bash
# Проверка логов
docker-compose -f docker-compose.production.yml logs -f --tail=50

# Проверка API
curl http://localhost:8000/
curl http://localhost:8000/health

# Проверка frontend
curl http://localhost/
```

### 3️⃣ Настройка автозапуска

```bash
# Создание systemd сервиса
sudo tee /etc/systemd/system/coworking.service > /dev/null <<EOF
[Unit]
Description=Coworking Management System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/coworking
ExecStart=/usr/local/bin/docker-compose -f docker-compose.production.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.production.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Активация сервиса
sudo systemctl daemon-reload
sudo systemctl enable coworking.service
sudo systemctl start coworking.service
```

---

## 🔒 Настройка HTTPS (рекомендуется)

### 1️⃣ Установка Nginx

```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y
```

### 2️⃣ Настройка Nginx

```bash
# Создание конфигурации
sudo tee /etc/nginx/sites-available/coworking > /dev/null <<EOF
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Увеличение лимитов для загрузки файлов
    client_max_body_size 20M;

    # Frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Статические файлы
    location /avatars/ {
        proxy_pass http://localhost:8000/avatars/;
    }
    
    location /ticket_photos/ {
        proxy_pass http://localhost:8000/ticket_photos/;
    }
}
EOF

# Активация конфигурации
sudo ln -s /etc/nginx/sites-available/coworking /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 3️⃣ Установка SSL сертификата (Let's Encrypt)

```bash
# Установка Certbot
sudo apt install snapd -y
sudo snap install core; sudo snap refresh core
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot

# Получение сертификата
sudo certbot --nginx -d YOUR_DOMAIN

# Автоматическое обновление
sudo systemctl enable --now snap.certbot.renew.timer
```

---

## 📊 Мониторинг и обслуживание

### 1️⃣ Создание скриптов мониторинга

```bash
# Скрипт проверки статуса
cat > check-status.sh << 'EOF'
#!/bin/bash
echo "🏥 Статус сервисов:"
docker-compose -f docker-compose.production.yml ps

echo -e "\n📊 Использование ресурсов:"
docker stats --no-stream

echo -e "\n🔍 Последние логи (ERROR/CRITICAL):"
docker-compose -f docker-compose.production.yml logs --tail=20 | grep -E "(ERROR|CRITICAL)"
EOF

chmod +x check-status.sh
```

### 2️⃣ Автоматические бэкапы

```bash
# Скрипт бэкапа
cat > backup-system.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/coworking/backups"
DATE=$(date +"%Y%m%d_%H%M%S")

mkdir -p $BACKUP_DIR

echo "📦 Создание бэкапа системы..."

# Бэкап базы данных
docker-compose -f docker-compose.production.yml exec -T web python -c "
from utils.backup_manager import create_backup
import asyncio
asyncio.run(create_backup())
"

# Архивация данных
tar -czf $BACKUP_DIR/data_backup_$DATE.tar.gz data/ logs/ config/

# Удаление старых бэкапов (старше 30 дней)
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "✅ Бэкап завершен: $BACKUP_DIR/data_backup_$DATE.tar.gz"
EOF

chmod +x backup-system.sh

# Добавление в cron (ежедневно в 2:00)
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/coworking/backup-system.sh") | crontab -
```

### 3️⃣ Скрипт обновления

```bash
# Скрипт обновления системы
cat > update-system.sh << 'EOF'
#!/bin/bash
echo "🔄 Начинаем обновление системы..."

# Создание бэкапа перед обновлением
./backup-system.sh

# Получение обновлений
git stash
git pull origin main
git stash pop

# Пересборка и перезапуск
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d

# Проверка статуса
sleep 10
./check-status.sh

echo "✅ Обновление завершено!"
EOF

chmod +x update-system.sh
```

### 4️⃣ Мониторинг логов

```bash
# Просмотр логов в реальном времени
docker-compose -f docker-compose.production.yml logs -f

# Фильтрация по сервисам
docker-compose -f docker-compose.production.yml logs -f web
docker-compose -f docker-compose.production.yml logs -f bot

# Поиск ошибок
docker-compose -f docker-compose.production.yml logs | grep -i error
```

---

## 🔧 Решение проблем

### Частые проблемы и решения

#### 1️⃣ Сервис не запускается

```bash
# Проверка логов
docker-compose -f docker-compose.production.yml logs [service_name]

# Перезапуск сервиса
docker-compose -f docker-compose.production.yml restart [service_name]

# Полная пересборка
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

#### 2️⃣ Проблемы с доступом к API

```bash
# Проверка портов
sudo netstat -tlnp | grep :8000

# Проверка firewall
sudo ufw status

# Тест подключения
curl -I http://localhost:8000/health
```

#### 3️⃣ Нехватка места на диске

```bash
# Очистка Docker образов
docker system prune -af

# Ротация логов
docker-compose -f docker-compose.production.yml exec web python -c "
import os
from pathlib import Path
logs_dir = Path('/app/logs')
for log_file in logs_dir.glob('*.log*'):
    if log_file.stat().st_size > 100*1024*1024:  # 100MB
        log_file.unlink()
"
```

#### 4️⃣ Высокая нагрузка на CPU/память

```bash
# Проверка ресурсов
docker stats

# Ограничение ресурсов в docker-compose.production.yml
# (уже настроено в файле)

# Мониторинг процессов
htop
```

### 📞 Получение поддержки

Если возникли проблемы:

1. **Проверьте логи**: `docker-compose logs`
2. **Запустите диагностику**: `./check-status.sh`
3. **Создайте issue**: [GitHub Issues](https://github.com/beerhunters/co-work_spa/issues)
4. **Напишите разработчику**: [@beerhunters](https://t.me/beerhunters)

---

## ✅ Чеклист успешного деплоя

- [ ] Сервер подготовлен и обновлен
- [ ] Docker и Docker Compose установлены
- [ ] Репозиторий склонирован в `/opt/coworking`
- [ ] Файл `.env` настроен с вашим IP адресом
- [ ] Скрипт `setup-ip.sh` выполнен
- [ ] Сервисы запущены через `docker-compose.production.yml`
- [ ] API отвечает на `http://YOUR_IP:8000/health`
- [ ] Frontend доступен на `http://YOUR_IP`
- [ ] Firewall настроен (порты 80, 443, 8000)
- [ ] Systemd сервис создан и запущен
- [ ] Nginx установлен и настроен (опционально)
- [ ] SSL сертификат получен (опционально)
- [ ] Бэкапы настроены и работают
- [ ] Мониторинг логов настроен

---

## 🎯 Доступ к системе

После успешного деплоя система будет доступна:

- **🌐 Веб-админка**: `http://YOUR_SERVER_IP` (или `https://YOUR_DOMAIN`)
- **📊 API Документация**: `http://YOUR_SERVER_IP:8000/docs`
- **🏥 Health Check**: `http://YOUR_SERVER_IP:8000/health`
- **🤖 Telegram Бот**: `https://t.me/your_bot_username`

**Данные для входа:**
- Логин: `admin` (или как указано в `ADMIN_LOGIN`)
- Пароль: как указано в `ADMIN_PASSWORD`

---

<div align="center">

**🚀 Поздравляем! Система успешно развернута на production сервере!**

*Не забудьте поставить ⭐ проекту на GitHub!*

</div>