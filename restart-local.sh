#!/bin/bash

echo "🔄 Перезапуск локальной среды разработки..."
./stop-local.sh
sleep 3
./start-local.sh