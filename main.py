import asyncio
import os
import threading
import time as time_module
import uuid
import re
from datetime import date
from datetime import timedelta
from datetime import time as time_type
from pathlib import Path
from typing import List

import aiohttp
import jwt
import pytz
import schedule
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InputMediaPhoto, FSInputFile
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form
from fastapi import Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, event
from sqlalchemy import func
from sqlalchemy.orm import joinedload, sessionmaker, scoped_session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash
import sqlite3
from sqlalchemy.exc import OperationalError, DatabaseError
from contextlib import contextmanager
from yookassa import Payment, Refund, Configuration
from pathlib import Path
from fastapi import File, UploadFile
from fastapi.responses import FileResponse
import hashlib

# Импорты моделей и утилит
from models.models import *
from models.models import init_db, create_admin, DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)
app = FastAPI()

# Настройки
AVATARS_DIR = Path(__file__).parent / "avatars"
AVATARS_DIR.mkdir(exist_ok=True)
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Создаем директорию data если её нет
data_dir = Path("/app/data")
data_dir.mkdir(exist_ok=True)

# Создаем улучшенный engine для SQLite (заменяем импортированный)
engine = create_engine(
    f"sqlite:///{data_dir}/coworking.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 60,
        "isolation_level": None,
    },
    echo=False,
    poolclass=StaticPool,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Используем scoped_session для thread-safe работы
Session = scoped_session(sessionmaker(bind=engine))

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
SECRET_KEY_JWT = os.getenv("SECRET_KEY_JWT", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Инициализация бота
if BOT_TOKEN:
    bot = Bot(token=BOT_TOKEN)
else:
    bot = None

# Настройки внешних API
RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = "https://rubitime.ru/api2/"
RUBITIME_BRANCH_ID = int(os.getenv("RUBITIME_BRANCH_ID", "12595"))
RUBITIME_COOPERATOR_ID = int(os.getenv("RUBITIME_COOPERATOR_ID", "25786"))

# Настройка Yookassa
Configuration.account_id = os.getenv("YOKASSA_ACCOUNT_ID")
Configuration.secret_key = os.getenv("YOKASSA_SECRET_KEY")

# Security
security = HTTPBearer()


# ================== PYDANTIC MODELS ==================


class AdminBase(BaseModel):
    """Модель данных админа для аутентификации."""

    login: str
    password: str


class TokenResponse(BaseModel):
    """Модель ответа с токеном."""

    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    """Базовая модель пользователя."""

    id: int
    telegram_id: int
    full_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    username: Optional[str]
    successful_bookings: int
    language_code: str
    invited_count: int
    reg_date: Optional[datetime]
    first_join_time: datetime
    agreed_to_terms: bool
    avatar: Optional[str]
    referrer_id: Optional[int]

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Модель для обновления данных пользователя."""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    avatar: Optional[str] = None
    agreed_to_terms: Optional[bool] = None
    reg_date: Optional[str] = None  # ISO строка
    successful_bookings: Optional[int] = None
    invited_count: Optional[int] = None


class UserCreate(BaseModel):
    """Модель создания нового пользователя."""

    telegram_id: int
    username: Optional[str] = None
    language_code: str = "ru"
    referrer_id: Optional[int] = None


# Остальные модели для тарифов, броней, билетов и т.д.
class TariffBase(BaseModel):
    id: int
    name: str
    description: str
    price: float
    purpose: Optional[str]
    service_id: Optional[int]
    is_active: bool

    class Config:
        from_attributes = True


class PromocodeBase(BaseModel):
    id: int
    name: str
    discount: int
    usage_quantity: int
    expiration_date: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class PromocodeCreate(BaseModel):
    name: str
    discount: int
    usage_quantity: int = 0
    expiration_date: Optional[datetime] = None
    is_active: bool = True


class PromocodeUpdate(BaseModel):
    name: Optional[str] = None
    discount: Optional[int] = None
    usage_quantity: Optional[int] = None
    expiration_date: Optional[datetime] = None
    is_active: Optional[bool] = None


class BookingBase(BaseModel):
    id: int
    user_id: int
    tariff_id: int
    visit_date: date
    visit_time: Optional[time_type]
    duration: Optional[int]
    promocode_id: Optional[int]
    amount: float
    payment_id: Optional[str]
    paid: bool
    rubitime_id: Optional[str]
    confirmed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    user_id: int  # Это будет telegram_id
    tariff_id: int
    visit_date: date
    visit_time: Optional[time_type] = None
    duration: Optional[int] = None
    promocode_id: Optional[int] = None
    amount: float
    payment_id: Optional[str] = None
    paid: bool = False
    confirmed: bool = False
    rubitime_id: Optional[str] = None


class NewsletterBase(BaseModel):
    id: int
    message: str
    created_at: datetime
    recipient_count: int

    class Config:
        from_attributes = True


class NewsletterCreate(BaseModel):
    message: str
    recipient_type: str  # 'all' или 'selected'
    user_ids: Optional[List[int]] = None


class NewsletterResponse(BaseModel):
    id: int
    message: str
    status: str
    total_count: int
    success_count: int
    photo_count: int
    created_at: datetime


class TicketBase(BaseModel):
    id: int
    user_id: int
    description: str
    photo_id: Optional[str]
    status: str
    comment: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TariffCreate(BaseModel):
    name: str
    description: str
    price: float
    purpose: Optional[str] = None
    service_id: Optional[int] = None
    is_active: bool = True


class TariffUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    purpose: Optional[str] = None
    service_id: Optional[int] = None
    is_active: Optional[bool] = None


class NotificationBase(BaseModel):
    id: int
    user_id: int
    message: str
    booking_id: Optional[int]
    ticket_id: Optional[int]
    target_url: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    user_id: int
    description: str
    photo_id: Optional[str] = None
    status: Optional[str] = "OPEN"
    comment: Optional[str] = None


class NotificationUpdate(BaseModel):
    is_read: bool = True


# ================== UTILITY FUNCTIONS ==================


def create_access_token(data: dict):
    """Создание JWT токена."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
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


def get_db():
    """Получение сессии БД с улучшенной обработкой ошибок."""
    session = Session()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка сессии БД: {e}")
        raise
    finally:
        try:
            session.close()
        except Exception as e:
            logger.error(f"Ошибка закрытия сессии БД: {e}")


def format_phone_for_rubitime(phone: str) -> str:
    """
    Форматирует номер телефона для Rubitime API
    Возвращает номер в формате +7XXXXXXXXXX или пустую строку если номер некорректный
    """
    if not phone:
        return ""

    # Убираем все символы кроме цифр
    digits = re.sub(r"[^0-9]", "", phone)

    if not digits:
        return ""

    # Обрабатываем различные форматы
    if digits.startswith("8") and len(digits) == 11:
        # 8XXXXXXXXXX -> +7XXXXXXXXXX
        digits = "7" + digits[1:]
    elif digits.startswith("7") and len(digits) == 11:
        # 7XXXXXXXXXX -> +7XXXXXXXXXX
        pass
    elif len(digits) == 10:
        # XXXXXXXXXX -> +7XXXXXXXXXX
        digits = "7" + digits
    else:
        # Неподдерживаемый формат
        logger.warning(f"Неподдерживаемый формат телефона: {phone}")
        return ""

    # Проверяем финальную длину
    if len(digits) != 11 or not digits.startswith("7"):
        logger.warning(f"Некорректный телефон после обработки: {digits}")
        return ""

    return "+" + digits


def format_booking_notification(user, tariff, booking_data) -> str:
    """
    Форматирует уведомление о новом бронировании для админа

    Args:
        user: объект User или словарь с данными пользователя
        tariff: объект Tariff или словарь с данными тарифа
        booking_data: словарь с данными бронирования
    """
    tariff_emojis = {
        "coworking": "🏢",
        "meeting": "🤝",
        "переговорная": "🤝",
        "коворкинг": "🏢",
    }

    # Безопасное получение данных пользователя
    if hasattr(user, "full_name"):
        user_name = user.full_name or "Не указано"
        user_phone = user.phone or "Не указано"
        user_username = f"@{user.username}" if user.username else "Не указано"
        telegram_id = user.telegram_id
    else:
        # Если user - это словарь
        user_name = user.get("full_name") or "Не указано"
        user_phone = user.get("phone") or "Не указано"
        user_username = (
            f"@{user.get('username')}" if user.get("username") else "Не указано"
        )
        telegram_id = user.get("telegram_id", "Неизвестно")

    # Безопасное получение данных тарифа
    if hasattr(tariff, "name"):
        tariff_name = tariff.name
        tariff_purpose = tariff.purpose or ""
        tariff_price = tariff.price
    else:
        # Если tariff - это словарь
        tariff_name = tariff.get("name", "Неизвестно")
        tariff_purpose = tariff.get("purpose", "")
        tariff_price = tariff.get("price", 0)

    purpose = tariff_purpose.lower() if tariff_purpose else ""
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    # Форматирование даты и времени
    if visit_time:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            # Если visit_date - строка
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)

        if hasattr(visit_time, "strftime"):
            time_str = visit_time.strftime("%H:%M")
        else:
            # Если visit_time - строка
            try:
                time_obj = datetime.strptime(str(visit_time), "%H:%M:%S").time_type()
                time_str = time_obj.strftime("%H:%M")
            except:
                time_str = str(visit_time)

        datetime_str = f"{date_str} в {time_str}"
    else:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)
        datetime_str = f"{date_str} (весь день)"

    # Информация о промокоде
    discount_info = ""
    promocode_name = booking_data.get("promocode_name")
    if promocode_name:
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    # Информация о длительности
    duration_info = ""
    duration = booking_data.get("duration")
    if duration:
        duration_info = f"\n⏱ <b>Длительность:</b> {duration} час(ов)"

    # Сумма
    amount = booking_data.get("amount", 0)

    message = f"""🎯 <b>НОВАЯ БРОНЬ!</b> {tariff_emoji}

👤 <b>Клиент:</b> {user_name}
📱 <b>Телефон:</b> {user_phone}
💬 <b>Telegram:</b> {user_username}
🆔 <b>ID:</b> {telegram_id}

📋 <b>Тариф:</b> {tariff_name}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}{discount_info}

💰 <b>Сумма:</b> {amount:.0f} ₽
✅ <b>Статус:</b> Оплачено, ожидает подтверждения"""

    return message


# ================== AUTHENTICATION ENDPOINTS ==================


@app.get("/")
async def root():
    """Корневой эндпоинт для проверки работы API."""
    return {"message": "Coworking API is running"}


@app.post("/login", response_model=TokenResponse)
async def login(credentials: AdminBase, db: Session = Depends(get_db)):
    """Аутентификация администратора."""
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": admin.login})
    return {"access_token": access_token}


@app.get("/verify_token")
async def verify_token_endpoint(username: str = Depends(verify_token)):
    """Проверка действительности токена."""
    return {"username": username}


@app.get("/logout")
async def logout():
    """Выход из системы."""
    return {"message": "Logged out successfully"}


# ================== USER ENDPOINTS ==================


@app.get("/users", response_model=List[UserBase])
async def get_users(_: str = Depends(verify_token)):
    """Получение списка всех пользователей."""

    def _get_users(session):
        users = session.query(User).order_by(User.first_join_time.desc()).all()

        # Преобразуем SQLAlchemy объекты в словари
        users_data = []
        for user in users:
            user_dict = {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "username": user.username,
                "successful_bookings": user.successful_bookings or 0,
                "language_code": user.language_code or "ru",
                "invited_count": user.invited_count or 0,
                "reg_date": user.reg_date,
                "first_join_time": user.first_join_time,
                "agreed_to_terms": user.agreed_to_terms or False,
                "avatar": user.avatar,
                "referrer_id": user.referrer_id,
            }
            users_data.append(user_dict)

        return users_data

    try:
        return DatabaseManager.safe_execute(_get_users)
    except Exception as e:
        logger.error(f"Ошибка в get_users: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения пользователей")


@app.get("/users/{user_id}", response_model=UserBase)
async def get_user(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение пользователя по ID."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/telegram/{telegram_id}")
async def get_user_by_telegram_id(telegram_id: int, db: Session = Depends(get_db)):
    """Получение пользователя по Telegram ID. Используется ботом."""
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем полноту регистрации
    is_complete = all([user.full_name, user.phone, user.email])

    user_data = {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "username": user.username,
        "successful_bookings": user.successful_bookings,
        "language_code": user.language_code,
        "invited_count": user.invited_count,
        "reg_date": user.reg_date,
        "first_join_time": user.first_join_time,
        "agreed_to_terms": user.agreed_to_terms,
        "avatar": user.avatar,
        "referrer_id": user.referrer_id,
        "is_complete": is_complete,
    }

    return user_data


@app.put("/users/telegram/{telegram_id}")
async def update_user_by_telegram_id(telegram_id: int, user_data: UserUpdate):
    """Обновление пользователя по telegram_id."""

    def _update_user(session):
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_dict = user_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(user, field):
                setattr(user, field, value)

        session.flush()  # Обновляем объект без коммита
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "email": user.email,
            "username": user.username,
            "successful_bookings": user.successful_bookings,
            "language_code": user.language_code,
            "invited_count": user.invited_count,
            "reg_date": user.reg_date,
            "first_join_time": user.first_join_time,
            "agreed_to_terms": user.agreed_to_terms,
            "avatar": user.avatar,
            "referrer_id": user.referrer_id,
        }

    try:
        return DatabaseManager.safe_execute(_update_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        raise HTTPException(
            status_code=500, detail=f"Ошибка обновления пользователя: {str(e)}"
        )


@app.post("/users/check_and_add")
async def check_and_add_user(
    telegram_id: int,
    username: Optional[str] = None,
    language_code: str = "ru",
    referrer_id: Optional[int] = None,
):
    """Проверка и добавление пользователя в БД с улучшенной обработкой."""

    def _check_and_add_user(session):
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        is_new = False

        if not user:
            # Создаем нового пользователя с минимальными данными
            user = User(
                telegram_id=telegram_id,
                username=username if username else None,
                language_code=language_code,
                first_join_time=datetime.now(MOSCOW_TZ),
                referrer_id=referrer_id if referrer_id else None,
                agreed_to_terms=False,
                successful_bookings=0,
                invited_count=0,
            )
            session.add(user)
            session.flush()
            is_new = True

            # Обновляем счетчик приглашений у реферера
            if referrer_id:
                referrer = (
                    session.query(User).filter_by(telegram_id=referrer_id).first()
                )
                if referrer:
                    referrer.invited_count += 1
        else:
            # Обновляем username, если изменился
            if username and user.username != username:
                user.username = username

        # Проверяем полноту регистрации
        is_complete = all(
            [user.full_name, user.phone, user.email, user.agreed_to_terms]
        )

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "username": user.username,
                "successful_bookings": user.successful_bookings,
                "language_code": user.language_code,
                "invited_count": user.invited_count,
                "reg_date": user.reg_date,
                "first_join_time": user.first_join_time,
                "agreed_to_terms": user.agreed_to_terms,
                "avatar": user.avatar,
                "referrer_id": user.referrer_id,
            },
            "is_new": is_new,
            "is_complete": is_complete,
        }

    try:
        return DatabaseManager.safe_execute(_check_and_add_user)
    except Exception as e:
        logger.error(f"Ошибка в check_and_add_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/users/{user_identifier}")
async def update_user(
    user_identifier: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    def _update_user(session):
        # Пробуем найти пользователя по ID или по telegram_id
        user = None

        # Сначала пробуем как обычный ID
        if user_identifier.isdigit():
            user_id = int(user_identifier)
            user = session.query(User).filter(User.id == user_id).first()

        # Если не найден, пробуем как telegram_id
        if not user and user_identifier.isdigit():
            telegram_id = int(user_identifier)
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = user_data.dict(exclude_unset=True)

        # Обрабатываем reg_date если передана как строка
        if "reg_date" in update_data and isinstance(update_data["reg_date"], str):
            try:
                update_data["reg_date"] = datetime.fromisoformat(
                    update_data["reg_date"]
                )
            except ValueError:
                del update_data["reg_date"]

        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        session.flush()
        return user

    try:
        return DatabaseManager.safe_execute(_update_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/users/{user_id}/avatar")
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Загрузка аватара пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Удаляем старый аватар, если есть
    if user.avatar:
        old_avatar_path = AVATARS_DIR / user.avatar
        if old_avatar_path.exists():
            try:
                old_avatar_path.unlink()
                logger.info(f"Удален старый аватар: {user.avatar}")
            except Exception as e:
                logger.warning(f"Не удалось удалить старый аватар: {e}")

    # Сохраняем с именем telegram_id
    avatar_filename = f"{user.telegram_id}.jpg"
    avatar_path = AVATARS_DIR / avatar_filename

    contents = await file.read()
    with open(avatar_path, "wb") as f:
        f.write(contents)

    # Обновляем запись в БД
    user.avatar = avatar_filename
    db.commit()

    logger.info(f"Загружен новый аватар для пользователя {user_id}: {avatar_filename}")

    # Возвращаем с версией для обновления на фронте
    timestamp = int(time.time() * 1000)
    return {
        "message": "Avatar uploaded successfully",
        "filename": avatar_filename,
        "avatar_url": f"/avatars/{avatar_filename}?v={timestamp}",
        "version": timestamp,
    }


@app.delete("/users/{user_id}/avatar")
async def delete_avatar(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление аватара пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = False

    # Удаляем текущий аватар
    if user.avatar:
        avatar_path = AVATARS_DIR / user.avatar
        if avatar_path.exists():
            try:
                avatar_path.unlink()
                deleted = True
                logger.info(f"Удален аватар: {user.avatar}")
            except Exception as e:
                logger.warning(f"Не удалось удалить аватар {user.avatar}: {e}")
        user.avatar = None
        db.commit()

    # Также удаляем стандартный файл аватара, если существует
    standard_path = AVATARS_DIR / f"{user.telegram_id}.jpg"
    if standard_path.exists():
        try:
            standard_path.unlink()
            deleted = True
            logger.info(f"Удален файл аватара: {standard_path.name}")
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {standard_path.name}: {e}")

    return {"deleted": deleted}


@app.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Получение аватара по имени файла с заголовками против кэширования."""
    file_path = AVATARS_DIR / filename

    if not file_path.exists():
        # Возвращаем заглушку, если файл не найден
        placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
        if placeholder_path.exists():
            return FileResponse(
                placeholder_path,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        raise HTTPException(status_code=404, detail="Avatar not found")

    # Получаем время последней модификации файла
    mtime = file_path.stat().st_mtime
    last_modified = datetime.fromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")

    # Создаем ETag на основе имени файла и времени модификации
    etag_base = f"{filename}-{mtime}"
    etag = hashlib.md5(etag_base.encode()).hexdigest()

    # Возвращаем файл с агрессивными заголовками против кэширования
    return FileResponse(
        file_path,
        headers={
            # Полностью отключаем кэширование
            "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "ETag": f'"{etag}"',
            "Last-Modified": last_modified,
            # Дополнительный заголовок для прокси-серверов
            "Surrogate-Control": "no-store",
        },
    )


@app.post("/users/{user_id}/download-telegram-avatar")
async def download_telegram_avatar(
    user_id: int,
    _: str = Depends(verify_token),
):
    """Скачивание аватара пользователя из Telegram."""
    try:
        # Получаем данные пользователя
        def _get_user_data(session):
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if not user.telegram_id:
                raise HTTPException(status_code=400, detail="User has no Telegram ID")

            # Удаляем старый аватар если есть
            if user.avatar:
                old_avatar_path = AVATARS_DIR / user.avatar
                if old_avatar_path.exists():
                    try:
                        old_avatar_path.unlink()
                        logger.info(f"Удален старый аватар: {user.avatar}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления старого аватара: {e}")

            return {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
            }

        user_data = DatabaseManager.safe_execute(_get_user_data)

        if not bot:
            raise HTTPException(status_code=503, detail="Bot not available")

        logger.info(
            f"Попытка скачать аватар для пользователя {user_data['telegram_id']}"
        )

        # Получаем фото профиля
        profile_photos = await bot.get_user_profile_photos(
            user_id=user_data["telegram_id"], limit=1
        )

        if not profile_photos.photos:
            logger.info(f"У пользователя {user_data['telegram_id']} нет фото профиля")
            raise HTTPException(
                status_code=404,
                detail="User has no profile photo or photo is not accessible",
            )

        # Берем самое большое фото
        photo = profile_photos.photos[0][-1]
        file = await bot.get_file(photo.file_id)

        # Сохраняем с именем telegram_id
        avatar_filename = f"{user_data['telegram_id']}.jpg"
        avatar_path = AVATARS_DIR / avatar_filename

        # Создаем директорию если её нет
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)

        # Если файл уже существует, удаляем его
        if avatar_path.exists():
            try:
                avatar_path.unlink()
                logger.info(f"Удален существующий аватар: {avatar_filename}")
            except Exception as e:
                logger.warning(f"Не удалось удалить существующий аватар: {e}")

        # Скачиваем файл
        await bot.download_file(file.file_path, destination=avatar_path)
        logger.info(f"Аватар сохранен: {avatar_path}")

        # Обновляем пользователя в БД
        def _update_avatar(session):
            user_obj = session.query(User).filter(User.id == user_id).first()
            if user_obj:
                user_obj.avatar = avatar_filename
                session.commit()
                return {
                    "id": user_obj.id,
                    "telegram_id": user_obj.telegram_id,
                    "avatar": user_obj.avatar,
                }
            return None

        updated_user_data = DatabaseManager.safe_execute(_update_avatar)

        if not updated_user_data:
            raise HTTPException(status_code=404, detail="Failed to update user")

        logger.info(
            f"Аватар пользователя {user_data['telegram_id']} успешно загружен: {avatar_filename}"
        )

        # Возвращаем с версией для обновления на фронте
        timestamp = int(time.time() * 1000)
        return {
            "message": "Avatar downloaded successfully",
            "avatar_filename": avatar_filename,
            "avatar_url": f"/avatars/{avatar_filename}?v={timestamp}",
            "version": timestamp,
            "user_id": updated_user_data["id"],
            "telegram_id": updated_user_data["telegram_id"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании аватара пользователя {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error downloading avatar: {str(e)}"
        )


async def save_user_avatar(bot: Bot, user_id: int) -> Optional[str]:
    """
    Сохранение аватара пользователя.

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя в Telegram

    Returns:
        Путь к сохраненному файлу или None
    """
    try:
        logger.info(f"Начинаем загрузку аватара для пользователя {user_id}")

        # Получаем фото профиля
        profile_photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)

        if not profile_photos.photos:
            logger.info(f"У пользователя {user_id} нет фото профиля")
            return None

        # Берем самое большое фото (последнее в списке)
        photo = profile_photos.photos[0][-1]
        file = await bot.get_file(photo.file_id)

        logger.info(
            f"Найдено фото профиля для пользователя {user_id}, file_path: {file.file_path}"
        )

        # Создаем директорию для аватаров если её нет
        AVATARS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Директория аватаров: {AVATARS_DIR.absolute()}")

        # Формируем путь к файлу - используем telegram_id как имя
        avatar_filename = f"{user_id}.jpg"
        file_path = AVATARS_DIR / avatar_filename

        # Скачиваем файл
        logger.info(f"Скачиваем файл из Telegram: {file.file_path}")

        # Используем метод download напрямую в файл
        await bot.download_file(file.file_path, destination=file_path)

        logger.info(f"Аватар пользователя {user_id} сохранен: {file_path}")
        return str(file_path)

    except Exception as e:
        logger.error(f"Ошибка при сохранении аватара пользователя {user_id}: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


@app.delete("/users/{user_id}")
async def delete_user(user_id: int, _: str = Depends(verify_token)):
    """Удаление пользователя и всех связанных данных."""

    def _delete_user(session):
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_name = user.full_name or f"Пользователь #{user.telegram_id}"
        telegram_id = user.telegram_id

        # Удаляем аватар, если есть
        if user.avatar:
            try:
                avatar_path = AVATARS_DIR / user.avatar
                if avatar_path.exists():
                    avatar_path.unlink()
                    logger.info(f"Удален аватар: {avatar_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить аватар: {e}")

        # Удаляем пользователя (связанные записи удалятся автоматически благодаря cascade)
        session.delete(user)

        logger.info(
            f"Удален пользователь: {user_name} (ID: {user_id}, Telegram ID: {telegram_id})"
        )

        return {
            "message": f"Пользователь {user_name} успешно удален",
            "deleted_user": {
                "id": user_id,
                "telegram_id": telegram_id,
                "full_name": user_name,
            },
        }

    try:
        return DatabaseManager.safe_execute(_delete_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления пользователя")


# ================== BOOKING ENDPOINTS ==================


@app.get("/bookings/detailed")
async def get_bookings_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: str = Depends(verify_token),
):
    """Получение бронирований с данными тарифов и пользователей (оптимизированная версия)."""

    def _get_bookings(session):
        try:
            logger.info(
                f"Запрос бронирований: page={page}, per_page={per_page}, "
                f"user_query='{user_query}', date_query='{date_query}', status_filter='{status_filter}'"
            )

            # Используем прямые SQL-запросы для лучшей производительности
            base_query = """
                SELECT 
                    b.id, b.user_id, b.tariff_id, b.visit_date, b.visit_time,
                    b.duration, b.promocode_id, b.amount, b.payment_id, b.paid,
                    b.rubitime_id, b.confirmed, b.created_at,
                    u.telegram_id, u.full_name, u.username, u.phone, u.email,
                    t.name as tariff_name, t.price as tariff_price, 
                    t.description as tariff_description, t.purpose as tariff_purpose, t.is_active
                FROM bookings b
                LEFT JOIN users u ON b.user_id = u.id
                LEFT JOIN tariffs t ON b.tariff_id = t.id
            """

            where_conditions = []
            params = {}

            # Фильтрация по пользователю
            if user_query and user_query.strip():
                where_conditions.append("u.full_name LIKE :user_query")
                params["user_query"] = f"%{user_query.strip()}%"

            # Фильтрация по дате
            if date_query and date_query.strip():
                try:
                    if date_query.count("-") == 2:
                        query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                    elif date_query.count(".") == 2:
                        query_date = datetime.strptime(date_query, "%d.%m.%Y").date()
                    else:
                        raise ValueError("Unsupported date format")

                    where_conditions.append("b.visit_date = :date_query")
                    params["date_query"] = query_date.isoformat()
                except ValueError:
                    logger.error(f"Ошибка формата даты: {date_query}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid date format. Use YYYY-MM-DD or DD.MM.YYYY",
                    )

            # Фильтрация по статусу
            if status_filter and status_filter.strip():
                if status_filter == "paid":
                    where_conditions.append("b.paid = 1")
                elif status_filter == "unpaid":
                    where_conditions.append("b.paid = 0")
                elif status_filter == "confirmed":
                    where_conditions.append("b.confirmed = 1")
                elif status_filter == "pending":
                    where_conditions.append("b.confirmed = 0")

            # Собираем финальный запрос
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            # Подсчет общего количества
            count_query = f"SELECT COUNT(*) FROM ({base_query}) as counted"
            total_count = session.execute(text(count_query), params).scalar()

            # Основной запрос с пагинацией
            final_query = (
                base_query + " ORDER BY b.created_at DESC LIMIT :limit OFFSET :offset"
            )
            params["limit"] = per_page
            params["offset"] = (page - 1) * per_page

            result = session.execute(text(final_query), params).fetchall()

            # Формируем ответ
            enriched_bookings = []
            for row in result:
                booking_item = {
                    "id": int(row.id),
                    "user_id": int(row.user_id),
                    "tariff_id": int(row.tariff_id),
                    "visit_date": row.visit_date,
                    "visit_time": row.visit_time,
                    "duration": int(row.duration) if row.duration else None,
                    "promocode_id": int(row.promocode_id) if row.promocode_id else None,
                    "amount": float(row.amount),
                    "payment_id": row.payment_id,
                    "paid": bool(row.paid),
                    "rubitime_id": row.rubitime_id,
                    "confirmed": bool(row.confirmed),
                    "created_at": row.created_at,
                    "user": {
                        "id": row.user_id,
                        "telegram_id": row.telegram_id,
                        "full_name": row.full_name or "Имя не указано",
                        "username": row.username,
                        "phone": row.phone,
                        "email": row.email,
                    },
                    "tariff": {
                        "id": row.tariff_id,
                        "name": row.tariff_name or f"Тариф #{row.tariff_id}",
                        "price": float(row.tariff_price) if row.tariff_price else 0.0,
                        "description": row.tariff_description or "Описание недоступно",
                        "purpose": row.tariff_purpose,
                        "is_active": (
                            bool(row.is_active) if row.is_active is not None else False
                        ),
                    },
                }
                enriched_bookings.append(booking_item)

            total_pages = (total_count + per_page - 1) // per_page

            return {
                "bookings": enriched_bookings,
                "total_count": int(total_count),
                "page": int(page),
                "per_page": int(per_page),
                "total_pages": int(total_pages),
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_bookings: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_bookings)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при получении бронирований: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/bookings/stats")
async def get_booking_stats(_: str = Depends(verify_token)):
    """Получение статистики по бронированиям."""

    def _get_stats(session):
        try:
            total_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings")
            ).scalar()
            paid_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE paid = 1")
            ).scalar()
            confirmed_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE confirmed = 1")
            ).scalar()

            # Общая сумма оплаченных бронирований
            total_revenue = session.execute(
                text("SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE paid = 1")
            ).scalar()

            # Статистика по текущему месяцу
            current_month_start = (
                datetime.now(MOSCOW_TZ)
                .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
            )

            current_month_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE created_at >= :start_date"),
                {"start_date": current_month_start},
            ).scalar()

            current_month_revenue = session.execute(
                text(
                    "SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE created_at >= :start_date AND paid = 1"
                ),
                {"start_date": current_month_start},
            ).scalar()

            # Топ тарифы по количеству бронирований
            top_tariffs = session.execute(
                text(
                    """
                    SELECT t.name, COUNT(b.id) as booking_count
                    FROM tariffs t
                    JOIN bookings b ON t.id = b.tariff_id
                    GROUP BY t.id, t.name
                    ORDER BY booking_count DESC
                    LIMIT 5
                """
                )
            ).fetchall()

            return {
                "total_bookings": total_bookings,
                "paid_bookings": paid_bookings,
                "confirmed_bookings": confirmed_bookings,
                "total_revenue": float(total_revenue),
                "current_month_bookings": current_month_bookings,
                "current_month_revenue": float(current_month_revenue),
                "top_tariffs": [
                    {"name": row.name, "count": row.booking_count}
                    for row in top_tariffs
                ],
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_stats: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики бронирований: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# 3. БАЗОВЫЙ маршрут /bookings (список)
@app.get("/bookings", response_model=List[BookingBase])
async def get_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение списка бронирований с пагинацией и фильтрацией."""
    query = db.query(Booking).order_by(Booking.created_at.desc())

    # Фильтрация по пользователю
    if user_query:
        query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))

    # Фильтрация по дате
    if date_query:
        try:
            query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
            query = query.filter(Booking.visit_date == query_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    bookings = query.offset((page - 1) * per_page).limit(per_page).all()
    return bookings


@app.post("/bookings", response_model=BookingBase)
async def create_booking(booking_data: BookingCreate):
    """Создание бронирования с улучшенной обработкой промокодов."""

    def _create_booking(session):
        logger.info(
            f"Создание бронирования: user_id={booking_data.user_id}, "
            f"tariff_id={booking_data.tariff_id}, promocode_id={booking_data.promocode_id}"
        )

        # Находим пользователя
        user = (
            session.query(User).filter(User.telegram_id == booking_data.user_id).first()
        )
        if not user:
            logger.error(f"Пользователь с telegram_id {booking_data.user_id} не найден")
            raise HTTPException(status_code=404, detail="User not found")

        # Находим тариф
        tariff = (
            session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        )
        if not tariff:
            logger.error(f"Тариф с ID {booking_data.tariff_id} не найден")
            raise HTTPException(status_code=404, detail="Tariff not found")

        amount = booking_data.amount
        promocode = None

        # Обработка промокода
        if booking_data.promocode_id:
            logger.info(f"Обработка промокода ID: {booking_data.promocode_id}")

            promocode = (
                session.query(Promocode)
                .filter(Promocode.id == booking_data.promocode_id)
                .first()
            )

            if not promocode:
                logger.error(f"Промокод с ID {booking_data.promocode_id} не найден")
                raise HTTPException(status_code=404, detail="Promocode not found")

            logger.info(
                f"Найден промокод: {promocode.name}, скидка: {promocode.discount}%, "
                f"осталось использований: {promocode.usage_quantity}"
            )

            # Проверяем доступность промокода
            if not promocode.is_active:
                logger.warning(f"Промокод {promocode.name} неактивен")
                raise HTTPException(status_code=400, detail="Promocode is not active")

            if promocode.expiration_date and promocode.expiration_date < datetime.now(
                MOSCOW_TZ
            ):
                logger.warning(f"Промокод {promocode.name} истек")
                raise HTTPException(status_code=410, detail="Promocode expired")

            if promocode.usage_quantity <= 0:
                logger.warning(f"Промокод {promocode.name} исчерпан")
                raise HTTPException(
                    status_code=410, detail="Promocode usage limit exceeded"
                )

            # Пересчитываем сумму с учетом скидки
            original_amount = amount
            amount = amount * (1 - promocode.discount / 100)
            logger.info(
                f"Сумма пересчитана: {original_amount} -> {amount} (скидка {promocode.discount}%)"
            )

            # Уменьшаем счетчик использований промокода
            old_usage = promocode.usage_quantity
            promocode.usage_quantity -= 1
            logger.info(
                f"🎫 ПРОМОКОД {promocode.name}: использований было {old_usage}, стало {promocode.usage_quantity}"
            )

        # Создаем бронирование
        booking = Booking(
            user_id=user.id,
            tariff_id=tariff.id,
            visit_date=booking_data.visit_date,
            visit_time=booking_data.visit_time,
            duration=booking_data.duration,
            promocode_id=booking_data.promocode_id,
            amount=amount,
            payment_id=booking_data.payment_id,
            paid=booking_data.paid,
            confirmed=booking_data.confirmed,
            rubitime_id=booking_data.rubitime_id,
        )

        session.add(booking)
        session.flush()  # Получаем ID бронирования

        # Создаем уведомление в БД
        notification = Notification(
            user_id=user.id,
            message=f"Создана новая бронь от {user.full_name or 'пользователя'}",
            target_url=f"/bookings/{booking.id}",
            booking_id=booking.id,
        )
        session.add(notification)

        # Обновляем счетчик успешных бронирований ТОЛЬКО если оплачено
        if booking_data.paid:
            old_bookings = user.successful_bookings or 0
            user.successful_bookings = old_bookings + 1
            logger.info(
                f"👤 Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        logger.info(f"✅ Создано бронирование #{booking.id} с суммой {amount} ₽")

        if promocode:
            logger.info(
                f"✅ Промокод {promocode.name} успешно использован, осталось: {promocode.usage_quantity}"
            )

        # ИСПРАВЛЕНИЕ: Возвращаем словарь вместо SQLAlchemy объекта
        # Это решает проблему DetachedInstanceError
        booking_dict = {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date,
            "visit_time": booking.visit_time,
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),
            "payment_id": booking.payment_id,
            "paid": booking.paid,
            "rubitime_id": booking.rubitime_id,
            "confirmed": booking.confirmed,
            "created_at": booking.created_at,
        }

        return booking_dict

    try:
        return DatabaseManager.safe_execute(_create_booking)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бронирования: {e}")
        raise HTTPException(status_code=500, detail="Failed to create booking")


# 5. ТЕПЕРЬ ДИНАМИЧЕСКИЕ маршруты с {booking_id}
# Маршрут для валидации ID (опциональный)
@app.get("/bookings/{booking_id}/validate")
async def validate_booking_id(
    booking_id: str, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Проверка существования бронирования по ID."""
    try:
        booking_id_int = int(booking_id)
        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail="Booking ID must be positive")

        booking = db.query(Booking).filter(Booking.id == booking_id_int).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return {
            "id": booking.id,
            "exists": True,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "paid": booking.paid,
            "confirmed": booking.confirmed,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка валидации booking ID {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Validation error")


# Маршрут для детальной информации о конкретном бронировании
@app.get("/bookings/{booking_id}/detailed")
async def get_booking_detailed(
    booking_id: str,  # Изменено с int на str для гибкости
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение детальной информации о конкретном бронировании."""
    try:
        # Пробуем преобразовать в int с валидацией
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")

        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail="Booking ID must be positive")

        # Сначала получаем само бронирование
        booking = db.query(Booking).filter(Booking.id == booking_id_int).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Получаем связанные объекты по отдельности с проверками
        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()
        promocode = None

        if booking.promocode_id:
            promocode = (
                db.query(Promocode).filter(Promocode.id == booking.promocode_id).first()
            )

        # Формируем ответ с безопасными проверками
        booking_detail = {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date.isoformat(),
            "visit_time": (
                booking.visit_time.isoformat() if booking.visit_time else None
            ),
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),  # Принудительно преобразуем в float
            "payment_id": booking.payment_id,
            "paid": bool(booking.paid),  # Принудительно преобразуем в bool
            "rubitime_id": booking.rubitime_id,
            "confirmed": bool(booking.confirmed),  # Принудительно преобразуем в bool
            "created_at": booking.created_at.isoformat(),
            # Детальная информация о пользователе (с fallback)
            "user": (
                {
                    "id": user.id if user else booking.user_id,
                    "telegram_id": user.telegram_id if user else None,
                    "full_name": user.full_name if user else "Пользователь не найден",
                    "phone": user.phone if user else None,
                    "email": user.email if user else None,
                    "username": user.username if user else None,
                    "successful_bookings": user.successful_bookings if user else 0,
                    "language_code": user.language_code if user else "ru",
                    "invited_count": user.invited_count if user else 0,
                    "reg_date": (
                        user.reg_date.isoformat() if user and user.reg_date else None
                    ),
                    "first_join_time": (
                        user.first_join_time.isoformat() if user else None
                    ),
                    "agreed_to_terms": bool(user.agreed_to_terms) if user else False,
                    "avatar": user.avatar if user else None,
                    "referrer_id": user.referrer_id if user else None,
                }
                if user
                else {
                    "id": booking.user_id,
                    "telegram_id": None,
                    "full_name": "Пользователь не найден",
                    "phone": None,
                    "email": None,
                    "username": None,
                    "successful_bookings": 0,
                    "language_code": "ru",
                    "invited_count": 0,
                    "reg_date": None,
                    "first_join_time": None,
                    "agreed_to_terms": False,
                    "avatar": None,
                    "referrer_id": None,
                }
            ),
            # Детальная информация о тарифе (с fallback)
            "tariff": (
                {
                    "id": tariff.id if tariff else booking.tariff_id,
                    "name": tariff.name if tariff else "Тариф не найден",
                    "description": (
                        tariff.description if tariff else "Описание недоступно"
                    ),
                    "price": (
                        float(tariff.price) if tariff else 0.0
                    ),  # Принудительно float
                    "purpose": tariff.purpose if tariff else None,
                    "service_id": tariff.service_id if tariff else None,
                    "is_active": bool(tariff.is_active) if tariff else False,
                }
                if tariff
                else {
                    "id": booking.tariff_id,
                    "name": "Тариф не найден",
                    "description": "Описание недоступно",
                    "price": 0.0,
                    "purpose": None,
                    "service_id": None,
                    "is_active": False,
                }
            ),
            # Информация о промокоде (если есть)
            "promocode": (
                {
                    "id": promocode.id,
                    "name": promocode.name,
                    "discount": int(promocode.discount),  # Принудительно int
                    "usage_quantity": int(
                        promocode.usage_quantity
                    ),  # Принудительно int
                    "expiration_date": (
                        promocode.expiration_date.isoformat()
                        if promocode.expiration_date
                        else None
                    ),
                    "is_active": bool(promocode.is_active),
                }
                if promocode
                else None
            ),
        }

        return booking_detail

    except HTTPException:
        # Переподнимаем HTTP исключения
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении детального бронирования {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# 6. Остальные динамические маршруты
@app.get("/bookings/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение бронирования по ID."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


# ОБНОВЛЕННЫЙ PUT endpoint - ЗАМЕНЯЕТ СТАРУЮ ВЕРСИЮ
@app.put("/bookings/{booking_id}")
async def update_booking(
    booking_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление статуса бронирования (подтверждение/оплата)."""
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Получаем связанные объекты
        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not tariff:
            raise HTTPException(status_code=404, detail="Tariff not found")

        # Сохраняем старые значения для проверки изменений
        old_confirmed = booking.confirmed
        old_paid = booking.paid

        # Обновляем статусы
        if "confirmed" in update_data:
            booking.confirmed = update_data["confirmed"]

        if "paid" in update_data:
            booking.paid = update_data["paid"]

        # Если подтверждаем бронирование И у нас нет записи в Rubitime - создаем её
        if (
            "confirmed" in update_data
            and update_data["confirmed"]
            and not old_confirmed
            and not booking.rubitime_id
            and tariff.service_id
        ):

            try:
                logger.info(
                    f"Создание записи Rubitime для подтвержденной брони #{booking.id}"
                )

                # Форматируем телефон для Rubitime
                def format_phone_for_rubitime(phone: str) -> str:
                    if not phone:
                        return "Не указано"

                    import re

                    digits = re.sub(r"[^0-9]", "", phone)

                    if len(digits) == 11 and digits.startswith("8"):
                        digits = "7" + digits[1:]
                    elif len(digits) == 10:
                        digits = "7" + digits
                    elif len(digits) == 11 and digits.startswith("7"):
                        pass
                    else:
                        return "Не указано"

                    if len(digits) == 11:
                        return "+" + digits
                    else:
                        return "Не указано"

                formatted_phone = format_phone_for_rubitime(user.phone or "")

                if formatted_phone != "Не указано":
                    # Формируем дату и время для Rubitime
                    if booking.visit_time and booking.duration:
                        rubitime_date = datetime.combine(
                            booking.visit_date, booking.visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = booking.duration * 60
                    else:
                        rubitime_date = (
                            booking.visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        )
                        rubitime_duration = None

                    # Формируем комментарий
                    comment_parts = [
                        f"Подтвержденная бронь через Telegram бота - {tariff.name}"
                    ]

                    # Добавляем информацию о промокоде если есть
                    if booking.promocode_id:
                        promocode = (
                            db.query(Promocode)
                            .filter(Promocode.id == booking.promocode_id)
                            .first()
                        )
                        if promocode:
                            comment_parts.append(
                                f"Промокод: {promocode.name} (-{promocode.discount}%)"
                            )

                    # Добавляем информацию о длительности для переговорных
                    if booking.duration and booking.duration > 1:
                        comment_parts.append(
                            f"Длительность: {booking.duration} час(ов)"
                        )

                    final_comment = " | ".join(comment_parts)

                    rubitime_params = {
                        "service_id": tariff.service_id,
                        "date": rubitime_date,
                        "phone": formatted_phone,
                        "name": user.full_name or "Клиент",
                        "comment": final_comment,
                        "source": "Telegram Bot Admin",
                    }

                    if rubitime_duration is not None:
                        rubitime_params["duration"] = rubitime_duration

                    if user.email and user.email.strip():
                        rubitime_params["email"] = user.email.strip()

                    logger.info(f"Параметры для Rubitime: {rubitime_params}")

                    # Создаем запись в Rubitime
                    rubitime_id = await rubitime("create_record", rubitime_params)

                    if rubitime_id:
                        booking.rubitime_id = str(rubitime_id)
                        logger.info(
                            f"✅ Создана запись Rubitime #{booking.rubitime_id} для подтвержденной брони #{booking.id}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Не удалось создать запись в Rubitime для брони #{booking.id}"
                        )

            except Exception as e:
                logger.error(
                    f"❌ Ошибка создания записи в Rubitime при подтверждении брони #{booking.id}: {e}"
                )
                # Не блокируем подтверждение из-за ошибки Rubitime

        # Обновляем счетчик успешных бронирований при отметке как оплачено
        if (
            "paid" in update_data
            and update_data["paid"]
            and not old_paid
            and tariff.purpose
            and tariff.purpose.lower() in ["опенспейс", "coworking"]
        ):
            old_bookings = user.successful_bookings or 0
            user.successful_bookings = old_bookings + 1
            logger.info(
                f"👤 Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        # Сохраняем изменения
        db.commit()
        db.refresh(booking)

        # Отправляем уведомления пользователю через бота
        if bot and user.telegram_id:
            try:
                if (
                    "confirmed" in update_data
                    and update_data["confirmed"]
                    and not old_confirmed
                ):
                    # Уведомление о подтверждении
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )
                    duration_str = f" ({booking.duration}ч)" if booking.duration else ""

                    message = f"""✅ <b>Ваша бронь подтверждена!</b>

📋 <b>Тариф:</b> {tariff.name}
📅 <b>Дата:</b> {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}{duration_str}
💰 <b>Сумма:</b> {booking.amount:.2f} ₽

💡 <b>Что дальше:</b> Ждем вас в назначенное время!"""

                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")
                    logger.info(
                        f"📤 Отправлено уведомление о подтверждении пользователю {user.telegram_id}"
                    )

                elif "paid" in update_data and update_data["paid"] and not old_paid:
                    # Уведомление об оплате
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )

                    message = f"""💳 <b>Оплата зачислена!</b>

📋 <b>Тариф:</b> {tariff.name}
📅 <b>Дата:</b> {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}
💰 <b>Сумма:</b> {booking.amount:.2f} ₽

✅ Ваша оплата успешно обработана и зачислена."""

                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")
                    logger.info(
                        f"📤 Отправлено уведомление об оплате пользователю {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"❌ Не удалось отправить уведомление пользователю {user.telegram_id}: {e}"
                )

        # Возвращаем обновленное бронирование
        return {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date.isoformat(),
            "visit_time": (
                booking.visit_time.isoformat() if booking.visit_time else None
            ),
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),
            "payment_id": booking.payment_id,
            "paid": bool(booking.paid),
            "rubitime_id": booking.rubitime_id,
            "confirmed": bool(booking.confirmed),
            "created_at": booking.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка обновления бронирования {booking_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/bookings/{booking_id}")
async def delete_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление бронирования."""
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted"}


# ================== TARIFF ENDPOINTS ==================


@app.get("/tariffs/active")
async def get_active_tariffs(db: Session = Depends(get_db)):
    """Получение активных тарифов. Используется ботом."""
    tariffs = db.query(Tariff).filter_by(is_active=True).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "price": t.price,
            "purpose": t.purpose,
            "service_id": t.service_id,
            "is_active": t.is_active,
        }
        for t in tariffs
    ]


@app.get("/tariffs", response_model=List[TariffBase])
async def get_tariffs(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение всех тарифов."""
    tariffs = db.query(Tariff).order_by(Tariff.id.desc()).all()
    return tariffs


@app.get("/tariffs/{tariff_id}")
async def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    """Получение тарифа по ID. Используется ботом и админкой."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    return {
        "id": tariff.id,
        "name": tariff.name,
        "description": tariff.description,
        "price": tariff.price,
        "purpose": tariff.purpose,
        "service_id": tariff.service_id,
        "is_active": tariff.is_active,
    }


@app.post("/tariffs", response_model=TariffBase)
async def create_tariff(
    tariff_data: TariffCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создание нового тарифа."""

    # Валидация названия
    if not tariff_data.name or len(tariff_data.name.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Название тарифа должно содержать минимум 3 символа"
        )

    if len(tariff_data.name) > 64:
        raise HTTPException(
            status_code=400, detail="Название тарифа не должно превышать 64 символа"
        )

    # Валидация описания
    if not tariff_data.description or len(tariff_data.description.strip()) < 1:
        raise HTTPException(status_code=400, detail="Описание тарифа обязательно")

    if len(tariff_data.description) > 255:
        raise HTTPException(
            status_code=400, detail="Описание не должно превышать 255 символов"
        )

    # Валидация цены
    if tariff_data.price < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")

    # Валидация service_id
    if tariff_data.service_id is not None and tariff_data.service_id < 1:
        raise HTTPException(
            status_code=400, detail="Service ID должен быть положительным числом"
        )

    try:
        tariff = Tariff(
            name=tariff_data.name.strip(),
            description=tariff_data.description.strip(),
            price=tariff_data.price,
            purpose=tariff_data.purpose,
            service_id=tariff_data.service_id,
            is_active=tariff_data.is_active,
        )

        db.add(tariff)
        db.commit()
        db.refresh(tariff)

        logger.info(f"Создан тариф: {tariff.name} ({tariff.price}₽)")
        return tariff

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания тарифа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать тариф")


@app.put("/tariffs/{tariff_id}", response_model=TariffBase)
async def update_tariff(
    tariff_id: int,
    tariff_data: TariffUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление тарифа."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    # Обновляем только переданные поля
    update_data = tariff_data.dict(exclude_unset=True)

    # Валидация названия
    if "name" in update_data:
        if not update_data["name"] or len(update_data["name"].strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Название тарифа должно содержать минимум 3 символа",
            )
        if len(update_data["name"]) > 64:
            raise HTTPException(
                status_code=400, detail="Название тарифа не должно превышать 64 символа"
            )
        update_data["name"] = update_data["name"].strip()

    # Валидация описания
    if "description" in update_data:
        if (
            not update_data["description"]
            or len(update_data["description"].strip()) < 1
        ):
            raise HTTPException(status_code=400, detail="Описание тарифа обязательно")
        if len(update_data["description"]) > 255:
            raise HTTPException(
                status_code=400, detail="Описание не должно превышать 255 символов"
            )
        update_data["description"] = update_data["description"].strip()

    # Валидация цены
    if "price" in update_data:
        if update_data["price"] < 0:
            raise HTTPException(
                status_code=400, detail="Цена не может быть отрицательной"
            )

    # Валидация service_id
    if "service_id" in update_data and update_data["service_id"] is not None:
        if update_data["service_id"] < 1:
            raise HTTPException(
                status_code=400, detail="Service ID должен быть положительным числом"
            )

    try:
        # Применяем изменения
        for field, value in update_data.items():
            setattr(tariff, field, value)

        db.commit()
        db.refresh(tariff)

        logger.info(f"Обновлен тариф: {tariff.name}")
        return tariff

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить тариф")


@app.delete("/tariffs/{tariff_id}")
async def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тарифа."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    # Проверяем, используется ли тариф в активных бронированиях
    active_bookings = db.query(Booking).filter_by(tariff_id=tariff_id).count()
    if active_bookings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить тариф. Он используется в {active_bookings} бронированиях. "
            f"Вместо удаления рекомендуется отключить тариф.",
        )

    try:
        tariff_name = tariff.name
        db.delete(tariff)
        db.commit()

        logger.info(f"Удален тариф: {tariff_name}")
        return {"message": f"Тариф '{tariff_name}' удален"}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить тариф")


# ================== PROMOCODE ENDPOINTS ==================


@app.get("/promocodes", response_model=List[PromocodeBase])
async def get_promocodes(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение всех промокодов."""
    promocodes = db.query(Promocode).order_by(Promocode.id.desc()).all()
    return promocodes


@app.get("/promocodes/by_name/{name}")
async def get_promocode_by_name(name: str, db: Session = Depends(get_db)):
    """Получение промокода по названию. Используется ботом."""
    promocode = db.query(Promocode).filter_by(name=name, is_active=True).first()
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    # Проверяем срок действия
    if promocode.expiration_date and promocode.expiration_date < datetime.now(
        MOSCOW_TZ
    ):
        raise HTTPException(status_code=410, detail="Promocode expired")

    # Проверяем количество использований
    if promocode.usage_quantity <= 0:
        raise HTTPException(status_code=410, detail="Promocode usage limit exceeded")

    return {
        "id": promocode.id,
        "name": promocode.name,
        "discount": promocode.discount,
        "usage_quantity": promocode.usage_quantity,
        "expiration_date": promocode.expiration_date,
        "is_active": promocode.is_active,
    }


@app.get("/promocodes/{promocode_id}", response_model=PromocodeBase)
async def get_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение промокода по ID."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return promocode


@app.post("/promocodes", response_model=PromocodeBase)
async def create_promocode(
    promocode_data: PromocodeCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создание нового промокода."""

    # Валидация названия
    if not promocode_data.name or len(promocode_data.name.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Название промокода должно содержать минимум 3 символа",
        )

    if len(promocode_data.name) > 20:
        raise HTTPException(
            status_code=400, detail="Название промокода не должно превышать 20 символов"
        )

    # Проверяем формат названия (только латинские буквы, цифры, дефис и подчеркивание)
    if not re.match(r"^[A-Za-z0-9_-]+$", promocode_data.name):
        raise HTTPException(
            status_code=400,
            detail="Название может содержать только латинские буквы, цифры, дефис и подчеркивание",
        )

    # Проверяем уникальность названия
    existing = db.query(Promocode).filter_by(name=promocode_data.name.upper()).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Промокод с названием '{promocode_data.name}' уже существует",
        )

    # Валидация скидки
    if promocode_data.discount < 1 or promocode_data.discount > 100:
        raise HTTPException(status_code=400, detail="Скидка должна быть от 1% до 100%")

    # Валидация количества использований
    if promocode_data.usage_quantity < 0:
        raise HTTPException(
            status_code=400,
            detail="Количество использований не может быть отрицательным",
        )

    # Проверяем дату истечения
    if promocode_data.expiration_date:
        if promocode_data.expiration_date.date() < datetime.now(MOSCOW_TZ).date():
            raise HTTPException(
                status_code=400, detail="Дата истечения не может быть в прошлом"
            )

    try:
        promocode = Promocode(
            name=promocode_data.name.upper(),
            discount=promocode_data.discount,
            usage_quantity=promocode_data.usage_quantity,
            expiration_date=promocode_data.expiration_date,
            is_active=promocode_data.is_active,
        )

        db.add(promocode)
        db.commit()
        db.refresh(promocode)

        logger.info(f"Создан промокод: {promocode.name} ({promocode.discount}%)")
        return promocode

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания промокода: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать промокод")


@app.put("/promocodes/{promocode_id}", response_model=PromocodeBase)
async def update_promocode(
    promocode_id: int,
    promocode_data: PromocodeUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление промокода."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    # Обновляем только переданные поля
    update_data = promocode_data.dict(exclude_unset=True)

    # Валидация названия на уникальность (если оно изменяется)
    if "name" in update_data:
        new_name = update_data["name"].upper()
        if new_name != promocode.name:
            existing = db.query(Promocode).filter_by(name=new_name).first()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Промокод с названием '{new_name}' уже существует",
                )

        # Валидация формата названия
        if not re.match(r"^[A-Za-z0-9_-]+$", new_name):
            raise HTTPException(
                status_code=400,
                detail="Название может содержать только латинские буквы, цифры, дефис и подчеркивание",
            )

        if len(new_name) < 3 or len(new_name) > 20:
            raise HTTPException(
                status_code=400, detail="Название должно содержать от 3 до 20 символов"
            )

        update_data["name"] = new_name

    # Валидация скидки
    if "discount" in update_data:
        if update_data["discount"] < 1 or update_data["discount"] > 100:
            raise HTTPException(
                status_code=400, detail="Скидка должна быть от 1% до 100%"
            )

    # Валидация количества использований
    if "usage_quantity" in update_data:
        if update_data["usage_quantity"] < 0:
            raise HTTPException(
                status_code=400,
                detail="Количество использований не может быть отрицательным",
            )

    # Валидация даты истечения
    if "expiration_date" in update_data and update_data["expiration_date"]:
        if update_data["expiration_date"].date() < datetime.now(MOSCOW_TZ).date():
            raise HTTPException(
                status_code=400, detail="Дата истечения не может быть в прошлом"
            )

    try:
        # Применяем изменения
        for field, value in update_data.items():
            setattr(promocode, field, value)

        db.commit()
        db.refresh(promocode)

        logger.info(f"Обновлен промокод: {promocode.name}")
        return promocode

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить промокод")


@app.post("/promocodes/{promocode_id}/use")
async def use_promocode(promocode_id: int, db: Session = Depends(get_db)):
    """Использование промокода (уменьшение счетчика). Используется ботом при создании брони."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    if not promocode.is_active:
        raise HTTPException(status_code=400, detail="Promocode is not active")

    if promocode.expiration_date and promocode.expiration_date < datetime.now(
        MOSCOW_TZ
    ):
        raise HTTPException(status_code=410, detail="Promocode expired")

    if promocode.usage_quantity <= 0:
        raise HTTPException(status_code=410, detail="Promocode usage limit exceeded")

    try:
        # Уменьшаем количество использований
        promocode.usage_quantity -= 1
        db.commit()

        logger.info(
            f"Использован промокод {promocode.name}. Осталось использований: {promocode.usage_quantity}"
        )

        return {
            "message": "Promocode used successfully",
            "remaining_uses": promocode.usage_quantity,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка использования промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to use promocode")


@app.delete("/promocodes/{promocode_id}")
async def delete_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление промокода."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    # Проверяем, используется ли промокод в активных бронированиях
    active_bookings = db.query(Booking).filter_by(promocode_id=promocode_id).count()
    if active_bookings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить промокод. Он используется в {active_bookings} бронированиях",
        )

    try:
        promocode_name = promocode.name
        db.delete(promocode)
        db.commit()

        logger.info(f"Удален промокод: {promocode_name}")
        return {"message": f"Промокод '{promocode_name}' удален"}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить промокод")


# ================== EXTERNAL API HELPERS ==================


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    """
    Функция для работы с Rubitime API согласно их документации
    """
    if not RUBITIME_API_KEY:
        logger.warning("RUBITIME_API_KEY не настроен")
        return None

    try:
        if method == "create_record":
            url = f"{RUBITIME_BASE_URL}create-record"

            # Проверяем обязательные поля
            required_fields = ["service_id", "date", "phone", "name"]
            for field in required_fields:
                if field not in extra_params or not extra_params[field]:
                    logger.error(f"Rubitime: отсутствует обязательное поле {field}")
                    return None

            # Формируем параметры согласно документации Rubitime
            params = {
                "rk": RUBITIME_API_KEY,
                "branch_id": RUBITIME_BRANCH_ID,
                "cooperator_id": RUBITIME_COOPERATOR_ID,
                "service_id": int(extra_params["service_id"]),
                "status": 0,
                "record": extra_params["date"],  # ДАТА ЗАПИСИ
                "name": extra_params["name"],
                "phone": extra_params["phone"],
                "comment": extra_params.get("comment", ""),
                "source": extra_params.get(
                    "source", "Telegram Bot"
                ),  # Используем source из параметров
            }

            # Добавляем email если передан
            if extra_params.get("email"):
                params["email"] = extra_params["email"]
                logger.info(
                    f"Email добавлен в запрос Rubitime: {extra_params['email']}"
                )
            else:
                logger.info("Email не передан в параметрах Rubitime")

            # Добавляем duration только если он есть
            if extra_params.get("duration") is not None:
                params["duration"] = int(extra_params["duration"])

            logger.info(f"Отправляем запрос в Rubitime: {url}")
            logger.info(f"Source в параметрах: '{params.get('source')}'")
            logger.info(f"Email в параметрах: '{params.get('email', 'НЕТ')}'")
            logger.info(f"Все параметры запроса: {params}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params) as response:
                    response_text = await response.text()
                    logger.info(f"Ответ Rubitime ({response.status}): {response_text}")

                    if response.status == 200:
                        try:
                            data = await response.json()
                            if (
                                data.get("status") == "success"
                                or data.get("status") == "ok"
                            ):
                                # Ищем ID в ответе
                                record_id = None
                                data_section = data.get("data")

                                if isinstance(data_section, dict):
                                    record_id = data_section.get("id")
                                elif (
                                    isinstance(data_section, list)
                                    and len(data_section) > 0
                                ):
                                    if isinstance(data_section[0], dict):
                                        record_id = data_section[0].get("id")
                                    else:
                                        record_id = data_section[0]
                                elif data.get("id"):
                                    record_id = data.get("id")

                                logger.info(
                                    f"Успешно создана запись Rubitime с ID: {record_id}"
                                )

                                # Проверяем, что создалась запись с правильными данными
                                url_created = (
                                    data_section.get("url")
                                    if isinstance(data_section, dict)
                                    else None
                                )
                                if url_created:
                                    logger.info(f"URL созданной записи: {url_created}")

                                return str(record_id) if record_id else None
                            else:
                                error_msg = data.get("message", "Неизвестная ошибка")
                                logger.warning(f"Ошибка Rubitime: {error_msg}")
                                logger.warning(f"Полный ответ Rubitime: {data}")
                                return None
                        except Exception as e:
                            logger.error(f"Ошибка парсинга ответа Rubitime: {e}")
                            logger.error(f"Сырой ответ: {response_text}")
                            return None
                    else:
                        logger.warning(
                            f"Rubitime вернул статус {response.status}: {response_text}"
                        )
                        return None

    except Exception as e:
        logger.error(f"Ошибка запроса к Rubitime: {e}")
        return None


@app.post("/rubitime/create_record")
async def create_rubitime_record_from_bot(rubitime_params: dict):
    """
    Создает запись в Rubitime (вызывается из бота)
    """
    try:
        logger.info(f"Получен запрос на создание записи Rubitime: {rubitime_params}")

        # Проверяем наличие email и source
        logger.info(f"Email в запросе: '{rubitime_params.get('email', 'ОТСУТСТВУЕТ')}'")
        logger.info(
            f"Source в запросе: '{rubitime_params.get('source', 'ОТСУТСТВУЕТ')}'"
        )

        # НЕ перезаписываем source, если он уже передан
        if "source" not in rubitime_params:
            rubitime_params["source"] = "Telegram Bot"

        logger.info(
            f"Финальные параметры перед отправкой в rubitime(): {rubitime_params}"
        )

        result = await rubitime("create_record", rubitime_params)

        if result:
            logger.info(f"Успешно создана запись Rubitime с ID: {result}")
            return {"rubitime_id": result}
        else:
            logger.warning("Не удалось создать запись в Rubitime")
            raise HTTPException(
                status_code=400, detail="Не удалось создать запись в Rubitime"
            )

    except Exception as e:
        logger.error(f"Ошибка создания записи Rubitime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== PAYMENT ENDPOINTS ==================


@app.post("/payments")
async def create_payment(payment_data: dict, db: Session = Depends(get_db)):
    """Создание платежа через YooKassa. Используется ботом."""
    try:
        # Находим пользователя по telegram_id
        user_id = payment_data.get("user_id")
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Находим тариф
        tariff_id = payment_data.get("tariff_id")
        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            raise HTTPException(status_code=404, detail="Tariff not found")

        # Создаем платеж в YooKassa
        payment = Payment.create(
            {
                "amount": {
                    "value": f"{payment_data.get('amount', 0):.2f}",
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://t.me/your_bot",
                },
                "capture": True,
                "description": payment_data.get("description", "Оплата бронирования"),
            }
        )

        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status,
        }

    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        raise HTTPException(status_code=500, detail="Payment creation failed")


@app.get("/payments/{payment_id}/status")
async def check_payment_status_api(payment_id: str, _: str = Depends(verify_token)):
    """Проверка статуса платежа."""
    try:
        payment = Payment.find_one(payment_id)
        return {"status": payment.status}
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        raise HTTPException(status_code=500, detail="Payment status check failed")


@app.post("/payments/{payment_id}/cancel")
async def cancel_payment_api(payment_id: str, _: str = Depends(verify_token)):
    """Отмена платежа."""
    try:
        payment = Payment.find_one(payment_id)
        refund = Refund.create({"payment_id": payment_id, "amount": payment.amount})
        return {"status": refund.status}
    except Exception as e:
        logger.error(f"Ошибка отмены платежа: {e}")
        raise HTTPException(status_code=500, detail="Payment cancellation failed")


# ================== NOTIFICATION ENDPOINTS ==================


@app.get("/notifications", response_model=List[NotificationBase])
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: Optional[str] = None,  # read, unread
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение всех уведомлений с пагинацией и фильтрацией."""
    query = db.query(Notification).order_by(Notification.created_at.desc())

    # Фильтрация по статусу прочтения
    if status == "read":
        query = query.filter(Notification.is_read == True)
    elif status == "unread":
        query = query.filter(Notification.is_read == False)

    # Пагинация
    notifications = query.offset((page - 1) * per_page).limit(per_page).all()
    return notifications


@app.get("/notifications/check_new")
async def check_new_notifications(
    since_id: int = Query(0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Проверка новых уведомлений с определенного ID."""
    query = db.query(Notification).order_by(Notification.created_at.desc())

    if since_id > 0:
        query = query.filter(Notification.id > since_id)

    notifications = query.limit(5).all()

    return {
        "has_new": len(notifications) > 0,
        "recent_notifications": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "message": n.message,
                "booking_id": n.booking_id,
                "ticket_id": n.ticket_id,
                "target_url": n.target_url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


@app.get("/notifications/{notification_id}")
async def get_notification(
    notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение конкретного уведомления."""
    notification = db.query(Notification).get(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@app.post("/notifications/mark_read/{notification_id}")
async def mark_notification_read(
    notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Пометить уведомление как прочитанное."""
    notification = (
        db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    logger.info(f"Уведомление #{notification_id} помечено как прочитанное")
    return {"message": "Notification marked as read"}


@app.post("/notifications/mark_all_read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Пометить все уведомления как прочитанные."""
    try:
        updated_count = (
            db.query(Notification).filter(Notification.is_read == False).count()
        )
        db.query(Notification).update({"is_read": True})
        db.commit()

        logger.info(f"Помечено как прочитанное {updated_count} уведомлений")
        return {
            "message": "All notifications marked as read",
            "updated_count": updated_count,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при пометке всех уведомлений: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to mark all notifications as read"
        )


@app.delete("/notifications/clear_all")
async def clear_all_notifications(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удалить все уведомления."""
    try:
        deleted_count = db.query(Notification).count()
        db.query(Notification).delete()
        db.commit()

        logger.info(f"Удалено {deleted_count} уведомлений")
        return {"message": "All notifications cleared", "deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при очистке уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear notifications")


@app.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удалить конкретное уведомление."""
    notification = db.query(Notification).get(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    try:
        db.delete(notification)
        db.commit()

        logger.info(f"Удалено уведомление #{notification_id}")
        return {"message": "Notification deleted"}
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления уведомления {notification_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete notification")


@app.post("/notifications/create")
async def create_notification(
    notification_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создать уведомление в БД (для отображения в админке)"""

    user_id = notification_data.get("user_id")
    message = notification_data.get("message")
    target_url = notification_data.get("target_url")
    booking_id = notification_data.get("booking_id")
    ticket_id = notification_data.get("ticket_id")

    # Проверяем существование пользователя
    user = None
    if user_id:
        user = db.query(User).get(user_id)
        if not user:
            # Если передан user_id как telegram_id, пытаемся найти по нему
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                user_id = user.id

    # Создаем уведомление в БД
    notification = Notification(
        user_id=user_id,
        message=message,
        target_url=target_url,
        booking_id=booking_id,
        ticket_id=ticket_id,
        created_at=datetime.now(MOSCOW_TZ),
        is_read=False,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return {
        "success": True,
        "notification_id": notification.id,
        "created_at": notification.created_at,
    }


# ================== NEWSLETTER ENDPOINTS ==================


@app.post("/newsletters/send")
async def send_newsletter(
    message: str = Form(...),
    recipient_type: str = Form(...),
    user_ids: Optional[List[str]] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    _: str = Depends(verify_token),
):
    """Отправка рассылки пользователям через Telegram бота."""

    if not bot:
        raise HTTPException(status_code=503, detail="Bot not available")

    # Валидация сообщения
    if not message.strip():
        raise HTTPException(
            status_code=400, detail="Текст сообщения не может быть пустым"
        )

    if len(message) > 4096:
        raise HTTPException(
            status_code=400,
            detail=f"Сообщение слишком длинное. Текущая длина: {len(message)} символов, максимум: 4096 символов",
        )

    if recipient_type not in ["all", "selected"]:
        raise HTTPException(
            status_code=400,
            detail="Неверный тип получателей. Допустимы: 'all' или 'selected'",
        )

    if recipient_type == "selected":
        if not user_ids:
            raise HTTPException(
                status_code=400,
                detail="Не выбраны получатели. Выберите хотя бы одного пользователя",
            )

        if len(user_ids) == 0:
            raise HTTPException(status_code=400, detail="Список получателей пуст")

        # Проверка корректности ID
        invalid_ids = [uid for uid in user_ids if not uid.isdigit()]
        if invalid_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Некорректные ID пользователей: {', '.join(invalid_ids)}",
            )

    # Детальная валидация фотографий
    if photos:
        if len(photos) > 10:
            raise HTTPException(
                status_code=400,
                detail=f"Превышено максимальное количество фотографий. Загружено: {len(photos)}, максимум: 10",
            )

        # Проверка размера и типа каждого файла
        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
        ALLOWED_TYPES = [
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/gif",
            "image/webp",
        ]

        for idx, photo in enumerate(photos):
            # Получаем размер файла
            contents = await photo.read()
            file_size = len(contents)
            await photo.seek(0)  # Возвращаем указатель в начало

            # Проверка размера файла
            if file_size > MAX_FILE_SIZE:
                size_mb = file_size / (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=f"Файл #{idx + 1} '{photo.filename}' слишком большой. Размер: {size_mb:.1f} MB, максимум: 20 MB",
                )

            # Проверка типа файла
            if photo.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Файл #{idx + 1} '{photo.filename}' имеет недопустимый тип: {photo.content_type}. Разрешены: JPEG, PNG, GIF, WebP",
                )

            # Проверка наличия имени файла
            if not photo.filename:
                raise HTTPException(
                    status_code=400, detail=f"Файл #{idx + 1} не имеет имени"
                )

    def _get_recipients(session):
        """Получение списка получателей."""
        if recipient_type == "all":
            users = session.query(User).filter(User.telegram_id.isnot(None)).all()
        else:
            # Преобразуем строки в числа
            telegram_ids = [int(uid) for uid in user_ids if uid.isdigit()]
            users = session.query(User).filter(User.telegram_id.in_(telegram_ids)).all()

        return [
            {
                "telegram_id": user.telegram_id,
                "full_name": user.full_name or f"User {user.telegram_id}",
            }
            for user in users
        ]

    # Получаем получателей с детальной информацией
    recipients = DatabaseManager.safe_execute(_get_recipients)

    if not recipients:
        if recipient_type == "all":
            raise HTTPException(
                status_code=400,
                detail="В системе нет пользователей с активными Telegram аккаунтами",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Среди выбранных {len(user_ids)} пользователей не найдено активных Telegram аккаунтов",
            )

    # Сохраняем фотографии с подробной валидацией
    photo_paths = []
    if photos:
        NEWSLETTER_PHOTOS_DIR = Path("newsletter_photos")
        NEWSLETTER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        # Проверка свободного места на диске
        import shutil

        free_space = shutil.disk_usage(NEWSLETTER_PHOTOS_DIR).free

        total_size = 0
        for photo in photos:
            contents = await photo.read()
            total_size += len(contents)
            await photo.seek(0)

        if total_size > free_space:
            raise HTTPException(
                status_code=507,
                detail=f"Недостаточно места на диске. Требуется: {total_size / (1024 * 1024):.1f} MB, доступно: {free_space / (1024 * 1024):.1f} MB",
            )

        for idx, photo in enumerate(photos):
            try:
                if photo.content_type and photo.content_type.startswith("image/"):
                    timestamp = int(time.time())
                    # Получаем расширение файла
                    file_ext = Path(photo.filename).suffix if photo.filename else ".jpg"
                    if file_ext not in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                        file_ext = ".jpg"

                    filename = f"newsletter_{timestamp}_{idx}{file_ext}"
                    file_path = NEWSLETTER_PHOTOS_DIR / filename

                    contents = await photo.read()
                    with open(file_path, "wb") as f:
                        f.write(contents)

                    photo_paths.append(str(file_path))
                    logger.info(
                        f"Saved photo {idx + 1}: {filename} ({len(contents) / 1024:.1f} KB)"
                    )
                else:
                    logger.warning(
                        f"Skipped file {idx + 1} '{photo.filename}': unsupported type {photo.content_type}"
                    )
            except Exception as e:
                logger.error(f"Error saving photo {idx + 1}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Ошибка сохранения файла #{idx + 1} '{photo.filename}': {str(e)}",
                )

    # Отправка сообщений с детальным логированием
    success_count = 0
    failed_count = 0
    failed_users = []

    logger.info(f"Starting newsletter delivery to {len(recipients)} recipients")

    for idx, recipient in enumerate(recipients):
        try:
            user_info = f"{recipient['full_name']} (ID: {recipient['telegram_id']})"
            logger.debug(f"Sending to {idx + 1}/{len(recipients)}: {user_info}")

            if photo_paths:
                # Отправка с фотографиями
                if len(photo_paths) == 1:
                    # Одно фото - отправляем как фото с подписью
                    with open(photo_paths[0], "rb") as photo:
                        await bot.send_photo(
                            chat_id=recipient["telegram_id"],
                            photo=photo,
                            caption=message,
                            parse_mode="HTML",
                        )
                    logger.debug(f"Sent photo message to {user_info}")
                else:
                    # Несколько фото - отправляем как медиагруппу
                    media_group = []
                    for photo_idx, photo_path in enumerate(photo_paths):
                        media = InputMediaPhoto(
                            media=FSInputFile(photo_path),
                            caption=message if photo_idx == 0 else None,
                            parse_mode="HTML" if photo_idx == 0 else None,
                        )
                        media_group.append(media)

                    await bot.send_media_group(
                        chat_id=recipient["telegram_id"], media=media_group
                    )
                    logger.debug(
                        f"Sent media group ({len(photo_paths)} photos) to {user_info}"
                    )
            else:
                # Отправка только текста
                await bot.send_message(
                    chat_id=recipient["telegram_id"], text=message, parse_mode="HTML"
                )
                logger.debug(f"Sent text message to {user_info}")

            success_count += 1

            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.05)

        except TelegramAPIError as e:
            failed_count += 1
            error_msg = str(e)
            failed_users.append(
                {
                    "telegram_id": recipient["telegram_id"],
                    "full_name": recipient["full_name"],
                    "error": error_msg,
                }
            )

            # Детальное логирование ошибок Telegram API
            if "bot was blocked by the user" in error_msg.lower():
                logger.warning(f"User {user_info} blocked the bot")
            elif "chat not found" in error_msg.lower():
                logger.warning(f"Chat not found for user {user_info}")
            elif "user is deactivated" in error_msg.lower():
                logger.warning(f"User {user_info} is deactivated")
            elif "too many requests" in error_msg.lower():
                logger.error(f"Rate limit exceeded when sending to {user_info}")
                # Увеличиваем задержку для следующих сообщений
                await asyncio.sleep(1)
            else:
                logger.warning(f"Telegram API error for {user_info}: {error_msg}")

        except Exception as e:
            failed_count += 1
            error_msg = str(e)
            failed_users.append(
                {
                    "telegram_id": recipient["telegram_id"],
                    "full_name": recipient["full_name"],
                    "error": error_msg,
                }
            )
            logger.error(f"Unexpected error sending to {user_info}: {error_msg}")

    # Итоговое логирование
    logger.info(
        f"Newsletter delivery completed: {success_count} successful, {failed_count} failed out of {len(recipients)} total"
    )

    # Определяем статус рассылки
    if success_count == len(recipients):
        status = "success"
    elif success_count == 0:
        status = "failed"
    else:
        status = "partial"

    # Сохраняем в БД
    def _save_newsletter(session):
        newsletter = Newsletter(
            message=message,
            recipient_type=recipient_type,
            recipient_ids=",".join([str(r["telegram_id"]) for r in recipients]),
            total_count=len(recipients),
            success_count=success_count,
            failed_count=failed_count,
            photo_count=len(photo_paths),
            status=status,
            created_at=datetime.now(MOSCOW_TZ),
        )
        session.add(newsletter)
        session.flush()

        return {
            "id": newsletter.id,
            "total_count": newsletter.total_count,
            "success_count": newsletter.success_count,
            "failed_count": newsletter.failed_count,
            "photo_count": newsletter.photo_count or 0,
            "status": newsletter.status,
            "recipient_type": newsletter.recipient_type,
            "created_at": newsletter.created_at,
        }

    result = DatabaseManager.safe_execute(_save_newsletter)

    # Удаляем временные файлы фотографий
    for photo_path in photo_paths:
        try:
            Path(photo_path).unlink()
        except Exception as e:
            logger.warning(f"Failed to delete photo {photo_path}: {e}")

    logger.info(
        f"Newsletter sent successfully: {success_count}/{len(recipients)} delivered, "
        f"message length: {len(message)} chars, photos: {len(photo_paths)}"
    )

    # Формируем детальный ответ
    response_data = {
        **result,
        "message_stats": {
            "length": len(message),
            "has_html": "<" in message and ">" in message,
            "photo_count": len(photo_paths),
        },
    }

    # Добавляем информацию о неудачах если есть
    if failed_count > 0:
        response_data["failed_users"] = failed_users
        response_data["failure_summary"] = {
            "blocked_users": len(
                [u for u in failed_users if "blocked" in u["error"].lower()]
            ),
            "not_found_users": len(
                [u for u in failed_users if "not found" in u["error"].lower()]
            ),
            "api_errors": len([u for u in failed_users if "api" in u["error"].lower()]),
            "other_errors": len(
                [
                    u
                    for u in failed_users
                    if not any(
                        keyword in u["error"].lower()
                        for keyword in ["blocked", "not found", "api"]
                    )
                ]
            ),
        }

    return response_data


@app.get("/newsletters", response_model=List[NewsletterResponse])
async def get_newsletters(
    limit: int = 50, offset: int = 0, _: str = Depends(verify_token)
):
    """Получение списка рассылок (алиас для history)."""
    return await get_newsletter_history(limit, offset, _)


@app.get("/newsletters/history", response_model=List[NewsletterResponse])
async def get_newsletter_history(
    limit: int = 50, offset: int = 0, _: str = Depends(verify_token)
):
    """Получение истории рассылок."""

    def _get_history(session):
        newsletters = (
            session.query(Newsletter)
            .order_by(Newsletter.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return [
            {
                "id": n.id,
                "message": n.message,
                "status": n.status,
                "total_count": n.total_count,
                "success_count": n.success_count,
                "photo_count": n.photo_count or 0,
                "created_at": n.created_at,
            }
            for n in newsletters
        ]

    try:
        return DatabaseManager.safe_execute(_get_history)
    except Exception as e:
        logger.error(f"Error getting newsletter history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter history")


@app.get("/newsletters/{newsletter_id}")
async def get_newsletter_detail(newsletter_id: int, _: str = Depends(verify_token)):
    """Получение детальной информации о рассылке."""

    def _get_detail(session):
        newsletter = (
            session.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        )

        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        # Получаем информацию о получателях
        recipient_ids = []
        if newsletter.recipient_ids:
            recipient_ids = [
                int(rid)
                for rid in newsletter.recipient_ids.split(",")
                if rid.strip().isdigit()
            ]

        recipients = []
        if recipient_ids:
            recipients = (
                session.query(User).filter(User.telegram_id.in_(recipient_ids)).all()
            )

        return {
            "id": newsletter.id,
            "message": newsletter.message,
            "status": newsletter.status,
            "total_count": newsletter.total_count,
            "success_count": newsletter.success_count,
            "failed_count": newsletter.failed_count,
            "photo_count": newsletter.photo_count or 0,
            "recipient_type": newsletter.recipient_type,
            "created_at": newsletter.created_at,
            "recipients": [
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "full_name": user.full_name,
                    "username": user.username,
                }
                for user in recipients
            ],
        }

    try:
        return DatabaseManager.safe_execute(_get_detail)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting newsletter detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter detail")


@app.delete("/newsletters/{newsletter_id}")
async def delete_newsletter(newsletter_id: int, _: str = Depends(verify_token)):
    """Удаление записи о рассылке из истории."""

    def _delete_newsletter(session):
        newsletter = (
            session.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        )

        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        session.delete(newsletter)

        return {"message": "Newsletter deleted successfully"}

    try:
        return DatabaseManager.safe_execute(_delete_newsletter)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting newsletter: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete newsletter")


@app.get("/newsletters/stats")
async def get_newsletter_stats(_: str = Depends(verify_token)):
    """Получение статистики рассылок."""

    def _get_stats(session):
        # Общая статистика
        total_newsletters = session.query(Newsletter).count()

        # Статистика по статусам
        successful = (
            session.query(Newsletter).filter(Newsletter.status == "success").count()
        )
        failed = session.query(Newsletter).filter(Newsletter.status == "failed").count()
        partial = (
            session.query(Newsletter).filter(Newsletter.status == "partial").count()
        )

        # Последние рассылки
        recent = (
            session.query(Newsletter)
            .order_by(Newsletter.created_at.desc())
            .limit(5)
            .all()
        )

        # Общее количество отправленных сообщений
        total_sent = (
            session.query(Newsletter)
            .with_entities(session.query(Newsletter.success_count).label("total"))
            .scalar()
            or 0
        )

        return {
            "total_newsletters": total_newsletters,
            "successful_newsletters": successful,
            "failed_newsletters": failed,
            "partial_newsletters": partial,
            "total_messages_sent": total_sent,
            "recent_newsletters": [
                {
                    "id": n.id,
                    "message": n.message[:100]
                    + ("..." if len(n.message) > 100 else ""),
                    "status": n.status,
                    "success_count": n.success_count,
                    "total_count": n.total_count,
                    "created_at": n.created_at,
                }
                for n in recent
            ],
        }

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Error getting newsletter stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter stats")


@app.post("/newsletters/validate")
async def validate_newsletter_message(
    message: str = Form(...), _: str = Depends(verify_token)
):
    """Валидация HTML тегов в сообщении рассылки."""

    # Разрешенные HTML теги для Telegram
    allowed_tags = ["b", "i", "u", "code", "a", "s", "strike", "pre", "strong", "em"]

    import re

    # Найти все теги
    tag_pattern = r"<\/?([a-zA-Z]+)(?:\s[^>]*)?>"
    matches = re.finditer(tag_pattern, message)

    open_tags = []
    errors = []

    for match in matches:
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        is_closing = full_tag.startswith("</")
        is_self_closing = full_tag.endswith("/>")

        # Проверка разрешенности тега
        if tag_name not in allowed_tags:
            errors.append(f"Недопустимый тег: <{tag_name}>")
            continue

        # Обработка открывающих и закрывающих тегов
        if is_closing:
            if not open_tags or open_tags[-1] != tag_name:
                errors.append(f"Неожиданный закрывающий тег: </{tag_name}>")
            else:
                open_tags.pop()
        elif not is_self_closing:
            open_tags.append(tag_name)

    # Проверка незакрытых тегов
    if open_tags:
        errors.append(
            f"Незакрытые теги: {', '.join([f'<{tag}>' for tag in open_tags])}"
        )

    # Проверка специальных правил для тега <a>
    link_pattern = r'<a\s+href="([^"]*)"[^>]*>'
    link_matches = re.finditer(link_pattern, message)

    for match in link_matches:
        href = match.group(1)
        if not href or not (href.startswith("http://") or href.startswith("https://")):
            errors.append(f"Некорректная ссылка: {href or 'пустая ссылка'}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "message": (
            "Сообщение валидно"
            if len(errors) == 0
            else f"Найдено ошибок: {len(errors)}"
        ),
    }


@app.post("/newsletters/preview")
async def preview_newsletter(
    message: str = Form(...),
    recipient_type: str = Form(...),
    user_ids: Optional[List[str]] = Form(None),
    _: str = Depends(verify_token),
):
    """Предварительный просмотр рассылки."""

    def _get_preview_data(session):
        if recipient_type == "all":
            users = session.query(User).filter(User.telegram_id.isnot(None)).all()
        else:
            telegram_ids = [int(uid) for uid in user_ids if uid.isdigit()]
            users = session.query(User).filter(User.telegram_id.in_(telegram_ids)).all()

        return {
            "recipient_count": len(users),
            "message_length": len(message),
            "recipients": [
                {
                    "telegram_id": user.telegram_id,
                    "full_name": user.full_name,
                    "username": user.username,
                }
                for user in users[:10]  # Показываем только первых 10
            ],
            "has_more_recipients": len(users) > 10,
        }

    try:
        preview_data = DatabaseManager.safe_execute(_get_preview_data)

        # Валидация сообщения
        validation_result = await validate_newsletter_message(message)

        return {
            **preview_data,
            "message_valid": validation_result["valid"],
            "validation_errors": validation_result.get("errors", []),
        }
    except Exception as e:
        logger.error(f"Error creating newsletter preview: {e}")
        raise HTTPException(status_code=500, detail="Failed to create preview")


@app.post("/newsletters/test")
async def test_newsletter(
    message: str = Form(...),
    test_telegram_id: int = Form(...),
    photos: Optional[List[UploadFile]] = File(None),
    _: str = Depends(verify_token),
):
    """Тестовая отправка рассылки на указанный Telegram ID."""

    if not bot:
        raise HTTPException(
            status_code=503,
            detail="Telegram бот недоступен. Обратитесь к системному администратору",
        )

    if not message.strip():
        raise HTTPException(
            status_code=400, detail="Текст тестового сообщения не может быть пустым"
        )

    if len(message) > 4096:
        raise HTTPException(
            status_code=400,
            detail=f"Тестовое сообщение слишком длинное: {len(message)} символов (максимум 4096)",
        )

    # Валидация фотографий для теста
    if photos:
        if len(photos) > 10:
            raise HTTPException(
                status_code=400,
                detail=f"Слишком много фотографий для теста: {len(photos)} (максимум 10)",
            )

        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
        for idx, photo in enumerate(photos):
            contents = await photo.read()
            await photo.seek(0)

            if len(contents) > MAX_FILE_SIZE:
                size_mb = len(contents) / (1024 * 1024)
                raise HTTPException(
                    status_code=400,
                    detail=f"Тестовое фото #{idx + 1} слишком большое: {size_mb:.1f} MB (максимум 20 MB)",
                )

    # Сохраняем фотографии во временную папку
    photo_paths = []
    if photos:
        TEST_PHOTOS_DIR = Path("static/test_photos")
        TEST_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        for idx, photo in enumerate(photos):
            if photo.content_type and photo.content_type.startswith("image/"):
                timestamp = int(time.time())
                file_ext = Path(photo.filename).suffix if photo.filename else ".jpg"
                filename = f"test_{timestamp}_{idx}{file_ext}"
                file_path = TEST_PHOTOS_DIR / filename

                contents = await photo.read()
                with open(file_path, "wb") as f:
                    f.write(contents)

                photo_paths.append(str(file_path))

    try:
        # Отправляем тестовое сообщение
        if photo_paths:
            if len(photo_paths) == 1:
                with open(photo_paths[0], "rb") as photo:
                    await bot.send_photo(
                        chat_id=test_telegram_id,
                        photo=photo,
                        caption=f"🧪 ТЕСТ: {message}",
                        parse_mode="HTML",
                    )
                logger.info(f"Test photo message sent to {test_telegram_id}")
            else:
                media_group = []
                for idx, photo_path in enumerate(photo_paths):
                    media = InputMediaPhoto(
                        media=FSInputFile(photo_path),
                        caption=f"🧪 ТЕСТ: {message}" if idx == 0 else None,
                        parse_mode="HTML" if idx == 0 else None,
                    )
                    media_group.append(media)

                await bot.send_media_group(chat_id=test_telegram_id, media=media_group)
                logger.info(
                    f"Test media group ({len(photo_paths)} photos) sent to {test_telegram_id}"
                )
        else:
            await bot.send_message(
                chat_id=test_telegram_id, text=f"🧪 ТЕСТ: {message}", parse_mode="HTML"
            )
            logger.info(f"Test text message sent to {test_telegram_id}")

        return {
            "success": True,
            "message": f"Тестовое сообщение успешно отправлено на Telegram ID: {test_telegram_id}",
            "details": {
                "recipient_id": test_telegram_id,
                "message_length": len(message),
                "photo_count": len(photo_paths),
                "has_html": "<" in message and ">" in message,
            },
        }

    except TelegramAPIError as e:
        error_msg = str(e)
        logger.error(
            f"Telegram API error during test to {test_telegram_id}: {error_msg}"
        )

        # Специфичные ошибки Telegram
        if "bot was blocked" in error_msg.lower():
            detail = f"Пользователь {test_telegram_id} заблокировал бота"
        elif "chat not found" in error_msg.lower():
            detail = f"Чат с пользователем {test_telegram_id} не найден"
        elif "user is deactivated" in error_msg.lower():
            detail = f"Аккаунт пользователя {test_telegram_id} деактивирован"
        elif "too many requests" in error_msg.lower():
            detail = "Превышен лимит запросов к Telegram API. Попробуйте позже"
        else:
            detail = f"Ошибка Telegram API: {error_msg}"

        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        logger.error(f"Unexpected error sending test to {test_telegram_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Неожиданная ошибка при отправке тестового сообщения: {str(e)}",
        )
    finally:
        # Удаляем тестовые фотографии
        for photo_path in photo_paths:
            try:
                Path(photo_path).unlink()
                logger.debug(f"Deleted test photo: {photo_path}")
            except Exception as e:
                logger.warning(f"Failed to delete test photo {photo_path}: {e}")


@app.get("/newsletters/templates")
async def get_newsletter_templates(_: str = Depends(verify_token)):
    """Получение шаблонов сообщений для рассылки."""

    templates = [
        {
            "id": 1,
            "name": "Приветствие",
            "message": "<b>Добро пожаловать!</b>\n\nСпасибо за регистрацию в нашем сервисе. Мы рады видеть вас среди наших пользователей!",
        },
        {
            "id": 2,
            "name": "Новости",
            "message": "<b>📰 Новости недели</b>\n\nУважаемые пользователи!\n\nСпешим поделиться с вами последними новостями...",
        },
        {
            "id": 3,
            "name": "Обновление",
            "message": "<b>🚀 Обновление системы</b>\n\nВ системе появились новые возможности:\n• Новая функция 1\n• Улучшение 2\n• Исправление 3",
        },
        {
            "id": 4,
            "name": "Техническое обслуживание",
            "message": "<b>⚠️ Техническое обслуживание</b>\n\nВнимание! Планируется техническое обслуживание системы.\n\n<u>Время:</u> [УКАЖИТЕ ВРЕМЯ]\n<u>Продолжительность:</u> [УКАЖИТЕ ВРЕМЯ]",
        },
    ]

    return templates


@app.get("/newsletters/limits")
async def get_newsletter_limits(_: str = Depends(verify_token)):
    """Получение ограничений системы для рассылок."""

    import shutil

    # Получаем информацию о дисковом пространстве
    newsletter_dir = Path("newsletter_photos")
    newsletter_dir.mkdir(parents=True, exist_ok=True)

    disk_usage = shutil.disk_usage(newsletter_dir)

    return {
        "message_limits": {
            "max_length": 4096,
            "supported_html_tags": [
                "b",
                "i",
                "u",
                "code",
                "a",
                "s",
                "strike",
                "pre",
                "strong",
                "em",
            ],
            "description": "Максимальная длина сообщения для Telegram",
        },
        "photo_limits": {
            "max_count": 10,
            "max_file_size_mb": 20,
            "supported_formats": ["JPEG", "PNG", "GIF", "WebP"],
            "description": "Ограничения для фотографий",
        },
        "system_info": {
            "disk_total_gb": round(disk_usage.total / (1024**3), 2),
            "disk_used_gb": round((disk_usage.total - disk_usage.free) / (1024**3), 2),
            "disk_free_gb": round(disk_usage.free / (1024**3), 2),
            "disk_usage_percent": round(
                ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100, 1
            ),
        },
        "telegram_limits": {
            "rate_limit": "30 сообщений в секунду для ботов",
            "file_size_limit": "20 MB для фотографий",
            "media_group_limit": "10 файлов в медиагруппе",
        },
    }


@app.get("/newsletters/user-count")
async def get_newsletter_user_count(_: str = Depends(verify_token)):
    """Получение количества пользователей для рассылки."""

    def _get_count(session):
        total_users = session.query(User).count()
        telegram_users = (
            session.query(User).filter(User.telegram_id.isnot(None)).count()
        )

        return {
            "total_users": total_users,
            "telegram_users": telegram_users,
            "available_for_newsletter": telegram_users,
        }

    try:
        return DatabaseManager.safe_execute(_get_count)
    except Exception as e:
        logger.error(f"Error getting user count: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user count")


# ================== DASHBOARD ENDPOINTS ==================


@app.get("/dashboard/stats")
async def get_dashboard_stats(_: str = Depends(verify_token)):
    """Получение статистики для дашборда."""

    def _get_stats(session):
        # Используем прямые SQL запросы для лучшей производительности
        total_users = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        total_bookings = session.execute(text("SELECT COUNT(*) FROM bookings")).scalar()
        open_tickets = session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED'")
        ).scalar()
        active_tariffs = session.execute(
            text("SELECT COUNT(*) FROM tariffs WHERE is_active = 1")
        ).scalar()

        return {
            "total_users": total_users,
            "total_bookings": total_bookings,
            "open_tickets": open_tickets,
            "active_tariffs": active_tariffs,
        }

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Ошибка в get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")


# ================== TICKET ENDPOINTS ==================


@app.get("/tickets/detailed")
async def get_tickets_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    user_query: Optional[str] = None,
    _: str = Depends(verify_token),
):
    """Получение тикетов с данными пользователей и фильтрацией."""

    def _get_tickets(session):
        try:
            logger.info(
                f"Запрос тикетов: page={page}, per_page={per_page}, status='{status}', user_query='{user_query}'"
            )

            # Используем прямые SQL-запросы для лучшей производительности
            base_query = """
                SELECT 
                    t.id, t.user_id, t.description, t.photo_id, t.response_photo_id,
                    t.status, t.comment, t.created_at, t.updated_at,
                    u.telegram_id, u.full_name, u.username, u.phone, u.email
                FROM tickets t
                LEFT JOIN users u ON t.user_id = u.id
            """

            where_conditions = []
            params = {}

            # Фильтрация по пользователю
            if user_query and user_query.strip():
                where_conditions.append("u.full_name LIKE :user_query")
                params["user_query"] = f"%{user_query.strip()}%"

            # Фильтрация по статусу
            if status and status.strip():
                where_conditions.append("t.status = :status")
                params["status"] = status.strip()

            # Собираем финальный запрос
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            # Подсчет общего количества
            count_query = f"SELECT COUNT(*) FROM ({base_query}) as counted"
            total_count = session.execute(text(count_query), params).scalar()

            # Основной запрос с пагинацией
            final_query = (
                base_query + " ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset"
            )
            params["limit"] = per_page
            params["offset"] = (page - 1) * per_page

            result = session.execute(text(final_query), params).fetchall()

            # Формируем ответ
            enriched_tickets = []
            for row in result:
                ticket_item = {
                    "id": int(row.id),
                    "user_id": int(row.user_id),
                    "description": row.description,
                    "photo_id": row.photo_id,
                    "response_photo_id": row.response_photo_id,
                    "status": row.status,
                    "comment": row.comment,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "user": {
                        "id": row.user_id,
                        "telegram_id": row.telegram_id,
                        "full_name": row.full_name or "Имя не указано",
                        "username": row.username,
                        "phone": row.phone,
                        "email": row.email,
                    },
                }
                enriched_tickets.append(ticket_item)

            total_pages = (total_count + per_page - 1) // per_page

            return {
                "tickets": enriched_tickets,
                "total_count": int(total_count),
                "page": int(page),
                "per_page": int(per_page),
                "total_pages": int(total_pages),
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_tickets: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_tickets)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при получении тикетов: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Также добавим эндпоинт для статистики тикетов
@app.get("/tickets/stats")
async def get_tickets_stats(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение статистики по тикетам."""
    try:
        total_tickets = db.query(Ticket).count()
        open_tickets = (
            db.query(Ticket).filter(Ticket.status == TicketStatus.OPEN).count()
        )
        in_progress_tickets = (
            db.query(Ticket).filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
        )
        closed_tickets = (
            db.query(Ticket).filter(Ticket.status == TicketStatus.CLOSED).count()
        )

        # Средний ответ можно вычислить как разница между created_at и updated_at для закрытых тикетов
        # Но это упрощенная версия для примера
        avg_response_time = 0  # В часах, можно добавить реальную логику позже

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "closed_tickets": closed_tickets,
            "avg_response_time": avg_response_time,
        }

    except Exception as e:
        logger.error(f"Ошибка при получении статистики тикетов: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/tickets", response_model=List[dict])
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение списка тикетов с фильтрацией."""
    query = db.query(Ticket).join(User).order_by(Ticket.created_at.desc())

    if status:
        try:
            status_enum = TicketStatus[status]
            query = query.filter(Ticket.status == status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid status")

    tickets = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for ticket in tickets:
        result.append(
            {
                "id": ticket.id,
                "description": ticket.description,
                "photo_id": ticket.photo_id,
                "response_photo_id": ticket.response_photo_id,
                "status": ticket.status.name,
                "comment": ticket.comment,
                "created_at": ticket.created_at.isoformat(),
                "updated_at": ticket.updated_at.isoformat(),
                "user": {
                    "id": ticket.user.id,
                    "telegram_id": ticket.user.telegram_id,
                    "full_name": ticket.user.full_name,
                    "username": ticket.user.username,
                    "phone": ticket.user.phone,
                    "email": ticket.user.email,
                },
            }
        )

    return result


@app.get("/tickets/{ticket_id}")
async def get_ticket_by_id(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение конкретного тикета по ID."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    user = db.query(User).filter(User.id == ticket.user_id).first()

    return {
        "id": ticket.id,
        "description": ticket.description,
        "photo_id": ticket.photo_id,
        "response_photo_id": ticket.response_photo_id,
        "status": ticket.status.name,
        "comment": ticket.comment,
        "created_at": ticket.created_at.isoformat(),
        "updated_at": ticket.updated_at.isoformat(),
        "user": (
            {
                "id": user.id if user else None,
                "telegram_id": user.telegram_id if user else None,
                "full_name": user.full_name if user else "Пользователь не найден",
                "username": user.username if user else None,
                "phone": user.phone if user else None,
                "email": user.email if user else None,
            }
            if user
            else {
                "id": ticket.user_id,
                "telegram_id": None,
                "full_name": "Пользователь не найден",
                "username": None,
                "phone": None,
                "email": None,
            }
        ),
    }


@app.post("/tickets")
async def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    """Создание нового тикета. Используется ботом."""
    user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Определяем статус
    status_enum = TicketStatus.OPEN
    if ticket_data.status:
        try:
            status_enum = TicketStatus(ticket_data.status)
        except ValueError:
            status_enum = TicketStatus.OPEN

    # Создаем тикет
    ticket = Ticket(
        user_id=user.id,
        description=ticket_data.description,
        photo_id=ticket_data.photo_id,  # Сохраняем Telegram file_id как есть
        status=status_enum,
        comment=ticket_data.comment,
        created_at=datetime.now(MOSCOW_TZ),
        updated_at=datetime.now(MOSCOW_TZ),
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "message": "Ticket created successfully"}


@app.put("/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление тикета (статус, комментарий)."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Получаем пользователя для отправки уведомления
        user = db.query(User).filter(User.id == ticket.user_id).first()

        # Сохраняем старые значения
        old_status = ticket.status
        old_comment = ticket.comment

        # Обновляем статус
        if "status" in update_data:
            try:
                new_status = TicketStatus[update_data["status"]]
                ticket.status = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        # Обновляем комментарий (всегда сохраняем в БД)
        if "comment" in update_data:
            ticket.comment = update_data["comment"]

        # Обновляем response_photo_id если указано
        if "response_photo_id" in update_data:
            ticket.response_photo_id = update_data["response_photo_id"]

        # Обновляем время изменения
        ticket.updated_at = datetime.now(MOSCOW_TZ)

        db.commit()
        db.refresh(ticket)

        # Отправляем уведомление пользователю (только если нет фото)
        # Если было фото, уведомление уже отправлено в /photo эндпоинте
        if bot and user and user.telegram_id and not update_data.get("photo_sent"):
            try:
                status_changed = old_status != ticket.status
                comment_changed = ticket.comment and ticket.comment != old_comment

                if status_changed or comment_changed:
                    status_messages = {
                        TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
                        TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
                        TicketStatus.CLOSED: "✅ Ваша заявка решена",
                    }

                    message = f"🎫 <b>Обновление по заявке #{ticket.id}</b>\n\n"

                    if status_changed:
                        message += status_messages.get(
                            ticket.status, f"Статус: {ticket.status.name}"
                        )

                    if comment_changed:
                        message += f"\n\n💬 <b>Комментарий администратора:</b>\n{ticket.comment}"

                    await bot.send_message(
                        chat_id=user.telegram_id, text=message, parse_mode="HTML"
                    )
                    logger.info(
                        f"📤 Отправлено уведомление об обновлении тикета #{ticket.id} пользователю {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"❌ Ошибка отправки уведомления о тикете #{ticket.id}: {e}"
                )

        # Возвращаем обновленный тикет
        return {
            "id": ticket.id,
            "description": ticket.description,
            "photo_id": ticket.photo_id,
            "response_photo_id": ticket.response_photo_id,
            "status": ticket.status.name,
            "comment": ticket.comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка обновления тикета {ticket_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/tickets/{ticket_id}/photo-base64")
async def get_ticket_photo_base64(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение фото в формате base64 для использования в React."""

    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not ticket.photo_id:
        raise HTTPException(status_code=404, detail="Photo not found")

    if not bot:
        raise HTTPException(status_code=503, detail="Bot not available")

    try:
        # Получаем файл через Telegram Bot API
        file_info = await bot.get_file(ticket.photo_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"

        # Скачиваем изображение
        import aiohttp
        import base64

        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    image_data = await response.read()

                    # Определяем MIME-тип
                    import mimetypes

                    mime_type, _ = mimetypes.guess_type(file_info.file_path)
                    if not mime_type or not mime_type.startswith("image/"):
                        mime_type = "image/jpeg"

                    # Конвертируем в base64
                    base64_data = base64.b64encode(image_data).decode("utf-8")
                    data_url = f"data:{mime_type};base64,{base64_data}"

                    return {
                        "photo_url": data_url,
                        "mime_type": mime_type,
                        "size": len(image_data),
                    }
                else:
                    raise HTTPException(
                        status_code=404, detail="Photo not accessible from Telegram"
                    )

    except Exception as e:
        logger.error(f"❌ Ошибка получения фото из Telegram: {e}")
        raise HTTPException(status_code=404, detail="Photo not accessible")


@app.post("/tickets/{ticket_id}/photo")
async def upload_response_photo(
    ticket_id: int,
    file: UploadFile = File(...),
    comment: Optional[str] = Form(None),
    status: Optional[str] = Form(None),  # Добавляем статус
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Загрузка фото в ответе администратора (отправляем в Telegram с caption, не сохраняем)."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Получаем пользователя
    user = db.query(User).filter(User.id == ticket.user_id).first()
    if not user or not user.telegram_id:
        raise HTTPException(status_code=404, detail="User telegram not found")

    # Проверяем тип файла
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Проверяем размер файла (максимум 10MB)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    if not bot:
        raise HTTPException(status_code=503, detail="Bot not available")

    try:
        # Читаем файл в память
        file_content = await file.read()

        # Правильный способ отправки фото через aiogram
        from aiogram.types import BufferedInputFile

        # Создаем BufferedInputFile для aiogram
        photo_file = BufferedInputFile(
            file=file_content, filename=file.filename or f"photo_{ticket_id}.jpg"
        )

        # Формируем caption с информацией о тикете и комментарием
        caption = f"📷 Фото к ответу по заявке #{ticket.id}"

        if comment and comment.strip():
            caption += f"\n\n💬 Комментарий администратора:\n{comment.strip()}"

        # Отправляем фото пользователю с caption
        sent_message = await bot.send_photo(
            chat_id=user.telegram_id,
            photo=photo_file,
            caption=caption,
            parse_mode="HTML",
        )

        logger.info(
            f"📷 Фото с комментарием отправлено пользователю {user.telegram_id} по тикету #{ticket.id}"
        )

        # Сохраняем информацию о том, что фото было отправлено
        photo_sent_id = f"photo_sent_{ticket.id}_{sent_message.message_id}"

        # Обновляем тикет в БД
        update_data = {
            "response_photo_id": photo_sent_id,  # Сохраняем факт отправки фото
            "photo_sent": True,  # Флаг для предотвращения повторной отправки уведомления
        }

        if comment and comment.strip():
            update_data["comment"] = comment.strip()

        if status:
            update_data["status"] = status

        # Вызываем обновление тикета
        from fastapi import Request
        from unittest.mock import Mock

        # Создаем mock request для обновления
        mock_request = {"method": "PUT", "url": f"/tickets/{ticket_id}"}

        updated_ticket = await update_ticket(ticket_id, update_data, db, _)

        # Возвращаем успешный ответ
        return {
            "message": "Photo with comment sent to user successfully",
            "sent_to": user.telegram_id,
            "ticket_id": ticket.id,
            "caption": caption,
            "photo_sent_id": photo_sent_id,
            "updated_ticket": updated_ticket,
        }

    except Exception as e:
        logger.error(f"❌ Ошибка отправки фото пользователю: {e}")
        raise HTTPException(status_code=500, detail="Error sending photo to user")


@app.get("/users/telegram/{telegram_id}/tickets")
async def get_user_tickets_by_telegram_id(
    telegram_id: int, status: Optional[str] = Query(None), db: Session = Depends(get_db)
):
    """Получение тикетов пользователя по его Telegram ID."""
    try:
        # Сначала находим пользователя по telegram_id
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Строим запрос для получения тикетов пользователя
        query = (
            db.query(Ticket)
            .filter(Ticket.user_id == user.id)
            .order_by(Ticket.created_at.desc())
        )

        # Фильтруем по статусу если указан
        if status:
            try:
                status_enum = TicketStatus[status]
                query = query.filter(Ticket.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        tickets = query.all()

        # Формируем ответ в том же формате, что ожидает бот
        result = []
        for ticket in tickets:
            result.append(
                {
                    "id": ticket.id,
                    "description": ticket.description,
                    "photo_id": ticket.photo_id,
                    "response_photo_id": ticket.response_photo_id,
                    "status": ticket.status.name,
                    "comment": ticket.comment,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "user_id": ticket.user_id,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении тикетов пользователя {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Удаление тикета."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.delete(ticket)
    db.commit()

    logger.info(f"🗑 Удален тикет #{ticket_id}")
    return {"message": "Ticket deleted successfully"}


# ================== HEALTH AND MONITORING ENDPOINTS ==================


@app.get("/health/database")
async def database_health(_: str = Depends(verify_token)):
    """Проверяет состояние базы данных."""
    try:

        def _test_connection(session):
            # Тест простого запроса
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1

        start_time = time_module.time()
        connection_ok = DatabaseManager.safe_execute(_test_connection)
        connection_time = time_module.time() - start_time

        # Проверяем статистику БД
        def _get_db_stats(session):
            stats = {}

            # Размер базы данных
            try:
                result = session.execute(text("PRAGMA page_count")).scalar()
                page_count = result or 0

                result = session.execute(text("PRAGMA page_size")).scalar()
                page_size = result or 4096

                stats["database_size_mb"] = (page_count * page_size) / (1024 * 1024)
            except:
                stats["database_size_mb"] = 0

            # WAL режим
            try:
                result = session.execute(text("PRAGMA journal_mode")).scalar()
                stats["wal_enabled"] = result == "wal"
            except:
                stats["wal_enabled"] = False

            # Количество записей
            try:
                stats["total_users"] = session.execute(
                    text("SELECT COUNT(*) FROM users")
                ).scalar()
                stats["total_bookings"] = session.execute(
                    text("SELECT COUNT(*) FROM bookings")
                ).scalar()
                stats["total_tickets"] = session.execute(
                    text("SELECT COUNT(*) FROM tickets")
                ).scalar()
            except:
                stats["total_users"] = 0
                stats["total_bookings"] = 0
                stats["total_tickets"] = 0

            return stats

        db_stats = DatabaseManager.safe_execute(_get_db_stats)

        return {
            "status": (
                "healthy" if connection_ok and connection_time < 2.0 else "degraded"
            ),
            "connection_ok": connection_ok,
            "connection_time": round(connection_time, 3),
            "database_stats": db_stats,
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка проверки здоровья БД: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }


@app.post("/admin/database/optimize")
async def optimize_database_endpoint(_: str = Depends(verify_token)):
    """Оптимизирует базу данных."""
    try:

        def _optimize(session):
            # Выполняем оптимизацию
            session.execute(text("PRAGMA optimize"))
            session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            return True

        success = DatabaseManager.safe_execute(_optimize)

        # Дополнительная оптимизация через прямое подключение
        try:
            db_path = data_dir / "coworking.db"
            conn = sqlite3.connect(str(db_path), timeout=30)
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            conn.commit()
            conn.close()
            logger.info("Дополнительная оптимизация (VACUUM, ANALYZE) выполнена")
        except Exception as e:
            logger.warning(f"Не удалось выполнить дополнительную оптимизацию: {e}")

        return {
            "status": "success" if success else "failed",
            "message": (
                "Оптимизация базы данных завершена" if success else "Ошибка оптимизации"
            ),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка оптимизации БД: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }


@app.get("/admin/database/status")
async def get_database_status(_: str = Depends(verify_token)):
    """Получение подробного статуса базы данных."""

    def _get_status(session):
        status = {}

        try:
            # Основная статистика
            status["tables"] = {}

            # Количество записей в таблицах
            tables = [
                "users",
                "bookings",
                "tickets",
                "tariffs",
                "promocodes",
                "notifications",
            ]
            for table in tables:
                try:
                    count = session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar()
                    status["tables"][table] = count
                except Exception as e:
                    status["tables"][table] = f"Error: {str(e)}"

            # Настройки базы данных
            pragmas = [
                "journal_mode",
                "synchronous",
                "cache_size",
                "page_size",
                "page_count",
            ]
            status["settings"] = {}

            for pragma in pragmas:
                try:
                    result = session.execute(text(f"PRAGMA {pragma}")).scalar()
                    status["settings"][pragma] = result
                except Exception as e:
                    status["settings"][pragma] = f"Error: {str(e)}"

            # Размер базы данных
            if "page_count" in status["settings"] and "page_size" in status["settings"]:
                try:
                    page_count = int(status["settings"]["page_count"])
                    page_size = int(status["settings"]["page_size"])
                    size_mb = (page_count * page_size) / (1024 * 1024)
                    status["database_size_mb"] = round(size_mb, 2)
                except:
                    status["database_size_mb"] = "Unknown"

            # Последние записи для проверки активности
            try:
                last_user = session.execute(
                    text(
                        "SELECT first_join_time FROM users ORDER BY first_join_time DESC LIMIT 1"
                    )
                ).scalar()
                status["last_user_created"] = last_user

                last_booking = session.execute(
                    text(
                        "SELECT created_at FROM bookings ORDER BY created_at DESC LIMIT 1"
                    )
                ).scalar()
                status["last_booking_created"] = last_booking

            except Exception as e:
                status["last_activity_error"] = str(e)

            return status

        except Exception as e:
            return {"error": str(e)}

    try:
        return DatabaseManager.safe_execute(_get_status)
    except Exception as e:
        logger.error(f"Ошибка получения статуса БД: {e}")
        return {"error": str(e), "timestamp": datetime.now(MOSCOW_TZ).isoformat()}


# ================== MIDDLEWARE ==================


@app.middleware("http")
async def database_maintenance_middleware(request, call_next):
    """Middleware для автоматического обслуживания БД."""

    # Выполняем обслуживание только для определенных запросов
    maintenance_paths = ["/dashboard/stats", "/health/database"]

    if request.url.path in maintenance_paths:
        # Простая проверка и оптимизация при необходимости
        try:

            def _check_db_health(session):
                # Проверяем размер WAL файла
                result = session.execute(
                    text("PRAGMA wal_checkpoint(PASSIVE)")
                ).fetchall()
                return result

            # Выполняем легкую оптимизацию
            DatabaseManager.safe_execute(_check_db_health, max_retries=1)
        except Exception as e:
            logger.debug(f"Не удалось выполнить обслуживание БД: {e}")

    response = await call_next(request)
    return response


# ================== DATABASE MAINTENANCE FUNCTIONS ==================


def optimize_database():
    """Оптимизация базы данных SQLite с улучшенной обработкой ошибок."""
    db_path = data_dir / "coworking.db"

    if not db_path.exists():
        logger.warning(f"База данных не найдена: {db_path}")
        return

    try:
        logger.info("Начинается плановая оптимизация базы данных...")

        # Создаем резервную копию
        backup_path = db_path.with_suffix(f".backup.{int(time_module.time())}")
        import shutil

        shutil.copy2(db_path, backup_path)
        logger.info(f"Создана резервная копия: {backup_path}")

        # Оптимизация через DatabaseManager
        def _optimize(session):
            session.execute(text("PRAGMA optimize"))
            session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            return True

        DatabaseManager.safe_execute(_optimize)

        # Дополнительная оптимизация через прямое соединение
        conn = sqlite3.connect(str(db_path), timeout=60)
        cursor = conn.cursor()

        # Проверяем целостность
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        if integrity_result != "ok":
            logger.warning(f"Проблема целостности БД: {integrity_result}")

        # Оптимизируем
        cursor.execute("VACUUM")
        cursor.execute("REINDEX")
        cursor.execute("ANALYZE")

        conn.commit()
        conn.close()

        logger.info("Плановая оптимизация базы данных завершена успешно")

        # Удаляем старые бэкапы (оставляем только последние 3)
        backup_files = sorted(data_dir.glob("*.backup.*"))
        if len(backup_files) > 3:
            for old_backup in backup_files[:-3]:
                old_backup.unlink()
                logger.info(f"Удален старый бэкап: {old_backup}")

    except Exception as e:
        logger.error(f"Ошибка плановой оптимизации БД: {e}")


def start_db_maintenance():
    """Запускает планировщик обслуживания БД."""
    import schedule

    # Оптимизация каждый день в 3:00
    schedule.every().day.at("03:00").do(optimize_database)

    # Проверка состояния каждые 10 минут
    def check_db_health():
        try:
            db_path = data_dir / "coworking.db"
            if db_path.exists():
                conn = sqlite3.connect(str(db_path), timeout=5)
                conn.execute("SELECT 1")
                conn.close()
        except Exception as e:
            logger.warning(f"Проблема с БД обнаружена: {e}")

    schedule.every(10).minutes.do(check_db_health)

    def run_maintenance():
        while True:
            schedule.run_pending()
            time_module.sleep(60)  # Проверяем каждую минуту

    maintenance_thread = threading.Thread(target=run_maintenance, daemon=True)
    maintenance_thread.start()
    logger.info("Планировщик обслуживания БД запущен")


# ================== STARTUP EVENT ==================


@app.on_event("startup")
async def startup_event():
    logger.info("Запуск приложения...")

    # Проверяем и создаем директории
    for directory in [data_dir, AVATARS_DIR, Path("/app/ticket_photos")]:
        try:
            directory.mkdir(exist_ok=True, parents=True)
            # Проверяем права на запись
            test_file = directory / "test_write"
            test_file.touch()
            test_file.unlink()
            logger.info(f"Директория {directory} готова")
        except Exception as e:
            logger.error(f"Ошибка с директорией {directory}: {e}")

    # Инициализируем БД с проверкой
    db_path = data_dir / "coworking.db"
    logger.info(f"Путь к БД: {db_path}")

    try:
        # Проверяем существующую БД на целостность
        if db_path.exists():
            logger.info(f"БД существует, размер: {db_path.stat().st_size} байт")

            # Быстрая проверка целостности
            try:
                conn = sqlite3.connect(str(db_path), timeout=10)
                cursor = conn.cursor()
                cursor.execute("PRAGMA quick_check")
                result = cursor.fetchone()[0]
                conn.close()

                if result != "ok":
                    logger.warning(f"Проблема с БД: {result}")
                else:
                    logger.info("БД прошла проверку целостности")
            except Exception as e:
                logger.warning(f"Не удалось проверить целостность БД: {e}")

        # Инициализируем БД
        logger.info("Инициализация БД...")
        init_db()
        logger.info("База данных инициализирована успешно")

        # Проверяем что всё работает
        def _test_db(session):
            return session.execute(text("SELECT COUNT(*) FROM users")).scalar()

        user_count = DatabaseManager.safe_execute(_test_db)
        logger.info(f"В БД найдено пользователей: {user_count}")

    except Exception as e:
        logger.error(f"Критическая ошибка инициализации БД: {e}")
        # Попытка восстановления
        try:
            if db_path.exists():
                backup_path = db_path.with_suffix(
                    f".corrupted.{int(time_module.time())}"
                )
                db_path.rename(backup_path)
                logger.info(f"Поврежденная БД перемещена в {backup_path}")

            # Создаем новую БД
            init_db()
            logger.info("Создана новая БД")
        except Exception as recovery_error:
            logger.error(f"Не удалось восстановить БД: {recovery_error}")

    # Создаем админа
    try:
        admin_login = os.getenv("ADMIN_LOGIN", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        create_admin(admin_login, admin_password)
        logger.info("Админ создан/обновлен успешно")
    except Exception as e:
        logger.error(f"Ошибка создания админа: {e}")

    # Запускаем планировщики
    start_db_maintenance()
    logger.info("Приложение запущено успешно")

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
