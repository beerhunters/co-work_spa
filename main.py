import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, date, time
from typing import List, Optional

import pytz
from fastapi import Depends, FastAPI, HTTPException, status, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash

from models.models import (
    Admin,
    User,
    Tariff,
    Promocode,
    Booking,
    Newsletter,
    Ticket,
    Notification,
    init_db,
    create_admin,
    Session as DBSession,
    format_booking_notification,
    TicketStatus,
    format_ticket_notification,
)
from utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

try:
    from aiogram import Bot

    bot = Bot(token=BOT_TOKEN)
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    bot = None

RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = "https://rubitime.ru/api2/"


class AdminBase(BaseModel):
    login: str
    password: str


class UserBase(BaseModel):
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


class TariffBase(BaseModel):
    id: int
    name: str
    description: str
    price: float
    purpose: Optional[str]
    service_id: Optional[int]
    is_active: bool


class PromocodeBase(BaseModel):
    id: int
    name: str
    discount: int
    usage_quantity: int
    expiration_date: Optional[datetime]
    is_active: bool


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


class BookingCreate(BaseModel):
    user_id: int
    tariff_id: int
    visit_date: date
    visit_time: Optional[time] = None
    duration: Optional[int] = None
    promocode_id: Optional[int] = None
    amount: float


class TicketCreate(BaseModel):
    user_id: int
    description: str
    photo_id: Optional[str] = None
    status: Optional[str] = "OPEN"
    comment: Optional[str] = None


class NotificationUpdate(BaseModel):
    is_read: bool = True


@app.get("/")
async def root():
    return {"message": "Admin Panel API"}


def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


security = HTTPBasic()


def get_current_admin(
    credentials: HTTPBasicCredentials = Depends(security), db: Session = Depends(get_db)
):
    admin = db.query(Admin).filter(Admin.login == credentials.username).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return admin


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    try:
        import aiohttp

        url = f"{RUBITIME_BASE_URL}create-record"
        params = {"api_key": RUBITIME_API_KEY, **extra_params}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params) as response:
                data = await response.json()
                return data.get("id")
    except Exception as e:
        logger.error(f"Ошибка Rubitime API: {e}")
        return None


async def check_payment_status(payment_id: str) -> Optional[str]:
    try:
        from yookassa import Payment

        payment = await Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        return None


@app.post("/login", response_model=dict)
async def login(credentials: AdminBase, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Неверные учетные данные")
    return {"message": "Успешный вход"}


@app.get("/logout")
async def logout():
    return {"message": "Успешный выход"}


@app.get("/users", response_model=List[UserBase])
async def get_users(page: int = 1, per_page: int = 20, db: Session = Depends(get_db)):
    users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
    return users


@app.get("/users/{user_id}", response_model=UserBase)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


# @app.get("/bookings", response_model=List[BookingBase])
# async def get_bookings(
#     page: int = 1,
#     per_page: int = 20,
#     user_query: Optional[str] = None,
#     date_query: Optional[str] = None,
#     db: Session = Depends(get_db),
# ):
#     query = db.query(Booking)
#
#     if user_query:
#         query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))
#
#     if date_query:
#         try:
#             query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
#             query = query.filter(Booking.visit_date == query_date)
#         except ValueError:
#             raise HTTPException(status_code=400, detail="Неверный формат даты")
#
#     bookings = (
#         query.order_by(desc(Booking.created_at))
#         .offset((page - 1) * per_page)
#         .limit(per_page)
#         .all()
#     )
#     return bookings
@app.get("/bookings", response_model=List[BookingBase])
async def get_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    user_query: str = Query(None),
    date_query: str = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        query = db.query(Booking).order_by(Booking.created_at.desc())

        if user_query:
            query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))

        if date_query:
            try:
                query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                query = query.filter(Booking.visit_date == query_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат даты")

        bookings = query.offset((page - 1) * per_page).limit(per_page).all()
        return bookings
    except Exception as e:
        logger.error(f"Ошибка получения бронирований: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# @app.get("/bookings/{booking_id}", response_model=BookingBase)
# async def get_booking(booking_id: int, db: Session = Depends(get_db)):
#     booking = db.query(Booking).get(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Бронирование не найдено")
#     return booking
@app.get("/bookings/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")
    return booking


# @app.post("/bookings", response_model=dict)
# async def create_booking(booking_data: BookingBase, db: Session = Depends(get_db)):
#     try:
#         from models.models import create_booking, format_booking_notification
#
#         user = db.query(User).get(booking_data.user_id)
#         if not user:
#             raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#         tariff = db.query(Tariff).get(booking_data.tariff_id)
#         if not tariff:
#             raise HTTPException(status_code=404, detail="Тариф не найден")
#
#         promocode = None
#         if booking_data.promocode_id:
#             promocode = (
#                 db.query(Promocode)
#                 .filter(
#                     Promocode.id == booking_data.promocode_id,
#                     Promocode.is_active == True,
#                 )
#                 .first()
#             )
#
#         amount = booking_data.amount
#         if promocode:
#             amount = amount * (1 - promocode.discount / 100)
#
#         rubitime_params = {
#             "service_id": tariff.service_id,
#             "client_name": user.full_name,
#             "client_phone": user.phone,
#             "date": str(booking_data.visit_date),
#             "time": str(booking_data.visit_time) if booking_data.visit_time else None,
#             "duration": booking_data.duration,
#         }
#
#         rubitime_id = await rubitime("create_record", rubitime_params)
#
#         # Создание платежа через YooKassa
#         try:
#             from yookassa import Payment
#
#             payment = await Payment.create(
#                 {
#                     "amount": {"value": str(amount), "currency": "RUB"},
#                     "confirmation": {
#                         "type": "redirect",
#                         "return_url": "https://example.com/return",
#                     },
#                     "description": f"Бронирование {tariff.name}",
#                 }
#             )
#             payment_id = payment.id
#         except Exception as e:
#             logger.error(f"Ошибка создания платежа: {e}")
#             payment_id = None
#
#         booking = Booking(
#             user_id=booking_data.user_id,
#             tariff_id=booking_data.tariff_id,
#             visit_date=booking_data.visit_date,
#             visit_time=booking_data.visit_time,
#             duration=booking_data.duration,
#             promocode_id=booking_data.promocode_id,
#             amount=amount,
#             payment_id=payment_id,
#             rubitime_id=rubitime_id,
#             created_at=datetime.now(MOSCOW_TZ),
#         )
#
#         db.add(booking)
#         db.commit()
#         db.refresh(booking)
#
#         # Отправка уведомления админу
#         admin_message = format_booking_notification(
#             user,
#             tariff,
#             {
#                 "visit_date": booking_data.visit_date,
#                 "visit_time": booking_data.visit_time,
#                 "duration": booking_data.duration,
#                 "amount": amount,
#                 "promocode_name": promocode.name if promocode else None,
#                 "discount": promocode.discount if promocode else 0,
#                 "tariff_purpose": tariff.purpose,
#             },
#         )
#
#         if bot and ADMIN_TELEGRAM_ID:
#             try:
#                 await bot.send_message(
#                     ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
#                 )
#             except Exception as e:
#                 logger.error(f"Ошибка отправки уведомления админу: {e}")
#
#         return {"message": "Бронирование создано", "booking_id": booking.id}
#
#     except Exception as e:
#         logger.error(f"Ошибка создания бронирования: {e}")
#         db.rollback()
#         raise HTTPException(status_code=500, detail="Ошибка создания бронирования")
@app.post("/bookings", response_model=BookingBase)
async def create_booking_endpoint(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        tariff = db.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        if not tariff:
            raise HTTPException(status_code=404, detail="Тариф не найден")

        # Рассчитываем итоговую сумму
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

        # Создаем запись в Rubitime (если нужно)
        rubitime_id = None
        if tariff.service_id:
            rubitime_params = {
                "service": tariff.service_id,
                "date": booking_data.visit_date.strftime("%Y-%m-%d"),
                "time": (
                    booking_data.visit_time.strftime("%H:%M")
                    if booking_data.visit_time
                    else "09:00"
                ),
                "duration": booking_data.duration or 60,
                "client_name": user.full_name or "Клиент",
                "client_phone": user.phone or "",
            }
            rubitime_id = await rubitime("create_record", rubitime_params)

        # Создаем бронирование
        booking = Booking(
            user_id=booking_data.user_id,
            tariff_id=booking_data.tariff_id,
            visit_date=booking_data.visit_date,
            visit_time=booking_data.visit_time,
            duration=booking_data.duration,
            promocode_id=booking_data.promocode_id,
            amount=amount,
            rubitime_id=rubitime_id,
            paid=False,
            confirmed=False,
        )

        db.add(booking)
        db.flush()  # Получаем ID

        # Создаем уведомление
        booking_data_dict = {
            "visit_date": booking_data.visit_date,
            "visit_time": booking_data.visit_time,
            "duration": booking_data.duration,
            "tariff_purpose": tariff.purpose,
            "amount": amount,
        }

        if promocode:
            booking_data_dict["promocode_name"] = promocode.name
            booking_data_dict["discount"] = promocode.discount

        admin_message = format_booking_notification(user, tariff, booking_data_dict)

        notification = Notification(
            user_id=booking_data.user_id,
            message=admin_message,
            target_url=f"/bookings/{booking.id}",
            booking_id=booking.id,
            is_read=False,
        )
        db.add(notification)

        # Отправляем уведомление админу в Telegram
        try:
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в Telegram: {e}")

        db.commit()
        return booking

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания бронирования: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать бронирование")


@app.put("/bookings/{booking_id}", response_model=dict)
async def update_booking(
    booking_id: int, booking_data: BookingBase, db: Session = Depends(get_db)
):
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")

    for field, value in booking_data.dict(exclude_unset=True).items():
        if hasattr(booking, field):
            setattr(booking, field, value)

    db.commit()
    return {"message": "Бронирование обновлено"}


@app.delete("/bookings/{booking_id}", response_model=dict)
async def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Бронирование не найдено")

    user = db.query(User).get(booking.user_id)
    tariff = db.query(Tariff).get(booking.tariff_id)

    db.delete(booking)
    db.commit()
    return {"message": "Бронирование удалено"}


@app.get("/tariffs", response_model=List[TariffBase])
async def get_tariffs(db: Session = Depends(get_db)):
    tariffs = db.query(Tariff).all()
    return tariffs


@app.get("/tariffs/{tariff_id}", response_model=TariffBase)
async def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")
    return tariff


@app.post("/tariffs", response_model=dict)
async def create_tariff(tariff_data: TariffBase, db: Session = Depends(get_db)):
    tariff = Tariff(**tariff_data.dict(exclude={"id"}))
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return {"message": "Тариф создан", "tariff_id": tariff.id}


@app.put("/tariffs/{tariff_id}", response_model=dict)
async def update_tariff(
    tariff_id: int, tariff_data: TariffBase, db: Session = Depends(get_db)
):
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    for field, value in tariff_data.dict(exclude_unset=True, exclude={"id"}).items():
        if hasattr(tariff, field):
            setattr(tariff, field, value)

    db.commit()
    return {"message": "Тариф обновлен"}


@app.delete("/tariffs/{tariff_id}", response_model=dict)
async def delete_tariff(tariff_id: int, db: Session = Depends(get_db)):
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    db.delete(tariff)
    db.commit()
    return {"message": "Тариф удален"}


@app.get("/promocodes", response_model=List[PromocodeBase])
async def get_promocodes(db: Session = Depends(get_db)):
    promocodes = db.query(Promocode).all()
    return promocodes


@app.get("/promocodes/{promocode_id}", response_model=PromocodeBase)
async def get_promocode(promocode_id: int, db: Session = Depends(get_db)):
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    return promocode


@app.post("/promocodes", response_model=dict)
async def create_promocode(
    promocode_data: PromocodeBase, db: Session = Depends(get_db)
):
    promocode = Promocode(**promocode_data.dict(exclude={"id"}))
    db.add(promocode)
    db.commit()
    db.refresh(promocode)
    return {"message": "Промокод создан", "promocode_id": promocode.id}


@app.put("/promocodes/{promocode_id}", response_model=dict)
async def update_promocode(
    promocode_id: int, promocode_data: PromocodeBase, db: Session = Depends(get_db)
):
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    for field, value in promocode_data.dict(exclude_unset=True, exclude={"id"}).items():
        if hasattr(promocode, field):
            setattr(promocode, field, value)

    db.commit()
    return {"message": "Промокод обновлен"}


@app.delete("/promocodes/{promocode_id}", response_model=dict)
async def delete_promocode(promocode_id: int, db: Session = Depends(get_db)):
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    db.delete(promocode)
    db.commit()
    return {"message": "Промокод удален"}


# @app.get("/tickets", response_model=List[TicketBase])
# async def get_tickets(
#     page: int = 1,
#     per_page: int = 20,
#     status: Optional[str] = None,
#     db: Session = Depends(get_db),
# ):
#     query = db.query(Ticket).order_by(Ticket.created_at.desc())
#
#     if status:
#         query = query.filter(Ticket.status == status)
#
#     tickets = query.offset((page - 1) * per_page).limit(per_page).all()
#     return tickets
@app.get("/tickets", response_model=List[TicketBase])
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        query = db.query(Ticket).order_by(Ticket.created_at.desc())

        if status:
            query = query.filter(Ticket.status == status)

        tickets = query.offset((page - 1) * per_page).limit(per_page).all()
        return tickets
    except Exception as e:
        logger.error(f"Ошибка получения тикетов: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# @app.get("/tickets/{ticket_id}", response_model=TicketBase)
# async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
#     ticket = db.query(Ticket).get(ticket_id)
#     if not ticket:
#         raise HTTPException(status_code=404, detail="Тикет не найден")
#     return ticket
@app.get("/tickets/{ticket_id}", response_model=TicketBase)
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    return ticket


# @app.post("/tickets", response_model=dict)
# async def create_ticket(ticket_data: TicketBase, db: Session = Depends(get_db)):
#     try:
#         from models.models import format_ticket_notification
#
#         user = db.query(User).get(ticket_data.user_id)
#         if not user:
#             raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#         ticket = Ticket(
#             user_id=ticket_data.user_id,
#             description=ticket_data.description,
#             photo_id=ticket_data.photo_id,
#             status=ticket_data.status,
#             comment=ticket_data.comment,
#             created_at=datetime.now(MOSCOW_TZ),
#             updated_at=datetime.now(MOSCOW_TZ),
#         )
#
#         db.add(ticket)
#         db.commit()
#         db.refresh(ticket)
#
#         # Отправка уведомления админу
#         admin_message = format_ticket_notification(
#             user,
#             {
#                 "description": ticket_data.description,
#                 "status": ticket_data.status,
#                 "photo_id": ticket_data.photo_id,
#             },
#         )
#
#         if bot and ADMIN_TELEGRAM_ID:
#             try:
#                 await bot.send_message(
#                     ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
#                 )
#             except Exception as e:
#                 logger.error(f"Ошибка отправки уведомления админу: {e}")
#
#         return {"message": "Тикет создан", "ticket_id": ticket.id}
#
#     except Exception as e:
#         logger.error(f"Ошибка создания тикета: {e}")
#         db.rollback()
#         raise HTTPException(status_code=500, detail="Ошибка создания тикета")
@app.post("/tickets", response_model=TicketBase)
async def create_ticket_endpoint(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Преобразуем статус в enum
        status_enum = TicketStatus.OPEN
        if ticket_data.status:
            try:
                status_enum = TicketStatus(ticket_data.status)
            except ValueError:
                status_enum = TicketStatus.OPEN

        ticket = Ticket(
            user_id=ticket_data.user_id,
            description=ticket_data.description,
            photo_id=ticket_data.photo_id,
            status=status_enum,
            comment=ticket_data.comment,
        )

        db.add(ticket)
        db.flush()  # Получаем ID

        # Создаем уведомление
        ticket_data_dict = {
            "description": ticket_data.description,
            "status": status_enum.value,
            "photo_id": ticket_data.photo_id,
        }

        admin_message = format_ticket_notification(user, ticket_data_dict)

        notification = Notification(
            user_id=ticket_data.user_id,
            message=admin_message,
            target_url=f"/tickets/{ticket.id}",
            ticket_id=ticket.id,
            is_read=False,
        )
        db.add(notification)

        # Отправляем уведомление админу в Telegram
        try:
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления в Telegram: {e}")

        db.commit()
        return ticket

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания тикета: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать тикет")


@app.put("/tickets/{ticket_id}", response_model=dict)
async def update_ticket(
    ticket_id: int, ticket_data: TicketBase, db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")

    for field, value in ticket_data.dict(exclude_unset=True, exclude={"id"}).items():
        if hasattr(ticket, field):
            setattr(ticket, field, value)

    ticket.updated_at = datetime.now(MOSCOW_TZ)
    db.commit()
    return {"message": "Тикет обновлен"}


@app.delete("/tickets/{ticket_id}", response_model=dict)
async def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Тикет не найден")

    db.delete(ticket)
    db.commit()
    return {"message": "Тикет удален"}


# @app.get("/notifications", response_model=List[NotificationBase])
# async def get_notifications(
#     page: int = 1, per_page: int = 20, db: Session = Depends(get_db)
# ):
#     notifications = (
#         db.query(Notification)
#         .order_by(desc(Notification.created_at))
#         .offset((page - 1) * per_page)
#         .limit(per_page)
#         .all()
#     )
#     return notifications
@app.get("/notifications", response_model=List[NotificationBase])
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        notifications = (
            db.query(Notification)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return notifications
    except Exception as e:
        logger.error(f"Ошибка получения уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# @app.get("/notifications/check_new")
# async def check_new_notifications(
#     since_id: int = Query(0), db: Session = Depends(get_db)
# ):
#     try:
#         query = db.query(Notification).order_by(desc(Notification.created_at))
#
#         if since_id > 0:
#             query = query.filter(Notification.id > since_id)
#
#         notifications = query.limit(10).all()
#
#         return {
#             "recent_notifications": [
#                 {
#                     "id": n.id,
#                     "user_id": n.user_id,
#                     "message": n.message,
#                     "booking_id": n.booking_id,
#                     "ticket_id": n.ticket_id,
#                     "target_url": n.target_url,
#                     "is_read": n.is_read,
#                     "created_at": n.created_at.isoformat(),
#                 }
#                 for n in notifications
#             ]
#         }
#     except Exception as e:
#         logger.error(f"Ошибка получения новых уведомлений: {e}")
#         return {"recent_notifications": []}
@app.get("/notifications/check_new")
async def check_new_notifications(
    since_id: int = Query(0),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        query = db.query(Notification).order_by(Notification.created_at.desc())

        if since_id > 0:
            query = query.filter(Notification.id > since_id)

        notifications = query.limit(5).all()

        return {
            "recent_notifications": [
                {
                    "id": n.id,
                    "user_id": n.user_id,
                    "message": n.message,
                    "target_url": n.target_url,
                    "is_read": n.is_read,
                    "created_at": n.created_at,
                    "booking_id": n.booking_id,
                    "ticket_id": n.ticket_id,
                }
                for n in notifications
            ]
        }
    except Exception as e:
        logger.error(f"Ошибка проверки новых уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# @app.post("/notifications/mark_read/{notification_id}", response_model=dict)
# async def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
#     notification = db.query(Notification).get(notification_id)
#     if not notification:
#         raise HTTPException(status_code=404, detail="Уведомление не найдено")
#
#     notification.is_read = True
#     db.commit()
#     return {"message": "Уведомление помечено как прочитанное"}
@app.post("/notifications/mark_read/{notification_id}")
async def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    try:
        notification = (
            db.query(Notification).filter(Notification.id == notification_id).first()
        )
        if not notification:
            raise HTTPException(status_code=404, detail="Уведомление не найдено")

        notification.is_read = True
        db.commit()

        return {"message": "Уведомление помечено как прочитанное"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка пометки уведомления: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


# @app.post("/notifications/mark_all_read", response_model=dict)
# async def mark_all_notifications_read(db: Session = Depends(get_db)):
#     try:
#         db.query(Notification).filter(Notification.is_read == False).update(
#             {"is_read": True}
#         )
#         db.commit()
#         return {"message": "Все уведомления помечены как прочитанные"}
#     except Exception as e:
#         logger.error(f"Ошибка пометки всех уведомлений: {e}")
#         db.rollback()
#         raise HTTPException(status_code=500, detail="Ошибка пометки уведомлений")
@app.post("/notifications/mark_all_read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db), current_admin: Admin = Depends(get_current_admin)
):
    try:
        db.query(Notification).filter(Notification.is_read == False).update(
            {"is_read": True}
        )
        db.commit()

        return {"message": "Все уведомления помечены как прочитанные"}
    except Exception as e:
        logger.error(f"Ошибка пометки всех уведомлений: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@app.get("/newsletters", response_model=List[NewsletterBase])
async def get_newsletters(
    page: int = 1, per_page: int = 20, db: Session = Depends(get_db)
):
    newsletters = (
        db.query(Newsletter)
        .order_by(desc(Newsletter.created_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return newsletters


@app.post("/newsletters", response_model=dict)
async def create_newsletter(
    newsletter_data: NewsletterBase, db: Session = Depends(get_db)
):
    newsletter = Newsletter(
        message=newsletter_data.message,
        created_at=datetime.now(MOSCOW_TZ),
        recipient_count=newsletter_data.recipient_count,
    )

    db.add(newsletter)
    db.commit()
    db.refresh(newsletter)
    return {"message": "Рассылка создана", "newsletter_id": newsletter.id}


@app.on_event("startup")
async def startup_event():
    init_db()
    admin_login = os.getenv("ADMIN_LOGIN", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    create_admin(admin_login, admin_password)
    logger.info("Приложение запущено")
