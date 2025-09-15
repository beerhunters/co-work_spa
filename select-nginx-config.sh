#!/bin/sh

# Скрипт для выбора правильной конфигурации nginx в зависимости от наличия SSL

echo "Выбор конфигурации nginx..."

# Проверяем наличие SSL сертификатов
if [ -n "$DOMAIN_NAME" ] && [ -d "/etc/letsencrypt/live/$DOMAIN_NAME" ]; then
    echo "SSL сертификаты найдены для домена $DOMAIN_NAME - используем HTTPS конфигурацию"
    envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/production-https.conf.template > /etc/nginx/conf.d/default.conf
else
    echo "SSL сертификаты не найдены - используем HTTP конфигурацию"
    if [ -n "$DOMAIN_NAME" ]; then
        envsubst '${DOMAIN_NAME}' < /etc/nginx/templates/production-http.conf.template > /etc/nginx/conf.d/default.conf
    else
        echo "DOMAIN_NAME не задан - используем локальную конфигурацию"
        cp /etc/nginx/templates/local.conf /etc/nginx/conf.d/default.conf
    fi
fi

echo "Конфигурация nginx настроена"

# Запускаем nginx
exec nginx -g "daemon off;"