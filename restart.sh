#!/bin/bash
echo "🔄 Перезапуск Coworking System..."
docker compose down
./scripts/start-prod.sh
