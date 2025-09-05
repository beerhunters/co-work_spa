# 🚀 Руководство по развертыванию Coworking Management System

## 🏗️ Архитектура развертывания

Система использует единый `docker-compose.yml` с переменными окружения для разных режимов развертывания:
- **Локальный режим** - для разработки с localhost
- **Продакшн режим** - для сервера с SSL от Let's Encrypt

### 🔧 Компоненты системы

- **Web API** - FastAPI backend с автоматическими миграциями БД
- **Bot** - Telegram бот для клиентов
- **Frontend** - React приложение с Nginx
- **Redis** - Кэширование и управление сессиями
- **Certbot** - Автообновление SSL сертификатов (только продакшн)

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
nano .env

# 4. Получаем SSL (если есть домен)
./scripts/setup-ssl.sh

# 5. Запускаем
./scripts/start-prod.sh
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
   ./scripts/start-local.sh
   
   # Или вручную
   docker-compose --env-file .env up -d
   ```

4. **Проверяем статус:**
   ```bash
   ./scripts/status.sh
   ```

### Доступные URL в локальном режиме:
- **Фронтенд:** http://localhost
- **API:** http://localhost:8000/api
- **Документация API:** http://localhost:8000/docs
- **Redis:** localhost:6379

### Управляющие скрипты

#### 🚀 Основные скрипты развертывания
| Скрипт | Описание |
|--------|----------|
| `./scripts/start-local.sh` | Запуск локального режима разработки |
| `./scripts/start-prod.sh` | Запуск продакшн режима с SSL |

#### 🔧 Скрипты управления сервисами  
| Скрипт | Описание |
|--------|----------|
| `./scripts/stop.sh` | Остановка всех сервисов |
| `./scripts/restart.sh` | Перезапуск сервисов |
| `./scripts/status.sh` | Проверка статуса сервисов |
| `./scripts/logs.sh [service] [follow]` | Просмотр логов |

#### ⚙️ Служебные скрипты
| Скрипт | Описание |
|--------|----------|
| `./scripts/setup-production.sh` | **Автоматическая настройка production сервера** |
| `./scripts/cleanup.sh` | Очистка системы и данных |
| `./scripts/setup-ssl.sh` | Настройка SSL сертификатов |

### Управление локальной средой:
```bash
# Основные команды
./scripts/start-local.sh           # Запуск для разработки
./scripts/stop.sh                  # Остановка всех сервисов
./scripts/restart.sh               # Перезапуск
./scripts/status.sh                # Проверка статуса

# Просмотр логов
./scripts/logs.sh                  # Все логи
./scripts/logs.sh web              # Логи API
./scripts/logs.sh bot follow       # Логи бота в реальном времени
./scripts/logs.sh frontend follow  # Логи фронтенда в реальном времени
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
   - Создаст директории данных в текущей папке
   - Настроит корректный путь проекта в .env.production
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
   - `DOMAIN_NAME` - ваш домен для SSL сертификатов
   
   ⚠️ **Примечание**: `COWORKING_DIR` будет автоматически установлен скриптом на текущую директорию

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
docker-compose exec certbot certbot renew

## 📊 Мониторинг и управление сервисами

### Проверка здоровья сервисов

```bash
# API
curl http://localhost:8000/     # Локально
curl https://your-domain.com/api/  # Продакшн

# Frontend
curl http://localhost/          # Локально  
curl https://your-domain.com/   # Продакшн

# Redis
docker-compose exec redis redis-cli ping
```

### Просмотр статуса и логов

```bash
# Общий статус системы
./scripts/status.sh

# Статус Docker контейнеров
docker-compose ps

# Просмотр логов
./scripts/logs.sh                  # Все логи
./scripts/logs.sh web              # Логи API
./scripts/logs.sh bot follow       # Логи бота в реальном времени
./scripts/logs.sh frontend follow  # Логи фронтенда в реальном времени
```

### Управление системой

```bash
./scripts/restart.sh              # Перезапуск
./scripts/stop.sh                 # Остановка
./scripts/cleanup.sh              # Полная очистка
```

### SSL сертификаты

```bash
# Проверка срока действия
openssl x509 -enddate -noout -in /etc/letsencrypt/live/your-domain.com/cert.pem

# Проверка логов certbot (автоматическое обновление)
./scripts/logs.sh certbot
```

---

## ⚙️ Переменные окружения

### Ключевые переменные для развертывания

```bash
# Режим сборки (устанавливается автоматически скриптами)
BUILD_TARGET=development|production
ENVIRONMENT=development|production
DEBUG=true|false

# URL конфигурация
DOMAIN_NAME=your-domain.com
API_BASE_URL_EXTERNAL=https://your-domain.com/api
FRONTEND_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com

# SSL пути (для продакшн)
SSL_CERTS_PATH=/etc/letsencrypt
SSL_WEBROOT_PATH=/var/www/certbot

# Порты
WEB_PORT=8000
FRONTEND_HTTP_PORT=80
FRONTEND_HTTPS_PORT=443
```

### Различия между локальным и продакшн режимами

| Параметр | Локальный | Продакшн |
|----------|-----------|----------|
| BUILD_TARGET | development | production |
| DEBUG | true | false |
| API_BASE_URL | http://localhost:8000/api | https://domain.com/api |
| SSL | Отключен | Включен |
| Ресурсы | Меньше | Больше |
| Логи | DEBUG, text | INFO, json |
| Certbot | Выключен | Включен |

---

## 🔄 Обновление системы

```bash
# Остановка сервисов
./scripts/stop.sh

# Обновление кода
git pull origin main

# Пересборка и запуск
./scripts/start-prod.sh    # или ./scripts/start-local.sh для локальной разработки
```

## 💾 Резервное копирование

```bash
# Создание резервной копии данных
tar -czf backup-$(date +%Y%m%d).tar.gz data/ avatars/ ticket_photos/ newsletter_photos/ config/

# Резервная копия через API (автоматическая система бэкапов)
docker-compose exec web python -m utils.backup_manager
```

## 🛠 Структура файлов

```
├── docker-compose.yml           # Единый Docker Compose файл с профилями
├── nginx.local.conf            # Nginx для localhost
├── nginx.production.conf       # Nginx с SSL для продакшена
├── .env                        # Переменные окружения
├── scripts/                    # Управляющие скрипты
│   ├── setup-production.sh     # Автоматическая установка продакшена
│   ├── setup-ssl.sh           # Настройка SSL сертификатов
│   ├── start-local.sh         # Запуск локальной среды
│   ├── start-prod.sh          # Запуск продакшн среды
│   ├── stop.sh                # Остановка всех сервисов
│   ├── restart.sh             # Перезапуск сервисов
│   ├── status.sh              # Проверка статуса
│   ├── logs.sh                # Просмотр логов
│   └── cleanup.sh             # Очистка системы
├── DEPLOYMENT.md              # Это руководство
└── README.md                  # Основная документация для GitHub
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
9. **Nginx конфиги:** Автоматически встраиваются в образы (nginx.local.conf для development, nginx.production.conf для production)
10. **DOMAIN_NAME:** Обязательно укажите в .env.production для корректной работы SSL сертификатов

---

## 🐛 Устранение проблем

### 🔧 Проблемы с SSL сертификатами

```bash
# Проверка сертификатов
ls -la /etc/letsencrypt/live/your-domain.com/

# Проверка логов certbot
./scripts/logs.sh certbot

# Принудительное обновление SSL
./scripts/setup-ssl.sh
```

### 🐳 Проблемы с Docker

```bash
# Очистка Docker системы
./scripts/cleanup.sh

# Проверка ресурсов
docker system df

# Перезапуск Docker
sudo systemctl restart docker
```

### ⚙️ Проблемы с переменными окружения

```bash
# Проверка переменных и статуса
./scripts/status.sh

# Проверка .env файла
cat .env

# Пересборка с чистыми параметрами
./scripts/stop.sh && ./scripts/start-prod.sh
```

### 🔍 Расширенная диагностика

```bash
# Проверка портов
netstat -tlnp | grep :80
netstat -tlnp | grep :443
netstat -tlnp | grep :8000

# Проверка процессов Docker
docker ps -a
docker images
docker network ls

# Проверка логов системы
journalctl -u docker --since "1 hour ago"
```

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

### Проблема: "unknown domain_name variable" в nginx
```bash
# Проверяем, что DOMAIN_NAME задан в .env.production
grep DOMAIN_NAME .env.production

# Если не задан, добавляем
echo "DOMAIN_NAME=your-domain.com" >> .env.production

# Пересобираем и перезапускаем frontend
docker-compose -f docker-compose.production.yml --env-file .env.production up -d --build frontend
```