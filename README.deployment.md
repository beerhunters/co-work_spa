# Деплоймент Coworking Management System

## Архитектура

Система использует единый `docker-compose.yml` с переменными окружения для разных режимов развертывания:
- **Локальный режим** - для разработки с localhost
- **Продакшн режим** - для сервера с SSL от Let's Encrypt

## Компоненты

- **Web API** - FastAPI backend
- **Bot** - Telegram бот  
- **Frontend** - React приложение с Nginx
- **Redis** - Кэширование и сессии
- **Certbot** - Автообновление SSL сертификатов (только продакшн)

## Быстрый старт

### Локальная разработка

```bash
# Запуск локального режима
./start-local.sh

# Доступные URL:
# http://localhost - Frontend
# http://localhost:8000/api - API
# http://localhost:8000/docs - API документация
```

### Продакшн развертывание

```bash
# Настройка домена в .env
echo "DOMAIN_NAME=your-domain.com" >> .env

# Запуск продакшн режима
./start-prod.sh

# Доступные URL:
# https://your-domain.com - Frontend  
# https://your-domain.com/api - API
# https://your-domain.com/docs - API документация
```

## Управляющие скрипты

| Скрипт | Описание |
|--------|----------|
| `start-local.sh` | Запуск локального режима разработки |
| `start-prod.sh` | Запуск продакшн режима с SSL |
| `stop.sh` | Остановка всех сервисов |
| `restart.sh` | Перезапуск сервисов |
| `status.sh` | Проверка статуса сервисов |
| `logs.sh` | Просмотр логов |
| `cleanup.sh` | Очистка системы |

## Настройка сервера

### 1. Создание пользователя (НЕ root)

```bash
# Создание пользователя
sudo adduser coworking

# Добавление в группы
sudo usermod -aG sudo coworking
sudo usermod -aG docker coworking

# Переключение на пользователя
su - coworking
```

### 2. Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo systemctl enable docker
sudo systemctl start docker

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

### 3. Настройка Docker

```bash
# Docker login
docker login

# Настройка DNS в Docker (опционально)
sudo mkdir -p /etc/docker
echo '{
  "dns": ["8.8.8.8", "8.8.4.4"]
}' | sudo tee /etc/docker/daemon.json

sudo systemctl restart docker
```

### 4. Клонирование и настройка проекта

```bash
# Клонирование репозитория
git clone <your-repo-url> coworking
cd coworking

# Настройка .env
cp .env .env.backup
nano .env  # Установите DOMAIN_NAME и другие параметры

# Установка прав на скрипты
chmod +x *.sh
```

### 5. Настройка SSL сертификатов

```bash
# Настройка Let's Encrypt
./setup-ssl.sh

# Или запуск без SSL (для тестирования)
./start-prod.sh  # Выберите 'y' при вопросе о запуске без SSL
```

## Переменные окружения

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

# SSL пути
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

## Управление сервисами

### Просмотр статуса

```bash
./status.sh                    # Общий статус
docker-compose ps              # Статус контейнеров
docker-compose logs -f web     # Логи API в реальном времени
```

### Просмотр логов

```bash
./logs.sh                      # Все логи
./logs.sh web                  # Логи API
./logs.sh bot follow          # Логи бота в реальном времени
./logs.sh frontend follow     # Логи фронтенда в реальном времени
```

### Управление

```bash
./restart.sh                  # Перезапуск
./stop.sh                     # Остановка
./cleanup.sh                  # Полная очистка
```

## Мониторинг

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

### SSL сертификаты

```bash
# Проверка срока действия
openssl x509 -enddate -noout -in /etc/letsencrypt/live/your-domain.com/cert.pem

# Обновление сертификатов (автоматически через certbot)
docker-compose logs certbot
```

## Обновление

```bash
# Остановка сервисов
./stop.sh

# Обновление кода
git pull

# Пересборка и запуск
./start-prod.sh    # или ./start-local.sh
```

## Резервное копирование

```bash
# Создание резервной копии данных
tar -czf backup-$(date +%Y%m%d).tar.gz data/ avatars/ ticket_photos/ newsletter_photos/ config/

# Резервная копия базы данных (если используется внешняя БД)
# mysqldump или pg_dump команды
```

## Решение проблем

### Проблемы с SSL

```bash
# Проверка сертификатов
ls -la /etc/letsencrypt/live/your-domain.com/

# Проверка логов certbot
./logs.sh certbot

# Принудительное обновление SSL
./setup-ssl.sh
```

### Проблемы с Docker

```bash
# Очистка Docker
./cleanup.sh

# Проверка ресурсов
docker system df

# Перезапуск Docker
sudo systemctl restart docker
```

### Проблемы с переменными окружения

```bash
# Проверка переменных
./status.sh

# Проверка .env файла
cat .env

# Пересборка с чистыми параметрами
./stop.sh && ./start-prod.sh
```