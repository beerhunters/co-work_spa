#!/bin/bash

# Скрипт для первоначального получения SSL сертификатов Let's Encrypt
# Используйте этот скрипт ТОЛЬКО при первом развертывании

set -e

# Проверяем наличие переменных окружения
if [ -z "$DOMAIN_NAME" ] || [ -z "$SSL_EMAIL" ]; then
    echo "Ошибка: Необходимо задать переменные DOMAIN_NAME и SSL_EMAIL"
    echo "Пример: DOMAIN_NAME=example.com SSL_EMAIL=admin@example.com ./setup-ssl.sh"
    exit 1
fi

echo "Настройка SSL сертификатов для домена: $DOMAIN_NAME"
echo "Email для уведомлений: $SSL_EMAIL"

# Создаем необходимые директории
sudo mkdir -p /etc/letsencrypt
sudo mkdir -p /var/www/certbot

# Создаем временный nginx конфиг без SSL для получения сертификата
cat > nginx.temp.conf << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF

# Запускаем временный nginx контейнер для получения сертификата
echo "Запускаем temporary nginx для получения сертификата..."
docker run -d --name temp-nginx \
    -p 80:80 \
    -v $(pwd)/nginx.temp.conf:/etc/nginx/conf.d/default.conf \
    -v /var/www/certbot:/var/www/certbot \
    nginx:alpine

# Даем nginx время на запуск
sleep 5

# Получаем SSL сертификат
echo "Получаем SSL сертификат от Let's Encrypt..."
docker run --rm \
    -v /etc/letsencrypt:/etc/letsencrypt \
    -v /var/www/certbot:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $SSL_EMAIL \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN_NAME

# Останавливаем и удаляем временный контейнер
echo "Останавливаем временный nginx..."
docker stop temp-nginx
docker rm temp-nginx

# Удаляем временный конфиг
rm nginx.temp.conf

# Генерируем Diffie-Hellman параметры если они не существуют
if [ ! -f /etc/letsencrypt/ssl-dhparams.pem ]; then
    echo "Генерируем Diffie-Hellman параметры..."
    sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
fi

echo "SSL сертификат успешно получен!"
echo "Теперь вы можете запустить продакшн сервер с командой:"
echo "docker-compose -f docker-compose.production.yml --env-file .env.production up -d"