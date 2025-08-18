import asyncio
import os
import threading
import time as time_module
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List
import jwt
from werkzeug.security import check_password_hash

# Импорты моделей и конфигурации
from models.models import init_db, create_admin, Admin
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
    SECRET_KEY_JWT,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
)
from dependencies import init_bot, close_bot, get_db
from utils.logger import get_logger

# Импорты маршрутов
from routes.auth import router as auth_router, create_access_token
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

logger = get_logger(__name__)
security = HTTPBearer()


# Модели для корневых эндпоинтов
class AdminCredentials(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def verify_token_func(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка JWT токена."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    logger.info("Запуск приложения...")

    # Проверяем и создаем директории
    for directory in [
        DATA_DIR,
        AVATARS_DIR,
        Path("/app/ticket_photos"),
        Path("/app/newsletter_photos"),
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

    # Запускаем планировщики
    start_maintenance_tasks()

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


def start_maintenance_tasks():
    """Запускает фоновые задачи обслуживания."""
    import schedule
    from utils.database_maintenance import optimize_database, check_db_health

    # Оптимизация каждый день в 3:00
    schedule.every().day.at("03:00").do(optimize_database)

    # Проверка состояния каждые 10 минут
    schedule.every(10).minutes.do(check_db_health)

    def run_maintenance():
        while True:
            schedule.run_pending()
            time_module.sleep(60)  # Проверяем каждую минуту

    maintenance_thread = threading.Thread(target=run_maintenance, daemon=True)
    maintenance_thread.start()
    logger.info("Планировщик обслуживания БД запущен")


# Создание приложения FastAPI
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="API для управления коворкингом",
    debug=DEBUG,
    lifespan=lifespan,
)

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


# Только необходимые корневые эндпоинты для совместимости с фронтендом
@app.post("/login", response_model=TokenResponse)
async def login_root(credentials: AdminCredentials, db: Session = Depends(get_db)):
    """Аутентификация администратора (для фронтенда)."""
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": admin.login})
    logger.info(f"Успешная аутентификация пользователя: {admin.login}")
    return {"access_token": access_token}


@app.get("/verify_token")
async def verify_token_root(username: str = Depends(verify_token_func)):
    """Проверка действительности токена (для фронтенда)."""
    return {"username": username, "valid": True}


@app.get("/me")
async def get_current_user_root(
    username: str = Depends(verify_token_func), db: Session = Depends(get_db)
):
    """Получение информации о текущем пользователе (для фронтенда)."""
    admin = db.query(Admin).filter(Admin.login == username).first()
    if not admin:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": admin.id,
        "login": admin.login,
        "is_active": admin.is_active,
        "permissions": ["admin"],
    }


# Статические файлы
@app.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Получение аватара."""
    from routes.users import get_avatar as get_avatar_handler

    return await get_avatar_handler(filename)


# Подключение всех маршрутов (теперь с префиксами и без дублирования)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(bookings_router)
app.include_router(tariffs_router)
app.include_router(promocodes_router)  # Теперь включает delete_promocode
app.include_router(tickets_router)
app.include_router(payments_router)
app.include_router(notifications_router)
app.include_router(newsletters_router)
app.include_router(dashboard_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG, log_level="info")
