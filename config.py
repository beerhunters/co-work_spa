import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Базовые настройки
APP_NAME = "Coworking API"
APP_VERSION = "1.0.0"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Директории
BASE_DIR = Path(__file__).parent
DATA_DIR = Path("/app/data")  # Используем абсолютный путь для Docker
LOGS_DIR = BASE_DIR / "logs"
AVATARS_DIR = Path("/app/avatars")  # Абсолютный путь
TICKET_PHOTOS_DIR = Path("/app/ticket_photos")  # Абсолютный путь
NEWSLETTER_PHOTOS_DIR = Path("/app/newsletter_photos")  # Абсолютный путь

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
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
SECRET_KEY_JWT = os.getenv("SECRET_KEY_JWT", "your-jwt-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

# Администратор
ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/your_bot")
INVITE_LINK = os.getenv("INVITE_LINK", "https://t.me/your_bot")
GROUP_ID = os.getenv("GROUP_ID")
FOR_LOGS = os.getenv("FOR_LOGS")

# YooKassa
YOKASSA_ACCOUNT_ID = os.getenv("YOKASSA_ACCOUNT_ID")
YOKASSA_SECRET_KEY = os.getenv("YOKASSA_SECRET_KEY")

# Rubitime
RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = os.getenv("RUBITIME_BASE_URL", "https://rubitime.ru/api2/")
RUBITIME_BRANCH_ID = int(os.getenv("RUBITIME_BRANCH_ID", "12595"))
RUBITIME_COOPERATOR_ID = int(os.getenv("RUBITIME_COOPERATOR_ID", "25786"))

# Лимиты файлов
FILE_RETENTION_DAYS = int(os.getenv("FILE_RETENTION_DAYS", "30"))
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Фронтенд
FRONTEND_URL = os.getenv("FRONTEND_URL", f"http://{HOST}")
ADMIN_URL = os.getenv("ADMIN_URL", "https://t.me/partacoworking")
RULES_URL = os.getenv("RULES_URL", "https://parta-works.ru/main_rules")

# CORS настройки
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", f"http://{HOST},http://localhost:3000,http://localhost:5173"
).split(",")

# Email (если потребуется в будущем)
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"

# Настройки рассылки
NEWSLETTER_MAX_PHOTOS = int(os.getenv("NEWSLETTER_MAX_PHOTOS", "10"))
NEWSLETTER_MAX_FILE_SIZE_MB = int(os.getenv("NEWSLETTER_MAX_FILE_SIZE_MB", "20"))
NEWSLETTER_RATE_LIMIT_DELAY = float(os.getenv("NEWSLETTER_RATE_LIMIT_DELAY", "0.05"))

# Настройки временной зоны
import pytz

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Валидация обязательных переменных
required_env_vars = {
    "BOT_TOKEN": BOT_TOKEN,
}

missing_vars = [key for key, value in required_env_vars.items() if not value]
if missing_vars:
    print(
        f"ПРЕДУПРЕЖДЕНИЕ: Отсутствуют переменные окружения: {', '.join(missing_vars)}"
    )
