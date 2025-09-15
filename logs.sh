#!/bin/bash
if [ -n "$1" ]; then
    echo "📋 Логи сервиса $1:"
    docker compose logs -f "$1"
else
    echo "📋 Логи всех сервисов:"
    docker compose logs -f
fi
