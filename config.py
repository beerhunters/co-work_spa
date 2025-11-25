import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional
import logging

# Загружаем переменные окружения
load_dotenv()

# ===================================
# Secret Manager - Lazy Loading
# ===================================

class SecretManager:
    """
    Управляет загрузкой секретов с поддержкой:
    1. Docker secrets (/run/secrets/<name>)
    2. Fallback на environment variables
    3. Кэширование прочитанных значений
    """

    _cache = {}
    _logger = logging.getLogger("SecretManager")

    @classmethod
    def get_secret(cls, name: str, env_var: Optional[str] = None, required: bool = True) -> Optional[str]:
        """
        Получить секрет с lazy loading.

        Args:
            name: Имя секрета (например, 'secret_key')
            env_var: Имя environment variable для fallback (по умолчанию равно name в верхнем регистре)
            required: Выбросить ошибку если секрет не найден

        Returns:
            Значение секрета или None если не найден и required=False
        """
        # Проверить кэш
        cache_key = name
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        secret_value = None

        # 1. Попробовать прочитать из Docker secrets
        docker_secret_path = Path(f"/run/secrets/{name}")
        if docker_secret_path.exists():
            try:
                secret_value = docker_secret_path.read_text().strip()
                cls._logger.debug(f"Loaded secret '{name}' from Docker secrets")
            except Exception as e:
                cls._logger.warning(f"Failed to read Docker secret '{name}': {e}")

        # 2. Fallback на environment variable
        if not secret_value:
            env_name = env_var or name.upper()
            secret_value = os.getenv(env_name)
            if secret_value:
                cls._logger.debug(f"Loaded secret '{name}' from environment variable '{env_name}'")

        # 3. Валидация если required
        if not secret_value and required:
            raise ValueError(
                f"Secret '{name}' not found. "
                f"Provide it via Docker secret (/run/secrets/{name}) or environment variable."
            )

        # Кэшировать и вернуть
        cls._cache[cache_key] = secret_value
        return secret_value

    @classmethod
    def clear_cache(cls):
        """Очистить кэш секретов (для тестирования)"""
        cls._cache.clear()


# Функции-геттеры для секретов (lazy loading)
def get_secret_key() -> str:
    """Получить SECRET_KEY"""
    return SecretManager.get_secret("secret_key", "SECRET_KEY", required=True)

def get_secret_key_jwt() -> str:
    """Получить SECRET_KEY_JWT"""
    return SecretManager.get_secret("secret_key_jwt", "SECRET_KEY_JWT", required=True)

def get_bot_token() -> str:
    """Получить BOT_TOKEN"""
    return SecretManager.get_secret("bot_token", "BOT_TOKEN", required=True)

def get_admin_password() -> str:
    """Получить ADMIN_PASSWORD"""
    return SecretManager.get_secret("admin_password", "ADMIN_PASSWORD", required=True)

def get_yokassa_secret_key() -> Optional[str]:
    """Получить YOKASSA_SECRET_KEY"""
    return SecretManager.get_secret("yokassa_secret_key", "YOKASSA_SECRET_KEY", required=False)

def get_smtp_password() -> Optional[str]:
    """Получить SMTP_PASSWORD"""
    return SecretManager.get_secret("smtp_password", "SMTP_PASSWORD", required=False)

# Базовые настройки
APP_NAME = os.getenv("APP_NAME", "Coworking API")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Директории
BASE_DIR = Path(__file__).parent

# Определяем окружение: Docker или хост
# Если /app существует и доступен для записи - мы в Docker
IS_DOCKER = Path("/app").exists() and os.access("/app", os.W_OK)

if IS_DOCKER:
    # В Docker используем абсолютные пути
    DATA_DIR = Path("/app/data")
    AVATARS_DIR = Path("/app/avatars")
    TICKET_PHOTOS_DIR = Path("/app/ticket_photos")
    NEWSLETTER_PHOTOS_DIR = Path("/app/newsletter_photos")
else:
    # На хосте используем относительные пути от BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    AVATARS_DIR = BASE_DIR / "avatars"
    TICKET_PHOTOS_DIR = BASE_DIR / "ticket_photos"
    NEWSLETTER_PHOTOS_DIR = BASE_DIR / "newsletter_photos"

LOGS_DIR = BASE_DIR / "logs"

# Создаем директории если не существуют
for directory in [
    DATA_DIR,
    LOGS_DIR,
    AVATARS_DIR,
    TICKET_PHOTOS_DIR,
    NEWSLETTER_PHOTOS_DIR,
]:
    directory.mkdir(exist_ok=True, parents=True)

# Сетевые настройки
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
API_BASE_URL = os.getenv("API_BASE_URL", f"http://{HOST}:{PORT}")

# База данных
DATABASE_URL = f"sqlite:///{DATA_DIR}/coworking.db"
DATABASE_TIMEOUT = int(os.getenv("DB_TIMEOUT", "60"))
DATABASE_RETRY_ATTEMPTS = int(os.getenv("DB_RETRY_ATTEMPTS", "3"))
DATABASE_RETRY_DELAY = float(os.getenv("DB_RETRY_DELAY", "0.1"))

# Безопасность
# ВАЖНО: Секреты загружаются через lazy loading функции выше
# Для обратной совместимости оставляем переменные, но они будут None до первого вызова
SECRET_KEY = None  # Используйте get_secret_key() вместо прямого доступа
SECRET_KEY_JWT = None  # Используйте get_secret_key_jwt() вместо прямого доступа
ALGORITHM = "HS256"

# Срок действия токенов
# ⚠️ ДЛЯ ТЕСТИРОВАНИЯ: установите ACCESS_TOKEN_EXPIRE_MINUTES=2 для быстрой проверки refresh токена
# Для продакшена используйте ACCESS_TOKEN_EXPIRE_HOURS=24
if os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"):
    # Режим тестирования с минутами
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    ACCESS_TOKEN_EXPIRE_HOURS = None
    print(f"⚠️ ТЕСТОВЫЙ РЕЖИМ: Access token истекает через {ACCESS_TOKEN_EXPIRE_MINUTES} минут")
else:
    # Обычный режим с часами
    ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))
    ACCESS_TOKEN_EXPIRE_MINUTES = None

REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# CAPTCHA настройки (hCaptcha)
# CAPTCHA требуется после CAPTCHA_FAILED_ATTEMPTS_THRESHOLD неудачных попыток входа
HCAPTCHA_SECRET_KEY = os.getenv("HCAPTCHA_SECRET_KEY")  # Опционально - если не задан, CAPTCHA отключен
HCAPTCHA_SITE_KEY = os.getenv("HCAPTCHA_SITE_KEY")  # Для frontend
CAPTCHA_ENABLED = bool(HCAPTCHA_SECRET_KEY)  # Автоматически включается если есть секретный ключ
CAPTCHA_FAILED_ATTEMPTS_THRESHOLD = int(os.getenv("CAPTCHA_FAILED_ATTEMPTS_THRESHOLD", "3"))

# Администратор
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN")
ADMIN_PASSWORD = None  # Используйте get_admin_password() вместо прямого доступа

if not ADMIN_LOGIN:
    raise ValueError("ADMIN_LOGIN не задан в переменных окружения")

# Telegram Bot
BOT_TOKEN = None  # Используйте get_bot_token() вместо прямого доступа
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/your_bot")
INVITE_LINK = os.getenv("INVITE_LINK", "https://t.me/your_bot")
GROUP_ID = os.getenv("GROUP_ID")
FOR_LOGS = os.getenv("FOR_LOGS")

# YooKassa
YOKASSA_ACCOUNT_ID = os.getenv("YOKASSA_ACCOUNT_ID")
YOKASSA_SECRET_KEY = None  # Используйте get_yokassa_secret_key() вместо прямого доступа

# Rubitime
RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = os.getenv("RUBITIME_BASE_URL", "https://rubitime.ru/api2/")
RUBITIME_BRANCH_ID = int(os.getenv("RUBITIME_BRANCH_ID", "12595"))
RUBITIME_COOPERATOR_ID = int(os.getenv("RUBITIME_COOPERATOR_ID", "25786"))

# Лимиты файлов
FILE_RETENTION_DAYS = int(os.getenv("FILE_RETENTION_DAYS", "30"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

# Фронтенд
FRONTEND_URL = os.getenv("FRONTEND_URL", f"http://{HOST}")
ADMIN_URL = os.getenv("ADMIN_URL", "https://t.me/partacoworking")
RULES_URL = os.getenv("RULES_URL", "https://parta-works.ru/main_rules")

# CORS настройки
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", f"http://{HOST},http://localhost:3000,http://localhost:5173"
).split(",")

# Email настройки удалены - не используются в приложении

# Настройки рассылки
NEWSLETTER_MAX_PHOTOS = int(os.getenv("NEWSLETTER_MAX_PHOTOS", "10"))
NEWSLETTER_MAX_FILE_SIZE_MB = int(os.getenv("NEWSLETTER_MAX_FILE_SIZE_MB", "20"))
NEWSLETTER_RATE_LIMIT_DELAY = float(os.getenv("NEWSLETTER_RATE_LIMIT_DELAY", "0.05"))

# Redis и кэширование
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))  # 5 минут
CACHE_DASHBOARD_TTL = int(os.getenv("CACHE_DASHBOARD_TTL", "60"))  # 1 минута
CACHE_USER_DATA_TTL = int(os.getenv("CACHE_USER_DATA_TTL", "600"))  # 10 минут
CACHE_STATIC_DATA_TTL = int(os.getenv("CACHE_STATIC_DATA_TTL", "1800"))  # 30 минут

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()  
LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()  # "text" или "json"
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOGS_DIR = BASE_DIR / Path(os.getenv("LOGS_DIR", "logs"))

# Telegram логирование
TELEGRAM_LOGGING_ENABLED = os.getenv("TELEGRAM_LOGGING_ENABLED", "false").lower() == "true"
TELEGRAM_LOG_MIN_LEVEL = os.getenv("TELEGRAM_LOG_MIN_LEVEL", "ERROR")
TELEGRAM_LOG_RATE_LIMIT = int(os.getenv("TELEGRAM_LOG_RATE_LIMIT", "5"))

# Фильтрация логов и метрики производительности
EXCLUDE_PATHS_FROM_LOGGING = os.getenv(
    "EXCLUDE_PATHS_FROM_LOGGING",
    "/notifications/check_new,/health"
).split(",")
MIDDLEWARE_LOG_LEVEL = os.getenv("MIDDLEWARE_LOG_LEVEL", "INFO").upper()
LOG_SLOW_REQUEST_THRESHOLD_MS = int(os.getenv("LOG_SLOW_REQUEST_THRESHOLD_MS", "1000"))

# ===================================
# Email / SMTP настройки
# ===================================

# Яндекс SMTP конфигурация
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.yandex.ru")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 для SSL, 587 для TLS
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
SMTP_USERNAME = os.getenv("SMTP_USERNAME")  # Email адрес
SMTP_PASSWORD = None  # Используйте get_smtp_password() вместо прямого доступа
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)  # По умолчанию = username
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Coworking Space")
SMTP_TIMEOUT = int(os.getenv("SMTP_TIMEOUT", "30"))  # Таймаут в секундах
SMTP_MAX_RETRIES = int(os.getenv("SMTP_MAX_RETRIES", "3"))  # Количество попыток

# Email настройки
EMAIL_BATCH_SIZE = int(os.getenv("EMAIL_BATCH_SIZE", "50"))  # Количество писем в батче
EMAIL_BATCH_DELAY = int(os.getenv("EMAIL_BATCH_DELAY", "1"))  # Задержка между батчами (секунды)
EMAIL_RATE_LIMIT_PER_MINUTE = int(os.getenv("EMAIL_RATE_LIMIT_PER_MINUTE", "100"))  # Яндекс лимит

# Tracking - используем FRONTEND_URL если EMAIL_TRACKING_DOMAIN не указан
# Это важно, так как для трекинга нужен публично доступный URL
FRONTEND_URL = os.getenv("FRONTEND_URL", f"http://{HOST}")
EMAIL_TRACKING_DOMAIN = os.getenv("EMAIL_TRACKING_DOMAIN", FRONTEND_URL)  # Домен для трекинга

# Настройки временной зоны
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Валидация обязательных переменных
import logging
logger = logging.getLogger(__name__)

# Валидация критичных секретов перенесена в функции-геттеры
# Секреты будут проверены при первом использовании, а не при импорте модуля
