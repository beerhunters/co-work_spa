# Secrets Directory

Эта директория содержит чувствительные данные (секреты) для работы приложения.

## Структура

```
secrets/
├── SECRET_KEY.txt           # Django/Flask secret key
├── SECRET_KEY_JWT.txt       # JWT signing key
├── BOT_TOKEN.txt            # Telegram bot token
├── YOKASSA_SECRET_KEY.txt   # YooKassa API secret
├── SMTP_PASSWORD.txt        # SMTP password
└── ADMIN_PASSWORD.txt       # Initial admin password
```

## Использование

### Автоматическая генерация

Используйте скрипт для генерации всех секретов:

```bash
./scripts/setup-secrets.sh
```

### Ручное создание

Создайте файлы вручную:

```bash
# Пример для SECRET_KEY
echo "your-secret-key-here" > secrets/SECRET_KEY.txt

# Генерация случайного ключа
openssl rand -hex 32 > secrets/SECRET_KEY.txt
```

## Безопасность

⚠️ **ВАЖНО:**
- Эта директория добавлена в `.gitignore`
- Никогда не коммитьте секреты в Git
- Используйте разные секреты для dev/staging/production
- Регулярно ротируйте секреты в production

## Docker Secrets

В production рекомендуется использовать Docker Swarm secrets или Kubernetes secrets вместо файлов.

### Docker Swarm пример:

```bash
# Создать secret
echo "my-secret" | docker secret create secret_key -

# В docker-compose.yml
secrets:
  secret_key:
    external: true
```

### Kubernetes пример:

```bash
# Создать secret
kubectl create secret generic app-secrets \
  --from-file=SECRET_KEY=secrets/SECRET_KEY.txt

# В deployment.yaml
env:
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: SECRET_KEY
```

## Fallback на Environment Variables

Приложение поддерживает fallback на environment variables, если файлы секретов не найдены:

```bash
export SECRET_KEY="fallback-key"
docker-compose up
```

## Аудит

Логируйте доступ к секретам (без раскрытия значений) для security audit.
