import os


import threading
import time as tm
import uuid
import re
from datetime import time, date
from datetime import timedelta
from pathlib import Path
from typing import List

import aiohttp
import jwt
import pytz
import schedule
from aiogram import Bot
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi import Query
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash
import sqlite3
from sqlalchemy.exc import OperationalError, DatabaseError
from contextlib import contextmanager
from yookassa import Payment, Refund, Configuration


# Импорты моделей и утилит
from models.models import *
from models.models import engine, Session, init_db, create_admin
from utils.logger import get_logger

logger = get_logger(__name__)
app = FastAPI()

# Настройки
AVATARS_DIR = Path(__file__).parent / "avatars"
AVATARS_DIR.mkdir(exist_ok=True)
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

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
    visit_time: Optional[time]
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
    visit_time: Optional[time] = None
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


# Контекстный менеджер для повторных попыток операций с БД
@contextmanager
def db_retry_context(max_retries=3, delay=0.1):
    """Контекстный менеджер для повторных попыток операций с БД."""
    for attempt in range(max_retries):
        try:
            yield
            break
        except (OperationalError, DatabaseError, sqlite3.OperationalError) as e:
            if attempt == max_retries - 1:
                logger.error(f"Ошибка БД после {max_retries} попыток: {e}")
                raise

            error_message = str(e).lower()
            if (
                "disk i/o error" in error_message
                or "database is locked" in error_message
            ):
                logger.warning(f"Попытка {attempt + 1}/{max_retries}: {e}")
                tm.sleep(delay * (attempt + 1))  # Экспоненциальная задержка
            else:
                raise


def get_db():
    """Получение сессии БД с повторными попытками."""
    db = Session()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка сессии БД: {e}")
        raise
    finally:
        try:
            db.close()
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
                time_obj = datetime.strptime(str(visit_time), "%H:%M:%S").time()
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
async def get_users(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение списка всех пользователей."""
    users = db.query(User).order_by(User.first_join_time.desc()).all()
    return users


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
async def update_user_by_telegram_id(
    telegram_id: int, user_data: UserUpdate, db: Session = Depends(get_db)
):
    """Обновление пользователя по telegram_id."""
    try:
        with db_retry_context():
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            update_dict = user_data.dict(exclude_unset=True)

            for field, value in update_dict.items():
                if hasattr(user, field):
                    setattr(user, field, value)

            db.commit()
            db.refresh(user)

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
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка обновления пользователя: {str(e)}"
        )


@app.post("/users/check_and_add")
async def check_and_add_user(
    telegram_id: int,
    username: Optional[str] = None,
    language_code: str = "ru",
    referrer_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Проверка и добавление пользователя в БД. Используется ботом при команде /start.
    Фиксирует дату первого обращения (first_join_time).
    """
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
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
        db.add(user)
        db.commit()
        db.refresh(user)
        is_new = True

        # Обновляем счетчик приглашений у реферера
        if referrer_id:
            referrer = db.query(User).filter_by(telegram_id=referrer_id).first()
            if referrer:
                referrer.invited_count += 1
                db.commit()
    else:
        # Обновляем username, если изменился
        if username and user.username != username:
            user.username = username
            db.commit()

    # Проверяем полноту регистрации
    is_complete = all([user.full_name, user.phone, user.email, user.agreed_to_terms])

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


@app.put("/users/{user_identifier}")
async def update_user(
    user_identifier: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    with db_retry_context():
        # Пробуем найти пользователя по ID или по telegram_id
        user = None

        # Сначала пробуем как обычный ID
        if user_identifier.isdigit():
            user_id = int(user_identifier)
            user = db.query(User).filter(User.id == user_id).first()

        # Если не найден, пробуем как telegram_id
        if not user and user_identifier.isdigit():
            telegram_id = int(user_identifier)
            user = db.query(User).filter(User.telegram_id == telegram_id).first()

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

        db.commit()
        db.refresh(user)
        return user


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
            old_avatar_path.unlink()

    # Сохраняем новый аватар
    avatar_filename = f"{user.telegram_id}.jpg"
    avatar_path = AVATARS_DIR / avatar_filename

    contents = await file.read()
    with open(avatar_path, "wb") as f:
        f.write(contents)

    # Обновляем запись в БД
    user.avatar = avatar_filename
    db.commit()

    return {"message": "Avatar uploaded successfully", "filename": avatar_filename}


@app.delete("/users/{user_id}/avatar")
async def delete_avatar(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление аватара пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = False
    if user.avatar:
        avatar_path = AVATARS_DIR / user.avatar
        if avatar_path.exists():
            avatar_path.unlink()
            deleted = True
        user.avatar = None
        db.commit()

    # Также удаляем стандартный файл аватара, если существует
    standard_path = AVATARS_DIR / f"{user.telegram_id}.jpg"
    if standard_path.exists():
        standard_path.unlink()
        deleted = True

    return {"deleted": deleted}


@app.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Получение аватара по имени файла."""
    file_path = AVATARS_DIR / filename
    if not file_path.exists():
        # Возвращаем заглушку, если файл не найден
        placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
        if placeholder_path.exists():
            return FileResponse(placeholder_path)
        raise HTTPException(status_code=404, detail="Avatar not found")

    return FileResponse(file_path)


# ================== BOOKING ENDPOINTS ==================


@app.get("/bookings/detailed")
async def get_bookings_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение бронирований с данными тарифов (оптимизированная версия)."""
    try:
        # Базовый запрос с eager loading тарифа
        query = db.query(Booking).options(joinedload(Booking.tariff))

        # Фильтрация по дате
        if date_query:
            try:
                if date_query.count("-") == 2:
                    query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                elif date_query.count(".") == 2:
                    query_date = datetime.strptime(date_query, "%d.%m.%Y").date()
                else:
                    raise ValueError("Unsupported date format")
                query = query.filter(Booking.visit_date == query_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD or DD.MM.YYYY",
                )

        # Фильтрация по статусу
        if status_filter:
            if status_filter == "paid":
                query = query.filter(Booking.paid == True)
            elif status_filter == "unpaid":
                query = query.filter(Booking.paid == False)
            elif status_filter == "confirmed":
                query = query.filter(Booking.confirmed == True)
            elif status_filter == "pending":
                query = query.filter(Booking.confirmed == False)

        # Получаем общее количество
        total_count = query.count()

        # Применяем пагинацию и сортировку
        bookings = (
            query.order_by(Booking.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # Формируем ответ с использованием relationship
        enriched_bookings = []
        for booking in bookings:
            booking_item = {
                "id": int(booking.id),
                "user_id": int(booking.user_id),
                "tariff_id": int(booking.tariff_id),
                "visit_date": booking.visit_date.isoformat(),
                "visit_time": (
                    booking.visit_time.isoformat() if booking.visit_time else None
                ),
                "duration": int(booking.duration) if booking.duration else None,
                "promocode_id": (
                    int(booking.promocode_id) if booking.promocode_id else None
                ),
                "amount": float(booking.amount),
                "payment_id": booking.payment_id,
                "paid": bool(booking.paid),
                "rubitime_id": booking.rubitime_id,
                "confirmed": bool(booking.confirmed),
                "created_at": booking.created_at.isoformat(),
                # Используем relationship для получения тарифа
                "tariff": (
                    {
                        "id": booking.tariff.id,
                        "name": booking.tariff.name,
                        "price": float(booking.tariff.price),
                        "description": booking.tariff.description,
                        "purpose": booking.tariff.purpose,
                        "is_active": bool(booking.tariff.is_active),
                    }
                    if booking.tariff
                    else {
                        "id": booking.tariff_id,
                        "name": f"Тариф #{booking.tariff_id} (удален)",
                        "price": 0.0,
                        "description": "Тариф не найден",
                        "purpose": None,
                        "is_active": False,
                    }
                ),
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении бронирований: {e}")
        import traceback

        logger.error(f"Полный traceback: {traceback.format_exc()}")

        # Fallback на простую версию без тарифов
        try:
            logger.info("Пытаемся fallback на простую версию...")
            query = db.query(Booking)

            if status_filter:
                if status_filter == "paid":
                    query = query.filter(Booking.paid == True)
                elif status_filter == "unpaid":
                    query = query.filter(Booking.paid == False)
                elif status_filter == "confirmed":
                    query = query.filter(Booking.confirmed == True)
                elif status_filter == "pending":
                    query = query.filter(Booking.confirmed == False)

            total_count = query.count()
            bookings = (
                query.order_by(Booking.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            simple_bookings = []
            for booking in bookings:
                booking_item = {
                    "id": int(booking.id),
                    "user_id": int(booking.user_id),
                    "tariff_id": int(booking.tariff_id),
                    "visit_date": booking.visit_date.isoformat(),
                    "visit_time": (
                        booking.visit_time.isoformat() if booking.visit_time else None
                    ),
                    "duration": int(booking.duration) if booking.duration else None,
                    "promocode_id": (
                        int(booking.promocode_id) if booking.promocode_id else None
                    ),
                    "amount": float(booking.amount),
                    "payment_id": booking.payment_id,
                    "paid": bool(booking.paid),
                    "rubitime_id": booking.rubitime_id,
                    "confirmed": bool(booking.confirmed),
                    "created_at": booking.created_at.isoformat(),
                    # Fallback тариф
                    "tariff": {
                        "id": booking.tariff_id,
                        "name": f"Тариф #{booking.tariff_id}",
                        "price": 0.0,
                        "description": "Данные тарифа недоступны",
                        "purpose": None,
                        "is_active": True,
                    },
                }
                simple_bookings.append(booking_item)

            total_pages = (total_count + per_page - 1) // per_page

            return {
                "bookings": simple_bookings,
                "total_count": int(total_count),
                "page": int(page),
                "per_page": int(per_page),
                "total_pages": int(total_pages),
            }

        except Exception as fallback_error:
            logger.error(f"Fallback также не удался: {fallback_error}")
            raise HTTPException(
                status_code=500, detail=f"Critical server error: {str(e)}"
            )


# 2. СТАТИЧЕСКИЙ маршрут /bookings/stats
@app.get("/bookings/stats")
async def get_booking_stats(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение статистики по бронированиям."""
    try:
        total_bookings = db.query(Booking).count()
        paid_bookings = db.query(Booking).filter(Booking.paid == True).count()
        confirmed_bookings = db.query(Booking).filter(Booking.confirmed == True).count()

        # Общая сумма оплаченных бронирований
        total_revenue = (
            db.query(func.sum(Booking.amount)).filter(Booking.paid == True).scalar()
            or 0
        )

        # Статистика по текущему месяцу
        current_month_start = datetime.now(MOSCOW_TZ).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        current_month_bookings = (
            db.query(Booking).filter(Booking.created_at >= current_month_start).count()
        )
        current_month_revenue = (
            db.query(func.sum(Booking.amount))
            .filter(Booking.created_at >= current_month_start, Booking.paid == True)
            .scalar()
            or 0
        )

        # Топ тарифы по количеству бронирований
        top_tariffs = (
            db.query(Tariff.name, func.count(Booking.id).label("booking_count"))
            .join(Booking)
            .group_by(Tariff.id, Tariff.name)
            .order_by(func.count(Booking.id).desc())
            .limit(5)
            .all()
        )

        return {
            "total_bookings": total_bookings,
            "paid_bookings": paid_bookings,
            "confirmed_bookings": confirmed_bookings,
            "total_revenue": float(total_revenue),
            "current_month_bookings": current_month_bookings,
            "current_month_revenue": float(current_month_revenue),
            "top_tariffs": [
                {"name": tariff.name, "count": tariff.booking_count}
                for tariff in top_tariffs
            ],
        }

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


# 4. СОЗДАНИЕ бронирования
@app.post("/bookings", response_model=BookingBase)
async def create_booking(booking_data: BookingCreate, db: Session = Depends(get_db)):
    logger.info(
        f"Создание бронирования: user_id={booking_data.user_id}, tariff_id={booking_data.tariff_id}, promocode_id={booking_data.promocode_id}"
    )

    with db_retry_context():
        # Находим пользователя
        user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
        if not user:
            logger.error(f"Пользователь с telegram_id {booking_data.user_id} не найден")
            raise HTTPException(status_code=404, detail="User not found")

        # Находим тариф
        tariff = db.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        if not tariff:
            logger.error(f"Тариф с ID {booking_data.tariff_id} не найден")
            raise HTTPException(status_code=404, detail="Tariff not found")

        amount = booking_data.amount
        promocode = None

        # Обработка промокода
        if booking_data.promocode_id:
            logger.info(f"Обработка промокода ID: {booking_data.promocode_id}")

            promocode = (
                db.query(Promocode)
                .filter(Promocode.id == booking_data.promocode_id)
                .first()
            )

            if not promocode:
                logger.error(f"Промокод с ID {booking_data.promocode_id} не найден")
                raise HTTPException(status_code=404, detail="Promocode not found")

            logger.info(
                f"Найден промокод: {promocode.name}, скидка: {promocode.discount}%, осталось использований: {promocode.usage_quantity}"
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

            # КРИТИЧЕСКИ ВАЖНО: Уменьшаем счетчик использований промокода
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

        db.add(booking)

        # Коммитим все изменения сразу (и бронирование, и промокод)
        try:
            db.commit()
            db.refresh(booking)
            logger.info(f"✅ Создано бронирование #{booking.id} с суммой {amount} ₽")

            if promocode:
                logger.info(
                    f"✅ Промокод {promocode.name} успешно использован, осталось: {promocode.usage_quantity}"
                )

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Ошибка при сохранении бронирования: {e}")
            raise HTTPException(status_code=500, detail="Failed to create booking")

        # Создаем уведомление в БД
        notification = Notification(
            user_id=user.id,
            message=f"Создана новая бронь от {user.full_name or 'пользователя'}",
            target_url=f"/bookings/{booking.id}",
            booking_id=booking.id,
        )
        db.add(notification)

        # Обновляем счетчик успешных бронирований ТОЛЬКО если оплачено
        if booking_data.paid:
            old_bookings = user.successful_bookings or 0
            user.successful_bookings = old_bookings + 1
            logger.info(
                f"👤 Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        # Финальный коммит для уведомления и счетчика пользователя
        try:
            db.commit()
            logger.info("✅ Уведомление и счетчики обновлены")
        except Exception as e:
            logger.error(f"❌ Ошибка при сохранении уведомления: {e}")
            # Не критично, бронирование уже создано

        return booking


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


@app.get("/newsletters", response_model=List[NewsletterBase])
async def get_newsletters(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение списка рассылок."""
    newsletters = (
        db.query(Newsletter)
        .order_by(Newsletter.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return newsletters


@app.post("/newsletters")
async def create_newsletter(
    newsletter_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Создание новой рассылки."""
    message = newsletter_data.get("message", "")
    if not message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Подсчитываем количество получателей
    users = db.query(User).all()
    newsletter = Newsletter(message=message, recipient_count=len(users))

    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)

    # Отправляем рассылку через бота
    if bot:
        sent_count = 0
        for user in users:
            try:
                await bot.send_message(user.telegram_id, message)
                sent_count += 1
            except Exception as e:
                logger.error(
                    f"Не удалось отправить сообщение пользователю {user.telegram_id}: {e}"
                )

        logger.info(f"Рассылка отправлена {sent_count} из {len(users)} пользователей")

    return {"id": newsletter.id, "message": "Newsletter sent", "recipients": len(users)}


# ================== DASHBOARD ENDPOINTS ==================


@app.get("/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение статистики для дашборда."""
    total_users = db.query(User).count()
    total_bookings = db.query(Booking).count()
    open_tickets = db.query(Ticket).filter(Ticket.status != TicketStatus.CLOSED).count()
    active_tariffs = db.query(Tariff).filter(Tariff.is_active == True).count()

    return {
        "total_users": total_users,
        "total_bookings": total_bookings,
        "open_tickets": open_tickets,
        "active_tariffs": active_tariffs,
    }


# ================== TICKET ENDPOINTS ==================

# Создаем директорию для фото ответов
TICKET_PHOTOS_DIR = Path(__file__).parent / "ticket_photos"
TICKET_PHOTOS_DIR.mkdir(exist_ok=True)


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
        photo_id=ticket_data.photo_id,
        status=status_enum,
        comment=ticket_data.comment,
        created_at=datetime.now(MOSCOW_TZ),
        updated_at=datetime.now(MOSCOW_TZ),
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "message": "Ticket created successfully"}


# ================== STARTUP EVENT ==================


def optimize_database():
    """Оптимизация базы данных SQLite."""
    db_path = "data/coworking.db"

    if not os.path.exists(db_path):
        logger.warning(f"База данных не найдена: {db_path}")
        return

    try:
        # Создаем резервную копию
        backup_path = f"{db_path}.backup.{int(tm.time())}"
        import shutil

        shutil.copy2(db_path, backup_path)

        # Подключаемся напрямую к SQLite
        conn = sqlite3.connect(db_path, timeout=30)
        cursor = conn.cursor()

        # Выполняем оптимизацию
        cursor.execute("PRAGMA optimize")
        cursor.execute("VACUUM")
        cursor.execute("REINDEX")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")

        conn.commit()
        conn.close()

        logger.info("Оптимизация базы данных завершена успешно")

        # Удаляем старые бэкапы (оставляем только последние 3)
        backup_dir = Path("data")
        backup_files = sorted(backup_dir.glob("*.backup.*"))
        if len(backup_files) > 3:
            for old_backup in backup_files[:-3]:
                old_backup.unlink()
                logger.info(f"Удален старый бэкап: {old_backup}")

    except Exception as e:
        logger.error(f"Ошибка оптимизации БД: {e}")


def start_db_maintenance():
    """Запускает планировщик обслуживания БД."""
    import schedule

    # Оптимизация каждый день в 3:00
    schedule.every().day.at("03:00").do(optimize_database)

    # Проверка состояния каждые 10 минут
    def check_db_health():
        try:
            db_path = "data/coworking.db"
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path, timeout=5)
                conn.execute("SELECT 1")
                conn.close()
        except Exception as e:
            logger.warning(f"Проблема с БД обнаружена: {e}")

    schedule.every(10).minutes.do(check_db_health)

    def run_maintenance():
        while True:
            schedule.run_pending()
            tm.sleep(60)  # Проверяем каждую минуту

    maintenance_thread = threading.Thread(target=run_maintenance, daemon=True)
    maintenance_thread.start()
    logger.info("Планировщик обслуживания БД запущен")


@app.on_event("startup")
async def startup_event():
    logger.info("Запуск приложения...")

    # Диагностика путей и прав
    import os

    current_dir = os.getcwd()
    logger.info(f"Текущая рабочая директория: {current_dir}")

    # Создаем директории с правильными правами
    data_dir = Path("/app/data")
    avatars_dir = Path("/app/avatars")
    ticket_photos_dir = Path("/app/ticket_photos")

    for directory in [data_dir, avatars_dir, ticket_photos_dir]:
        try:
            directory.mkdir(exist_ok=True, parents=True)
            # Проверяем права на запись
            test_file = directory / "test_write"
            test_file.touch()
            test_file.unlink()
            logger.info(f"Директория {directory} создана и доступна для записи")
        except Exception as e:
            logger.error(f"Ошибка с директорией {directory}: {e}")

    # Проверяем путь к БД
    db_path = data_dir / "coworking.db"
    logger.info(f"Путь к БД: {db_path}")
    logger.info(f"БД существует: {db_path.exists()}")

    if db_path.exists():
        logger.info(f"Размер БД: {db_path.stat().st_size} байт")

    # Инициализируем БД
    try:
        logger.info("Инициализация БД...")
        init_db()
        logger.info("База данных инициализирована успешно")

        # Проверяем что БД действительно создалась
        if db_path.exists():
            logger.info(f"БД создана, размер: {db_path.stat().st_size} байт")
        else:
            logger.error("БД не была создана!")

    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        # Пробуем создать БД принудительно
        try:
            db_path.touch()
            logger.info("Файл БД создан принудительно")
        except Exception as create_error:
            logger.error(f"Не удалось создать файл БД: {create_error}")

    # Создаем админа
    try:
        admin_login = os.getenv("ADMIN_LOGIN", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        create_admin(admin_login, admin_password)
        logger.info("Админ создан успешно")
    except Exception as e:
        logger.error(f"Ошибка создания админа: {e}")

    logger.info("Запуск завершен")

    # Запускаем планировщики
    start_db_maintenance()

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
