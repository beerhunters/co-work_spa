import os
import threading
import time as tm
import uuid
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
from werkzeug.security import check_password_hash
from yookassa import Payment, Refund

# Импорты моделей и утилит
from models.models import *
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


# Модели для создания записей
class BookingCreate(BaseModel):
    user_id: int
    tariff_id: int
    visit_date: date
    visit_time: Optional[time] = None
    duration: Optional[int] = None
    promocode_id: Optional[int] = None
    amount: float
    payment_id: Optional[str] = None
    paid: bool = False
    confirmed: bool = False


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
    """Получение сессии базы данных."""
    db = Session()
    try:
        yield db
    finally:
        db.close()


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


@app.put("/users/{user_id}", response_model=UserBase)
async def update_user(
    user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)
):
    """Обновление данных пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляем только переданные поля
    update_dict = user_data.dict(exclude_unset=True)

    # Обрабатываем дату регистрации
    if "reg_date" in update_dict and update_dict["reg_date"]:
        try:
            update_dict["reg_date"] = datetime.fromisoformat(update_dict["reg_date"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid reg_date format")

    for field, value in update_dict.items():
        setattr(user, field, value)

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


@app.get("/bookings/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение бронирования по ID."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@app.post("/bookings", response_model=BookingBase)
async def create_booking(booking_data: BookingCreate, db: Session = Depends(get_db)):
    """Создание нового бронирования. Используется ботом."""
    user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tariff = db.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    # Вычисляем итоговую сумму с учетом промокода
    amount = booking_data.amount
    promocode = None
    if booking_data.promocode_id:
        promocode = (
            db.query(Promocode)
            .filter(Promocode.id == booking_data.promocode_id)
            .first()
        )
        if promocode and promocode.is_active:
            amount = amount * (1 - promocode.discount / 100)

    # Создаем запись в Rubitime, если нужно
    rubitime_id = None
    if tariff.service_id and booking_data.visit_time:
        rubitime_params = {
            "service_id": tariff.service_id,
            "datetime": f"{booking_data.visit_date} {booking_data.visit_time}",
            "duration": booking_data.duration or 60,
            "client_name": user.full_name or "Неизвестно",
            "client_phone": user.phone or "",
            "comment": f"Бронь из Telegram бота",
        }
        rubitime_id = await rubitime("create_record", rubitime_params)

    # Создаем бронирование
    booking = Booking(
        user_id=user.id,
        tariff_id=booking_data.tariff_id,
        visit_date=booking_data.visit_date,
        visit_time=booking_data.visit_time,
        duration=booking_data.duration,
        promocode_id=booking_data.promocode_id,
        amount=amount,
        payment_id=booking_data.payment_id,
        paid=booking_data.paid,
        confirmed=booking_data.confirmed,
        rubitime_id=rubitime_id,
        created_at=datetime.now(MOSCOW_TZ),
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Создаем уведомление админу
    booking_data_dict = {
        "tariff_name": tariff.name,
        "tariff_purpose": tariff.purpose,
        "visit_date": booking_data.visit_date,
        "visit_time": booking_data.visit_time,
        "duration": booking_data.duration,
        "amount": amount,
        "discount": promocode.discount if promocode else 0,
        "promocode_name": promocode.name if promocode else None,
    }

    admin_message = format_booking_notification(user, tariff, booking_data_dict)

    # Отправляем уведомление админу
    if bot and ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")

    # Создаем уведомление в БД
    notification = Notification(
        user_id=user.id,
        message="Создано новое бронирование",
        booking_id=booking.id,
        target_url="/bookings",
        created_at=datetime.now(MOSCOW_TZ),
    )
    db.add(notification)
    db.commit()

    return booking


@app.put("/bookings/{booking_id}", response_model=BookingBase)
async def update_booking(
    booking_id: int,
    confirmed: bool,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Подтверждение или отклонение бронирования."""
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.confirmed = confirmed
    db.commit()

    # Уведомляем пользователя
    if bot:
        user = db.query(User).get(booking.user_id)
        tariff = db.query(Tariff).get(booking.tariff_id)

        if confirmed:
            message = f"✅ Ваша бронь подтверждена!\n\n📋 Тариф: {tariff.name}\n📅 Дата: {booking.visit_date}"
        else:
            message = f"❌ Ваша бронь отклонена.\n\n📋 Тариф: {tariff.name}\n📅 Дата: {booking.visit_date}"

        try:
            await bot.send_message(user.telegram_id, message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю: {e}")

    return booking


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
    tariffs = db.query(Tariff).all()
    return tariffs


@app.get("/tariffs/{tariff_id}")
async def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    """Получение тарифа по ID. Используется ботом."""
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
    tariff_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Создание нового тарифа."""
    tariff = Tariff(**tariff_data)
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return tariff


@app.delete("/tariffs/{tariff_id}")
async def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тарифа."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    db.delete(tariff)
    db.commit()
    return {"message": "Tariff deleted"}


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
    import re

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
        import re

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


@app.get("/tickets/{ticket_id}", response_model=dict)
async def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение тикета по ID."""
    ticket = db.query(Ticket).join(User).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return {
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

    # Уведомляем админа
    ticket_data_dict = {
        "id": ticket.id,
        "description": ticket.description,
        "status": ticket.status.value,
        "photo_id": ticket.photo_id,
        "created_at": ticket.created_at,
    }

    return {"id": ticket.id, "message": "Ticket created successfully"}


@app.get("/users/telegram/{telegram_id}/tickets")
async def get_user_tickets_by_telegram_id(
    telegram_id: int, status: Optional[str] = None, db: Session = Depends(get_db)
):
    """Получение тикетов пользователя по Telegram ID. Используется ботом."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []

    query = db.query(Ticket).filter(Ticket.user_id == user.id)

    if status:
        try:
            status_enum = TicketStatus[status]
            query = query.filter(Ticket.status == status_enum)
        except KeyError:
            pass

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return [
        {
            "id": t.id,
            "description": t.description,
            "status": t.status.value,
            "photo_id": t.photo_id,
            "comment": t.comment,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in tickets
    ]


@app.put("/tickets/{ticket_id}")
async def update_ticket_status(
    ticket_id: int,
    status_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление статуса тикета с возможностью добавления фото."""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Запрещаем редактирование закрытых тикетов
    if ticket.status == TicketStatus.CLOSED:
        # Разрешаем только если явно меняем статус с CLOSED (что и так запрещено выше)
        new_status = status_data.get("status")
        if new_status and new_status != "CLOSED":
            raise HTTPException(
                status_code=400, detail="Закрытые тикеты нельзя редактировать"
            )
        elif not new_status:  # Если пытаются изменить только комментарий
            raise HTTPException(
                status_code=400, detail="Закрытые тикеты нельзя редактировать"
            )

    new_status = status_data.get("status")
    comment = status_data.get("comment")
    response_photo_id = status_data.get("response_photo_id")

    # Валидация статуса и комментария
    if new_status:
        # Проверяем валидность статуса
        valid_statuses = ["OPEN", "IN_PROGRESS", "CLOSED"]
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Invalid status")

        # Проверяем логику переходов статусов
        current_status = ticket.status.name

        # Разрешенные переходы (более строгая логика)
        allowed_transitions = {
            "OPEN": ["IN_PROGRESS", "CLOSED"],
            "IN_PROGRESS": ["CLOSED"],  # Из "В работе" можно только закрыть
            "CLOSED": [],  # Из "Закрыта" никуда нельзя перейти
        }

        if new_status != current_status:
            if (
                not allowed_transitions.get(current_status)
                or new_status not in allowed_transitions[current_status]
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Недопустимый переход статуса с '{current_status}' на '{new_status}'",
                )

        # Если закрываем тикет, комментарий обязателен
        if new_status == "CLOSED" and not comment and not ticket.comment:
            raise HTTPException(
                status_code=400, detail="Comment is required when closing a ticket"
            )

        try:
            ticket.status = TicketStatus[new_status]
        except (ValueError, KeyError):
            raise HTTPException(status_code=400, detail="Invalid status")

    # Обновляем комментарий
    if comment is not None:
        ticket.comment = comment

    # Обновляем ID фото ответа
    if response_photo_id is not None:
        ticket.response_photo_id = response_photo_id

    ticket.updated_at = datetime.now(MOSCOW_TZ)

    try:
        db.commit()

        # Уведомляем пользователя
        if bot:
            user = db.query(User).get(ticket.user_id)
            if user:
                status_text = {
                    TicketStatus.OPEN: "🟢 Открыта",
                    TicketStatus.IN_PROGRESS: "🟡 В работе",
                    TicketStatus.CLOSED: "🔴 Закрыта",
                }

                message = f"📋 <b>Обращение #{ticket.id}</b>\n"
                message += f"📊 <b>Статус:</b> {status_text.get(ticket.status, 'Обновлен')}\n\n"

                if ticket.comment:
                    message += f"💬 <b>Ответ администратора:</b>\n{ticket.comment}\n\n"

                message += f"⏰ <b>Время обновления:</b> {ticket.updated_at.strftime('%d.%m.%Y %H:%M')}"

                try:
                    # Отправляем текстовое сообщение
                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")

                    # Если есть фото в ответе, отправляем его
                    if ticket.response_photo_id:
                        photo_path = TICKET_PHOTOS_DIR / ticket.response_photo_id
                        if photo_path.exists():
                            try:
                                from aiogram.types import FSInputFile

                                photo_file = FSInputFile(photo_path)
                                await bot.send_photo(
                                    user.telegram_id,
                                    photo_file,
                                    caption="📸 Прикрепленное фото от администратора",
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки фото пользователю: {e}")

                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление пользователю: {e}")

        return {"message": "Ticket updated successfully", "ticket_id": ticket.id}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления тикета: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ticket")


# Настройки для очистки файлов (в днях)
FILE_RETENTION_DAYS = int(
    os.getenv("FILE_RETENTION_DAYS", "30")
)  # По умолчанию 30 дней
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))  # По умолчанию 10MB


def cleanup_old_files():
    """Удаляет старые файлы тикетов"""
    try:
        cutoff_date = datetime.now() - timedelta(days=FILE_RETENTION_DAYS)
        deleted_count = 0

        # Очищаем файлы фото тикетов
        for file_path in TICKET_PHOTOS_DIR.glob("*"):
            if file_path.is_file():
                file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_age < cutoff_date:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Удален старый файл: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления файла {file_path}: {e}")

        if deleted_count > 0:
            logger.info(f"Очистка завершена. Удалено файлов: {deleted_count}")

    except Exception as e:
        logger.error(f"Ошибка при очистке файлов: {e}")


def start_cleanup_scheduler():
    """Запускает планировщик очистки файлов"""
    schedule.every().day.at("02:00").do(cleanup_old_files)  # Каждый день в 2:00

    def run_scheduler():
        while True:
            schedule.run_pending()
            tm.sleep(3600)  # Проверяем каждый час

    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info(
        f"Планировщик очистки файлов запущен. Срок хранения: {FILE_RETENTION_DAYS} дней"
    )


# Обновленный эндпоинт загрузки фото с улучшенной валидацией:
@app.post("/tickets/{ticket_id}/photo")
async def upload_ticket_response_photo(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Загрузка фото для ответа администратора."""
    # Проверяем существование тикета
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")

    # Проверяем тип файла
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Файл должен быть изображением (JPEG, PNG, GIF, WebP)",
        )

    # Читаем файл для проверки размера
    file_content = await file.read()
    file_size_mb = len(file_content) / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Размер файла ({file_size_mb:.1f} МБ) превышает максимально допустимый ({MAX_FILE_SIZE_MB} МБ)",
        )

    # Проверяем допустимые расширения
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    file_extension = Path(file.filename).suffix.lower() if file.filename else ".jpg"

    if file_extension not in allowed_extensions:
        file_extension = ".jpg"

    # Генерируем уникальное имя файла
    photo_id = f"{uuid.uuid4()}{file_extension}"
    photo_path = TICKET_PHOTOS_DIR / photo_id

    try:
        # Сохраняем файл
        with open(photo_path, "wb") as buffer:
            buffer.write(file_content)

        logger.info(
            f"Фото для тикета {ticket_id} загружено: {photo_id} ({file_size_mb:.1f} МБ)"
        )
        return {
            "photo_id": photo_id,
            "message": "Фото успешно загружено",
            "file_size_mb": round(file_size_mb, 1),
        }

    except Exception as e:
        logger.error(f"Ошибка загрузки фото для тикета {ticket_id}: {e}")
        # Удаляем файл если он был частично создан
        if photo_path.exists():
            try:
                photo_path.unlink()
            except:
                pass
        raise HTTPException(status_code=500, detail="Не удалось загрузить фото")


@app.get("/tickets/{ticket_id}/photo")
async def get_ticket_photo(ticket_id: int, db: Session = Depends(get_db)):
    """Получение фото тикета (от пользователя)."""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket or not ticket.photo_id:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Если это локальный файл (содержит расширение), возвращаем его
    if "." in ticket.photo_id:
        photo_path = TICKET_PHOTOS_DIR / ticket.photo_id
        if photo_path.exists():
            return FileResponse(photo_path)

    # Если это Telegram file_id, скачиваем файл
    if bot:
        try:
            file_info = await bot.get_file(ticket.photo_id)
            file_url = (
                f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            )

            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as resp:
                    if resp.status == 200:
                        # Сохраняем файл локально для кэширования
                        photo_path = (
                            TICKET_PHOTOS_DIR / f"telegram_{ticket.photo_id}.jpg"
                        )
                        with open(photo_path, "wb") as f:
                            f.write(await resp.read())
                        return FileResponse(photo_path)
        except Exception as e:
            logger.error(f"Ошибка получения фото из Telegram: {e}")

    raise HTTPException(status_code=404, detail="Photo not found")


@app.delete("/tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тикета."""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Удаляем связанные файлы
    if ticket.response_photo_id:
        photo_path = TICKET_PHOTOS_DIR / ticket.response_photo_id
        if photo_path.exists():
            try:
                photo_path.unlink()
                logger.info(f"Удален файл фото: {photo_path}")
            except Exception as e:
                logger.error(f"Ошибка удаления файла {photo_path}: {e}")

    db.delete(ticket)
    db.commit()
    return {"message": "Ticket deleted"}


@app.get("/tickets/stats")
async def get_tickets_stats(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение статистики по тикетам."""
    total_tickets = db.query(Ticket).count()
    open_tickets = db.query(Ticket).filter(Ticket.status == TicketStatus.OPEN).count()
    in_progress_tickets = (
        db.query(Ticket).filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
    )
    closed_tickets = (
        db.query(Ticket).filter(Ticket.status == TicketStatus.CLOSED).count()
    )

    # Расчет среднего времени решения
    closed_tickets_times = (
        db.query(Ticket)
        .filter(Ticket.status == TicketStatus.CLOSED)
        .filter(Ticket.updated_at.isnot(None))
        .all()
    )

    avg_resolution_time = 0
    if closed_tickets_times:
        total_time = sum(
            (t.updated_at - t.created_at).total_seconds() / 3600
            for t in closed_tickets_times
        )
        avg_resolution_time = round(total_time / len(closed_tickets_times), 1)

    return {
        "total": total_tickets,
        "open": open_tickets,
        "in_progress": in_progress_tickets,
        "closed": closed_tickets,
        "avg_resolution_hours": avg_resolution_time,
    }


# ================== NOTIFICATION ENDPOINTS ==================


@app.get("/notifications", response_model=List[NotificationBase])
async def get_notifications(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение всех уведомлений."""
    notifications = (
        db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()
    )
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
    return {"message": "Notification marked as read"}


@app.post("/notifications/mark_all_read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Пометить все уведомления как прочитанные."""
    db.query(Notification).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}


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

    # Проверяем существование пользователя
    user = db.query(User).get(user_id)
    if not user:
        # Если передан user_id как telegram_id, пытаемся найти по нему
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = user.id

    # Создаем уведомление в БД
    notification = Notification(
        user_id=user_id,
        message=message,
        target_url=target_url,
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


# ================== EXTERNAL API HELPERS ==================


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    """Взаимодействие с Rubitime API."""
    if not RUBITIME_API_KEY:
        logger.warning("RUBITIME_API_KEY не настроен")
        return None

    if method == "create_record":
        url = f"{RUBITIME_BASE_URL}create-record"
        params = {"api_key": RUBITIME_API_KEY, **extra_params}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("record_id")
        except Exception as e:
            logger.error(f"Ошибка Rubitime API: {e}")

    return None


async def check_payment_status(payment_id: str) -> Optional[str]:
    """Проверка статуса платежа через YooKassa."""
    try:
        payment = await Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        return None


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


# ================== BOT-SPECIFIC ENDPOINTS ==================
# Эти эндпоинты используются только ботом и не требуют авторизации


@app.post("/bot/tickets")
async def create_ticket_from_bot(ticket_data: dict, db: Session = Depends(get_db)):
    """Создание тикета из бота."""
    telegram_id = ticket_data.get("user_id")
    description = ticket_data.get("description", "")
    photo_id = ticket_data.get("photo_id")
    status_str = ticket_data.get("status", "OPEN")

    # Находим пользователя
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Определяем статус
    try:
        status_enum = TicketStatus[status_str]
    except KeyError:
        status_enum = TicketStatus.OPEN

    # Создаем тикет
    ticket = Ticket(
        user_id=user.id,
        description=description,
        photo_id=photo_id,
        status=status_enum,
        created_at=datetime.now(MOSCOW_TZ),
        updated_at=datetime.now(MOSCOW_TZ),
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "message": "Ticket created successfully"}


@app.get("/bot/users/{telegram_id}/tickets")
async def get_user_tickets_by_telegram_id(
    telegram_id: int, status: Optional[str] = None, db: Session = Depends(get_db)
):
    """Получение тикетов пользователя по Telegram ID."""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []

    query = db.query(Ticket).filter(Ticket.user_id == user.id)

    if status:
        try:
            status_enum = TicketStatus[status]
            query = query.filter(Ticket.status == status_enum)
        except KeyError:
            pass

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return [
        {
            "id": t.id,
            "description": t.description,
            "status": t.status.value,
            "photo_id": t.photo_id,
            "comment": t.comment,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
        for t in tickets
    ]


@app.post("/bot/rubitime")
async def create_rubitime_record_from_bot(rubitime_params: dict):
    """Создание записи в Rubitime из бота."""
    rubitime_id = await rubitime("create_record", rubitime_params)
    return {"rubitime_id": rubitime_id}


@app.post("/admin/cleanup-files")
async def manual_cleanup(
    days: int = Query(
        FILE_RETENTION_DAYS, description="Количество дней для хранения файлов"
    ),
    _: str = Depends(verify_token),
):
    """Ручная очистка старых файлов."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        total_size_mb = 0

        for file_path in TICKET_PHOTOS_DIR.glob("*"):
            if file_path.is_file():
                file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_age < cutoff_date:
                    try:
                        file_size = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        deleted_count += 1
                        total_size_mb += file_size
                        logger.info(f"Удален файл: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления файла {file_path}: {e}")

        return {
            "message": f"Очистка завершена",
            "deleted_files": deleted_count,
            "freed_space_mb": round(total_size_mb, 1),
            "retention_days": days,
        }

    except Exception as e:
        logger.error(f"Ошибка при ручной очистке: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при очистке файлов")


# ================== STARTUP EVENT ==================


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    init_db()
    # Запускаем планировщик очистки файлов
    start_cleanup_scheduler()

    # Создаем директории если их нет
    TICKET_PHOTOS_DIR.mkdir(exist_ok=True)
    AVATARS_DIR.mkdir(exist_ok=True)

    admin_login = os.getenv("ADMIN_LOGIN", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    create_admin(admin_login, admin_password)

    # Создаем placeholder аватар если его нет
    placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
    if not placeholder_path.exists():
        # Создаем простой placeholder (серый квадрат)
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (200, 200), color="#E2E8F0")
            draw = ImageDraw.Draw(img)
            # Рисуем круг
            draw.ellipse([10, 10, 190, 190], fill="#CBD5E0")
            # Рисуем силуэт пользователя
            draw.ellipse([75, 50, 125, 100], fill="#718096")  # голова
            draw.ellipse([50, 100, 150, 180], fill="#718096")  # тело
            img.save(placeholder_path)
            logger.info("Placeholder avatar created")
        except ImportError:
            logger.warning("PIL not installed, placeholder avatar not created")

    logger.info("Application started successfully")
