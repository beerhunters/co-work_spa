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
from utils.logger import get_logger, log_startup_info
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
from routes.frontend_logs import router as frontend_logs_router
from routes.optimization import router as optimization_router
from routes.cache import router as cache_router
from routes.logging import router as logging_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""

    # Логируем информацию о запуске
    log_startup_info()
    logger.info("Запуск приложения...")
    
    # Отправляем уведомление о запуске в Telegram
    try:
        logger.info("🔄 Попытка отправить уведомление о запуске в Telegram...")
        from utils.telegram_logger import send_startup_notification
        result = await send_startup_notification()
        logger.info(f"📱 Результат отправки уведомления о запуске: {result}")
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о запуске: {e}")
        import traceback
        logger.error(f"Трассировка ошибки уведомления: {traceback.format_exc()}")

    # Загружаем сохраненную конфигурацию логирования
    try:
        from pathlib import Path
        import json
        import os
        config_file = Path("config") / "logging_config.json"
        logger.info(f"Проверяем наличие файла конфигурации: {config_file.absolute()}")
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
            
            logger.info(f"Найден файл конфигурации с настройками: {list(saved_config.keys())}")
            
            # Применяем сохраненные настройки к переменным окружения
            for key, value in saved_config.items():
                old_value = os.getenv(key)
                os.environ[key] = str(value)
                logger.info(f"Загружена настройка {key}: {old_value} -> {value}")
            
            logger.info("✅ Конфигурация логирования успешно загружена из файла")
            
            # Обновляем уровень логгеров после загрузки новых настроек
            if 'LOG_LEVEL' in saved_config:
                try:
                    from utils.logger import update_loggers_level
                    new_level = saved_config['LOG_LEVEL'].upper()
                    update_loggers_level(new_level)
                    logger.info(f"🔄 Уровень логирования обновлен до {new_level} для всех активных логгеров")
                except Exception as e:
                    logger.error(f"❌ Ошибка обновления уровня логгеров: {e}")
        else:
            logger.info("Файл конфигурации логирования не найден, используются настройки по умолчанию")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки конфигурации логирования: {e}")
        import traceback
        logger.error(f"Полная трассировка: {traceback.format_exc()}")

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

    # Загружаем настройки бэкапов из конфигурационного файла
    try:
        from pathlib import Path
        import json
        import os
        backup_config_file = Path("config") / "backup_config.json"
        logger.info(f"📂 Проверяем файл конфигурации бэкапов: {backup_config_file.absolute()}")
        
        if backup_config_file.exists():
            with open(backup_config_file, 'r') as f:
                backup_settings = json.load(f)
            
            logger.info(f"📂 Найден файл конфигурации бэкапов с настройками: {list(backup_settings.keys())}")
            
            # Применяем сохраненные настройки к переменным окружения
            for key, value in backup_settings.items():
                old_value = os.getenv(key)
                os.environ[key] = str(value)
                logger.info(f"📂 Загружена настройка бэкапов {key}: {old_value} -> {value}")
            
            logger.info("✅ Настройки бэкапов успешно загружены из файла")
        else:
            logger.info("📂 Файл настроек бэкапов не найден, используются настройки по умолчанию")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки настроек бэкапов: {e}")
        import traceback
        logger.error(f"Трассировка: {traceback.format_exc()}")

    # Пересоздаем backup_manager с новыми настройками
    try:
        from utils.backup_manager import backup_manager, DatabaseBackupManager
        # Пересоздаем глобальный экземпляр с обновленными настройками
        import utils.backup_manager
        utils.backup_manager.backup_manager = DatabaseBackupManager()
        logger.info("📂 Backup manager recreated with updated settings")
    except Exception as e:
        logger.error(f"❌ Ошибка пересоздания backup manager: {e}")

    # Запускаем систему автоматических бэкапов
    try:
        await start_backup_scheduler()
        logger.info("📂 Планировщик бэкапов запущен")
    except Exception as e:
        logger.error(f"Ошибка запуска планировщика бэкапов: {e}")

    yield

    # Shutdown
    logger.info("Завершение приложения...")
    
    # Отправляем уведомление об остановке в Telegram
    try:
        logger.info("🔄 Попытка отправить уведомление об остановке в Telegram...")
        from utils.telegram_logger import send_shutdown_notification
        result = await send_shutdown_notification()
        logger.info(f"📱 Результат отправки уведомления об остановке: {result}")
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление об остановке: {e}")
        import traceback
        logger.error(f"Трассировка ошибки уведомления об остановке: {traceback.format_exc()}")

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
    (frontend_logs_router, "frontend_logs"),
    (optimization_router, "optimization"),
    (cache_router, "cache"),
    (logging_router, "logging"),
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
