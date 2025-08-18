import asyncio
import os
import time  # Добавляем недостающий импорт
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
from dependencies import init_bot, close_bot
from utils.logger import get_logger
from utils.database_maintenance import start_maintenance_tasks

# from middleware import (
#     ErrorHandlingMiddleware,
#     DatabaseMaintenanceMiddleware,
#     RequestLoggingMiddleware,
# )

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
from routes.rubitime import router as rubitime_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    logger.info("Запуск приложения...")

    # Проверяем и создаем директории
    for directory in [
        DATA_DIR,
        AVATARS_DIR,
        TICKET_PHOTOS_DIR,
        NEWSLETTER_PHOTOS_DIR,
    ]:
        try:
            directory.mkdir(exist_ok=True, parents=True)
            # Проверяем права на запись
            test_file = directory / "test_write"
            test_file.touch()
            test_file.unlink()
            logger.info(f"Директория {directory} готова")
        except Exception as e:
            logger.error(f"Ошибка с директорией {directory}: {e}")

    # Инициализируем БД
    try:
        logger.info("Инициализация БД...")
        init_db()
        logger.info("База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"Критическая ошибка инициализации БД: {e}")
        # Попытка восстановления
        try:
            db_path = DATA_DIR / "coworking.db"
            if db_path.exists():
                backup_path = db_path.with_suffix(f".corrupted.{int(time.time())}")
                db_path.rename(backup_path)
                logger.info(f"Поврежденная БД перемещена в {backup_path}")

            # Создаем новую БД
            init_db()
            logger.info("Создана новая БД")
        except Exception as recovery_error:
            logger.error(f"Не удалось восстановить БД: {recovery_error}")

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

    # Создаем placeholder аватар
    placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
    if not placeholder_path.exists():
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (200, 200), color="#E2E8F0")
            draw = ImageDraw.Draw(img)
            draw.ellipse([75, 50, 125, 100], fill="#718096")  # голова
            draw.ellipse([50, 100, 150, 180], fill="#718096")  # тело
            img.save(placeholder_path)
            logger.info("Создан placeholder аватар")
        except Exception as e:
            logger.error(f"Ошибка создания placeholder аватара: {e}")

    logger.info("Приложение запущено успешно")

    yield

    # Shutdown
    logger.info("Остановка приложения...")
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
    docs_url="/api/docs" if DEBUG else None,
    redoc_url="/api/redoc" if DEBUG else None,
)

# # Добавляем middleware
# app.add_middleware(ErrorHandlingMiddleware)
# app.add_middleware(DatabaseMaintenanceMiddleware)
# if DEBUG:
#     app.add_middleware(RequestLoggingMiddleware)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Подключение статических файлов для аватаров
try:
    if AVATARS_DIR.exists():
        app.mount("/avatars", StaticFiles(directory=str(AVATARS_DIR)), name="avatars")

    if TICKET_PHOTOS_DIR.exists():
        app.mount(
            "/ticket_photos",
            StaticFiles(directory=str(TICKET_PHOTOS_DIR)),
            name="ticket_photos",
        )
except Exception as e:
    logger.error(f"Ошибка монтирования статических файлов: {e}")

# Подключение всех роутеров
try:
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(bookings_router)
    app.include_router(tariffs_router)
    app.include_router(promocodes_router)
    app.include_router(tickets_router)
    app.include_router(payments_router)
    app.include_router(notifications_router)
    app.include_router(newsletters_router)
    app.include_router(dashboard_router)
    app.include_router(health_router)
    app.include_router(rubitime_router)
    logger.info("Все роутеры подключены успешно")
except Exception as e:
    logger.error(f"Ошибка подключения роутеров: {e}")

# Дублирующие эндпоинты для совместимости (если фронтенд ожидает их в корне)
# Эти эндпоинты будут работать как с префиксами, так и без них
try:

    @app.post("/login")
    async def login_compat(*args, **kwargs):
        """Совместимость с фронтендом - дублирование /auth/login."""
        from routes.auth import login_auth

        return await login_auth(*args, **kwargs)

    @app.get("/verify_token")
    async def verify_token_compat(*args, **kwargs):
        """Совместимость с фронтендом - дублирование /auth/verify."""
        from routes.auth import verify_token_endpoint

        return await verify_token_endpoint(*args, **kwargs)

    @app.get("/logout")
    async def logout_compat():
        """Совместимость с фронтендом - дублирование /auth/logout."""
        return {"message": "Logged out successfully"}

except Exception as e:
    logger.error(f"Ошибка настройки совместимости: {e}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info",
    )
