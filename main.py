import asyncio
import os
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Импорты моделей и конфигурации
from models.models import init_db, create_admin
from config import (
    APP_NAME,
    APP_VERSION,
    DEBUG,
    HOST,
    PORT,
    ADMIN_LOGIN,
    ADMIN_PASSWORD,
    CORS_ORIGINS,
    DATA_DIR,
    AVATARS_DIR,
    TICKET_PHOTOS_DIR,
    NEWSLETTER_PHOTOS_DIR,
)
from dependencies import init_bot, close_bot, start_cache_cleanup, stop_cache_cleanup
from models.models import cleanup_database
from utils.logger import get_logger
from utils.database_maintenance import start_maintenance_tasks
from utils.backup_manager import start_backup_scheduler, stop_backup_scheduler

# Импорты всех роутеров
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.bookings import router as bookings_router
from routes.tariffs import router as tariffs_router
from routes.promocodes import router as promocodes_router
from routes.tickets import router as tickets_router
from routes.payments import router as payments_router
from routes.notifications import router as notifications_router
from routes.newsletters import router as newsletters_router
from routes.dashboard import router as dashboard_router
from routes.health import router as health_router
from routes.monitoring import router as monitoring_router
from routes.api_keys import router as api_keys_router
from routes.rubitime import router as rubitime_router
from routes.backups import router as backups_router
from routes import admins

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    logger.info("Запуск приложения...")

    # Создаем необходимые директории
    directories = [DATA_DIR, AVATARS_DIR, TICKET_PHOTOS_DIR, NEWSLETTER_PHOTOS_DIR]

    for directory in directories:
        try:
            directory.mkdir(exist_ok=True, parents=True)
            logger.info(f"Директория {directory} готова")
        except Exception as e:
            logger.error(f"Ошибка создания директории {directory}: {e}")

    # Инициализируем БД (DatabaseManager делает это автоматически и безопасно)
    try:
        logger.info("Инициализация БД...")
        init_db()
        logger.info("База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

    # Создаем админа
    try:
        create_admin(ADMIN_LOGIN, ADMIN_PASSWORD)
        logger.info("Админ создан/обновлен успешно")
    except Exception as e:
        logger.error(f"Ошибка создания админа: {e}")

    # Инициализируем бота
    try:
        init_bot()
        logger.info("Бот инициализирован")
    except Exception as e:
        logger.error(f"Ошибка инициализации бота: {e}")

    # Запускаем планировщики обслуживания БД
    try:
        start_maintenance_tasks()
    except Exception as e:
        logger.error(f"Ошибка запуска планировщиков: {e}")

    # Запускаем фоновую очистку кэша
    try:
        await start_cache_cleanup()
        logger.info("Кэш-менеджер запущен")
    except Exception as e:
        logger.error(f"Ошибка запуска кэш-менеджера: {e}")

    # Запускаем систему автоматических бэкапов
    try:
        await start_backup_scheduler()
        logger.info("Планировщик бэкапов запущен")
    except Exception as e:
        logger.error(f"Ошибка запуска планировщика бэкапов: {e}")

    yield

    # Shutdown
    logger.info("Завершение приложения...")

    try:
        await stop_cache_cleanup()
        logger.info("Кэш-менеджер остановлен")
    except Exception as e:
        logger.error(f"Ошибка остановки кэш-менеджера: {e}")

    # Останавливаем планировщик бэкапов
    try:
        await stop_backup_scheduler()
        logger.info("Планировщик бэкапов остановлен")
    except Exception as e:
        logger.error(f"Ошибка остановки планировщика бэкапов: {e}")

    try:
        await cleanup_database()
        logger.info("Connection pool очищен")
    except Exception as e:
        logger.error(f"Ошибка очистки connection pool: {e}")

    try:
        await close_bot()
        logger.info("Бот закрыт")
    except Exception as e:
        logger.error(f"Ошибка закрытия бота: {e}")


# Создание приложения FastAPI
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API для управления коворкингом",
    debug=DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if DEBUG else None,  # Только в debug режиме
    redoc_url="/redoc" if DEBUG else None,  # Только в debug режиме
)

# Подключение middleware
from utils.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    PerformanceMiddleware,
)

# Порядок middleware важен - добавляем в обратном порядке выполнения
app.add_middleware(PerformanceMiddleware, enabled=True)
app.add_middleware(SecurityHeadersMiddleware, enabled=True)
app.add_middleware(RequestLoggingMiddleware, enabled=True)
app.add_middleware(RateLimitMiddleware, enabled=True)

# Настройка CORS (должен быть после других middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Request-ID",  # Для трассировки запросов
    ],
)


# Базовый маршрут
@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы API."""
    return {
        "message": f"{APP_NAME} is running",
        "version": APP_VERSION,
        "status": "healthy",
    }


# Подключение статических файлов
try:
    if AVATARS_DIR.exists():
        app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")
        logger.info("Аватары подключены")

    if TICKET_PHOTOS_DIR.exists():
        app.mount(
            "/ticket_photos",
            StaticFiles(directory=str(TICKET_PHOTOS_DIR)),
            name="ticket_photos",
        )
        logger.info("Фото тикетов подключены")
except Exception as e:
    logger.error(f"Ошибка монтирования статических файлов: {e}")

# Подключение всех роутеров
routers = [
    (auth_router, "auth"),
    (users_router, "users"),
    (bookings_router, "bookings"),
    (tariffs_router, "tariffs"),
    (promocodes_router, "promocodes"),
    (tickets_router, "tickets"),
    (payments_router, "payments"),
    (notifications_router, "notifications"),
    (newsletters_router, "newsletters"),
    (dashboard_router, "dashboard"),
    (health_router, "health"),
    (monitoring_router, "monitoring"),
    (api_keys_router, "api_keys"),
    (backups_router, "backups"),
    (rubitime_router, "rubitime"),
    (admins.router, "admins"),
]

for router, name in routers:
    try:
        app.include_router(router)
        logger.debug(f"Роутер {name} подключен")
    except Exception as e:
        logger.error(f"Ошибка подключения роутера {name}: {e}")

logger.info("Все роутеры подключены")


# Совместимость с фронтендом обеспечивается через auth.py роутер


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info",
    )
