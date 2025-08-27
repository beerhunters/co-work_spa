# Руководство по развертыванию

Этот проект поддерживает два варианта развертывания:
1. **Локальная разработка** - для разработки на localhost
2. **Продакшн сервер** - с SSL сертификатами Let's Encrypt

## ⚡ Быстрый старт для продакшена

```bash
# 1. Создаем пользователя (если root)
adduser coworking
usermod -aG sudo coworking
su - coworking

# 2. Клонируем и устанавливаем
git clone https://github.com/your-repo/co-work_spa.git
cd co-work_spa
chmod +x scripts/setup-production.sh
./scripts/setup-production.sh

# 3. Настраиваем (заполняем BOT_TOKEN, ADMIN_TELEGRAM_ID, etc.)
nano .env.production

# 4. Получаем SSL (если есть домен)
./setup-ssl.sh

# 5. Запускаем
./start.sh
```

## 🔧 Локальная разработка (localhost)

### Быстрый старт

1. **Копируем переменные окружения:**
   ```bash
   cp .env.local.example .env.local
   ```

2. **Редактируем `.env.local`** и заполняем необходимые значения (особенно Telegram Bot токены)

3. **Запускаем сервисы:**
   ```bash
   # Быстрый способ
   ./start-local.sh
   
   # Или вручную
   docker-compose -f docker-compose.local.yml --env-file .env.local up -d
   ```

4. **Проверяем статус:**
   ```bash
   ./status-local.sh
   ```

### Доступные URL в локальном режиме:
- **Фронтенд:** http://localhost
- **API:** http://localhost:8000/api
- **Документация API:** http://localhost:8000/docs
- **Redis:** localhost:6379

### Управление локальной средой:
```bash
# Остановка
./stop-local.sh

# Перезапуск
./restart-local.sh

# Просмотр логов всех сервисов
./logs-local.sh

# Просмотр логов конкретного сервиса
./logs-local.sh web
./logs-local.sh bot
./logs-local.sh frontend

# Проверка статуса
./status-local.sh
```

---

## 🌐 Продакшн сервер с SSL

### Предварительные требования

1. **Сервер с Ubuntu/Debian** с публичным IP
2. **Домен**, направленный на IP сервера (опционально для SSL)
3. **Открытые порты:** 22 (SSH), 80 (HTTP), 443 (HTTPS)

### Подготовка сервера

#### Создание пользователя (если используете root)

```bash
# Подключаемся к серверу как root
ssh root@your-server-ip

# Создаем нового пользователя
adduser coworking

# Добавляем пользователя в группу sudo
usermod -aG sudo coworking

# Переключаемся на нового пользователя
su - coworking

# Или сразу подключаемся под новым пользователем
ssh coworking@your-server-ip
```

#### Настройка SSH ключей (рекомендуется)

```bash
# На вашем локальном компьютере создаем SSH ключ (если нет)
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"

# Копируем публичный ключ на сервер
ssh-copy-id coworking@your-server-ip

# Или вручную:
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# Вставьте содержимое вашего ~/.ssh/id_rsa.pub

# Устанавливаем правильные права
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

#### Базовая настройка безопасности

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем базовые пакеты
sudo apt install -y curl wget git nano htop unzip fail2ban

# Настраиваем fail2ban для защиты SSH
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Опционально: изменяем SSH порт (в /etc/ssh/sshd_config)
# sudo nano /etc/ssh/sshd_config
# Port 2222
# PermitRootLogin no
# sudo systemctl restart ssh
```

#### Настройка Docker

```bash
# Установка Docker (если не установлен)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Настройка Docker daemon с DNS
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

# Перезапуск Docker для применения настроек
sudo systemctl restart docker
sudo systemctl enable docker

# Логин в Docker Hub (если нужно)
docker login
```

⚠️ **Важно**: После добавления пользователя в группу docker необходимо перелогиниться!

### Автоматическое развертывание

#### Вариант 1: Полная автоматическая установка

1. **Скачиваем и запускаем setup скрипт:**
   ```bash
   # Клонируем репозиторий
   git clone https://github.com/your-repo/co-work_spa.git
   cd co-work_spa
   
   # Запускаем автоматическую установку
   chmod +x scripts/setup-production.sh
   ./scripts/setup-production.sh
   ```
   
   Скрипт автоматически:
   - Проверит права пользователя (не должен быть root)
   - Установит Docker и Docker Compose
   - Добавит пользователя в группу docker
   - Настроит firewall
   - Создаст директории
   - Сгенерирует безопасные ключи
   - Создаст служебные скрипты
   - Настроит автозапуск

2. **Заполняем конфигурацию:**
   ```bash
   nano .env.production
   ```
   Обязательно укажите:
   - `BOT_TOKEN` - токен Telegram бота
   - `ADMIN_TELEGRAM_ID` - ваш Telegram ID
   - `ADMIN_PASSWORD` - пароль администратора

3. **Получаем SSL (если используете домен):**
   ```bash
   ./setup-ssl.sh
   ```

4. **Перелогиниваемся (если требуется):**
   ```bash
   # Если скрипт сообщил о добавлении в группу docker
   exit
   ssh coworking@your-server-ip
   cd co-work_spa
   ```

5. **Запускаем систему:**
   ```bash
   ./start.sh
   ```

#### Вариант 2: Ручная установка

1. **Подготовка переменных окружения:**
   ```bash
   cp .env.production.example .env.production
   nano .env.production
   ```

2. **Получение SSL сертификата:**
   ```bash
   ./setup-ssl.sh
   ```

3. **Запуск сервисов:**
   ```bash
   docker-compose -f docker-compose.production.yml --env-file .env.production up -d
   ```

#### Шаг 4: Проверка

```bash
# Проверяем статус контейнеров
docker-compose -f docker-compose.production.yml ps

# Проверяем логи
docker-compose -f docker-compose.production.yml logs -f

# Проверяем SSL сертификат
curl -I https://your-domain.com
```

### Доступные URL в продакшене:
- **Фронтенд:** https://your-domain.com
- **API:** https://your-domain.com/api
- **Документация API:** https://your-domain.com/docs

---

## 🔄 Управление и обслуживание

### Команды быстрого управления (создаются автоматически при установке):

```bash
# Запуск системы
./start.sh

# Остановка системы  
./stop.sh

# Перезапуск системы
./restart.sh

# Проверка статуса
./check-status.sh

# Просмотр логов всех сервисов
./logs.sh

# Просмотр логов конкретного сервиса
./logs.sh web
./logs.sh bot
./logs.sh frontend

# Создание резервной копии
./backup-system.sh

# Обновление системы
./update-system.sh
```

⚠️ **Примечание**: Эти скрипты создаются автоматически при запуске `setup-production.sh`

### Ручное управление:
```bash
# Обновление кода в продакшене
docker-compose -f docker-compose.production.yml --env-file .env.production down
git pull origin main
docker-compose -f docker-compose.production.yml --env-file .env.production up -d --build

# Просмотр логов
docker-compose -f docker-compose.production.yml --env-file .env.production logs -f

# Резервное копирование
docker-compose -f docker-compose.production.yml --env-file .env.production exec web python -c "from utils.backup_manager import BackupManager; BackupManager().create_backup()"
```

### Обновление SSL сертификатов:
SSL сертификаты обновляются автоматически через контейнер `certbot`. 
Для ручного обновления:
```bash
docker-compose -f docker-compose.production.yml exec certbot certbot renew
```

---

## 🛠 Структура файлов

```
├── docker-compose.local.yml      # Локальная разработка
├── docker-compose.production.yml # Продакшн сервер  
├── nginx.local.conf             # Nginx для localhost
├── nginx.production.conf        # Nginx с SSL для продакшена
├── .env.local.example           # Пример переменных для локальной разработки
├── .env.production.example      # Пример переменных для продакшена
├── setup-ssl.sh                 # Скрипт получения SSL сертификата
├── scripts/
│   └── setup-production.sh      # Автоматическая установка продакшена
│
├── # Скрипты для локальной разработки (готовые)
├── start-local.sh               # Запуск локальной среды
├── stop-local.sh                # Остановка локальной среды
├── restart-local.sh             # Перезапуск локальной среды
├── logs-local.sh                # Логи локальной среды
├── status-local.sh              # Статус локальной среды
│
├── # Скрипты для продакшена (создаются автоматически)
├── start.sh                     # Быстрый запуск системы
├── stop.sh                      # Быстрая остановка системы
├── restart.sh                   # Перезапуск системы
├── check-status.sh              # Проверка статуса
├── logs.sh                      # Просмотр логов
├── backup-system.sh             # Резервное копирование
├── update-system.sh             # Обновление системы
│
└── DEPLOYMENT.md               # Это руководство
```

---

## ⚠️ Важные замечания

1. **Безопасность:** Никогда не коммитьте файлы `.env.production` и `.env.local` в репозиторий
2. **SSL:** Первое получение SSL сертификата требует остановленных сервисов на 80 порту
3. **Домен:** Убедитесь, что домен корректно указывает на IP сервера перед получением SSL
4. **Файрвол:** Откройте порты 80 и 443 в файрволе сервера
5. **Ресурсы:** Убедитесь, что у сервера достаточно RAM (рекомендуется минимум 2GB)
6. **Docker:** После добавления в группу docker обязательно перелогиньтесь
7. **DNS:** Настройка DNS в daemon.json помогает избежать проблем с разрешением имен
8. **Docker Hub:** Если используете приватные репозитории, выполните `docker login`

---

## 🐛 Устранение проблем

### Проблема: Permission denied при работе с Docker
```bash
# Проверяем, в группе ли docker пользователь
groups $USER

# Если нет docker в группах, добавляем
sudo usermod -aG docker $USER

# Перелогиниваемся
exit
ssh user@server
```

### Проблема: "sudo: command not found" или нет sudo прав
```bash
# Подключаемся как root
ssh root@server

# Добавляем пользователя в sudo группу  
usermod -aG sudo username

# Или редактируем sudoers файл
visudo
# Добавляем: username ALL=(ALL:ALL) ALL
```

### Проблема: SSH подключение отклоняется
```bash
# Проверяем статус SSH
sudo systemctl status ssh

# Перезапускаем SSH
sudo systemctl restart ssh

# Проверяем конфигурацию
sudo nano /etc/ssh/sshd_config
```

### Проблема: SSL сертификат не получается
- Проверьте, что домен указывает на правильный IP
- Убедитесь, что порт 80 открыт и доступен
- Остановите все другие веб-сервисы на порту 80

### Проблема: Контейнеры не стартуют
- Проверьте логи: `./logs.sh`
- Убедитесь, что все переменные окружения заполнены
- Проверьте наличие свободного места на диске
- Проверьте права доступа: `ls -la data/ logs/`

### Проблема: API недоступен
- Проверьте статус контейнера: `./check-status.sh`
- Проверьте логи API: `./logs.sh web`  
- Убедитесь, что база данных создана и мигрирована

### Проблема: Firewall блокирует подключения
```bash
# Для UFW
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Для firewall-cmd  
sudo firewall-cmd --list-all
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

### Проблема: Docker не может резолвить DNS
```bash
# Проверяем текущую конфигурацию
cat /etc/docker/daemon.json

# Добавляем DNS серверы
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "dns": ["8.8.8.8", "8.8.4.4", "1.1.1.1"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Перезапускаем Docker
sudo systemctl restart docker

# Проверяем работу
docker run --rm busybox nslookup google.com
```

### Проблема: Docker Hub недоступен
```bash
# Проверяем подключение к Docker Hub
docker pull hello-world

# Если ошибка авторизации
docker login

# Проверяем настройки proxy (если используете)
docker info | grep -i proxy
```