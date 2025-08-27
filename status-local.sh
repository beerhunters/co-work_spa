#!/bin/bash

echo "🏥 Статус локальной среды разработки:"
docker-compose -f docker-compose.local.yml ps

echo -e "\n📊 Использование ресурсов:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

echo -e "\n🔍 Последние логи (ERROR/WARNING):"
docker-compose -f docker-compose.local.yml --env-file .env.local logs --tail=20 | grep -E "(ERROR|WARNING|CRITICAL)" || echo "Ошибок не найдено"

echo -e "\n🌐 Проверка доступности:"
curl -s -o /dev/null -w "API Status: %{http_code}\n" http://localhost:8000/ || echo "API недоступен"
curl -s -o /dev/null -w "Frontend: %{http_code}\n" http://localhost/ || echo "Frontend недоступен"