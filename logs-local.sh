#!/bin/bash

if [ "$1" = "" ]; then
    echo "📋 Все логи локальной среды:"
    docker-compose -f docker-compose.local.yml --env-file .env.local logs -f
else
    echo "📋 Логи сервиса $1:"
    docker-compose -f docker-compose.local.yml --env-file .env.local logs -f $1
fi