# Docker Build Instructions

## Исправленные проблемы сборки

### 1. Frontend package-lock.json синхронизация
Проблема была в несоответствии версий между package.json и package-lock.json.
Решение: обновлен package-lock.json командой `npm install` в директории frontend/.

### 2. Упрощенные Dockerfile
Создан упрощенный `Dockerfile.frontend.simple` для разработки и отладки.

## Варианты сборки

### Для разработки (быстрая сборка):
```bash
# Использует простые Dockerfile без многоступенчатой сборки
docker-compose up -d

# Или по отдельности:
docker-compose up -d web
docker-compose up -d frontend
```

### Для production (оптимизированная сборка):
```bash
# Использует multi-stage builds с оптимизацией
docker-compose -f docker-compose.prod.yml up -d

# С принудительной пересборкой:
docker-compose -f docker-compose.prod.yml up -d --build
```

## Создание необходимых директорий

Перед запуском создайте директории для данных:
```bash
mkdir -p data avatars ticket_photos newsletter_photos
```

## Решение проблем сборки

### Если проблемы с frontend:
```bash
cd frontend/
npm install  # Пересоздаст package-lock.json
cd ..
docker-compose build frontend
```

### Если проблемы с Python зависимостями:
```bash
# Очистка кеша Docker
docker system prune -f
docker-compose build --no-cache web
```

### Проверка health checks:
```bash
# После запуска проверьте статус
docker-compose ps

# Health check endpoints:
curl http://localhost:8000/health/
curl http://localhost/
```

## Мониторинг ресурсов

```bash
# Статистика использования ресурсов
docker stats

# Логи сервисов
docker-compose logs -f web
docker-compose logs -f frontend
docker-compose logs -f bot
```

## Переменные окружения

Создайте файл `.env` с необходимыми переменными:
```env
# Обязательные
SECRET_KEY=your-strong-secret-key-here
SECRET_KEY_JWT=your-jwt-secret-key-here
ADMIN_LOGIN=admin
ADMIN_PASSWORD=strong-password-here
BOT_TOKEN=your-telegram-bot-token

# Опциональные
DEBUG=false
HOST=0.0.0.0
PORT=8000
```