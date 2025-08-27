#!/bin/bash

echo "⏹️ Остановка локальной среды разработки..."
docker-compose -f docker-compose.local.yml --env-file .env.local down
echo "✅ Локальная среда остановлена"