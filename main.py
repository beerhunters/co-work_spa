from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # Добавлен импорт для статических файлов
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, date, time
from werkzeug.security import check_password_hash
import os
import aiohttp
from aiogram import Bot
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from yookassa import Payment
from models.models import (
    Admin,
    User,
    Tariff,
    Promocode,
    Booking,
    Newsletter,
    Ticket,
    Notification,
    TicketStatus,
    Session,
    format_booking_notification,
    format_ticket_notification,
)
from utils.logger import get_logger
import pytz

logger = get_logger(__name__)

try:
    # Инициализация FastAPI
    app = FastAPI()

    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Монтирование папки со статическими файлами
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Настройка базы данных
    MOSCOW_TZ = pytz.timezone("Europe/Moscow")

    # Настройка Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
    if not BOT_TOKEN or not ADMIN_TELEGRAM_ID:
        logger.error(
            "BOT_TOKEN или ADMIN_TELEGRAM_ID не указаны в переменных окружения"
        )
        raise ValueError("Необходимые переменные окружения отсутствуют")

    bot = Bot(token=BOT_TOKEN)

    # Настройка Rubitime
    RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
    RUBITIME_BASE_URL = "https://rubitime.ru/api2/"

    # Pydantic модели
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

    class NotificationBase(BaseModel):
        id: int
        user_id: int
        booking_id: Optional[int]
        ticket_id: Optional[int]
        message: str
        is_read: bool
        created_at: datetime

    # Корневой маршрут
    @app.get("/")
    async def root():
        """Возвращает приветственное сообщение для корневого пути.

        Returns:
            Словарь с приветственным сообщением.

        Сложность: O(1).
        """
        logger.info("Запрос к корневому пути /")
        return {"message": "Добро пожаловать в API коворкинга Parta!"}

    # Зависимость для получения сессии базы данных
    def get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    # Проверка авторизации
    security = HTTPBasic()

    def verify_credentials(
        credentials: HTTPBasicCredentials = Depends(security),
        db: Session = Depends(get_db),
    ):
        admin = db.query(Admin).filter(Admin.login == credentials.username).first()
        if not admin or not check_password_hash(admin.password, credentials.password):
            logger.warning(f"Неудачная попытка входа: {credentials.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
                headers={"WWW-Authenticate": "Basic"},
            )
        return admin

    async def rubitime(method: str, extra_params: dict) -> Optional[str]:
        """Отправляет запрос к Rubitime API.

        Args:
            method: Метод API Rubitime.
            extra_params: Дополнительные параметры запроса.

        Returns:
            ID записи или None при ошибке.

        Сложность: O(1) для сетевого запроса.
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{RUBITIME_BASE_URL}create-record"
                params = {"api_key": RUBITIME_API_KEY, **extra_params}
                async with session.post(url, json=params) as response:
                    if response.status != 200:
                        logger.error(f"Ошибка Rubitime API: {response.status}")
                        return None
                    data = await response.json()
                    return data.get("data", {}).get("id")
        except Exception as e:
            logger.error(f"Ошибка при запросе к Rubitime: {str(e)}")
            return None

    async def check_payment_status(payment_id: str) -> Optional[str]:
        """Проверяет статус платежа через Yookassa.

        Args:
            payment_id: ID платежа.

        Returns:
            Статус платежа или None при ошибке.

        Сложность: O(1).
        """
        try:
            payment = await Payment.find_one(payment_id)
            return payment.status if payment else None
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса платежа {payment_id}: {str(e)}")
            return None

    # Маршруты авторизации
    @app.post("/login", response_model=dict)
    async def login(credentials: AdminBase, db: Session = Depends(get_db)):
        admin = db.query(Admin).filter(Admin.login == credentials.login).first()
        if not admin or not check_password_hash(admin.password, credentials.password):
            logger.warning(f"Неудачная попытка входа: {credentials.login}")
            raise HTTPException(status_code=401, detail="Неверный логин или пароль")
        logger.info(f"Успешный вход: {credentials.login}")
        return {"message": "Успешный вход"}

    @app.get("/logout")
    async def logout():
        logger.info("Выход из системы")
        return {"message": "Успешный выход"}

    # Маршруты пользователей
    @app.get("/users", response_model=List[UserBase])
    async def get_users(
        page: int = 1,
        per_page: int = 10,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(
            f"Запрос списка пользователей: страница {page}, по {per_page} на страницу"
        )
        users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
        return users

    @app.get("/user/{user_id}", response_model=UserBase)
    async def get_user(
        user_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос данных пользователя: ID {user_id}")
        user = db.query(User).get(user_id)
        if not user:
            logger.warning(f"Пользователь не найден: ID {user_id}")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        return user

    @app.post("/user/{user_id}/edit", response_model=UserBase)
    async def edit_user(
        user_id: int,
        user_data: UserBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Редактирование пользователя: ID {user_id}")
        user = db.query(User).get(user_id)
        if not user:
            logger.warning(f"Пользователь не найден: ID {user_id}")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        user.full_name = user_data.full_name
        user.phone = user_data.phone
        user.email = user_data.email
        user.username = user_data.username
        user.referrer_id = user_data.referrer_id
        db.commit()
        db.refresh(user)
        logger.info(f"Пользователь успешно отредактирован: ID {user_id}")
        return user

    @app.delete("/user/{user_id}/delete")
    async def delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Удаление пользователя: ID {user_id}")
        user = db.query(User).get(user_id)
        if not user:
            logger.warning(f"Пользователь не найден: ID {user_id}")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        db.delete(user)
        db.commit()
        logger.info(f"Пользователь успешно удален: ID {user_id}")
        return {"message": "Пользователь удален"}

    # Маршруты бронирований
    @app.get("/bookings", response_model=List[BookingBase])
    async def get_bookings(
        user_query: str = "",
        date_query: str = "",
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(
            f"Запрос списка бронирований: user_query={user_query}, date_query={date_query}"
        )
        query = db.query(Booking)
        if user_query:
            query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))
        if date_query:
            try:
                query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                query = query.filter(Booking.visit_date == query_date)
            except ValueError:
                logger.warning(f"Неверный формат даты: {date_query}")
                raise HTTPException(status_code=400, detail="Неверный формат даты")
        return query.all()

    @app.get("/booking/{booking_id}", response_model=BookingBase)
    async def get_booking(
        booking_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос данных брони: ID {booking_id}")
        booking = db.query(Booking).get(booking_id)
        if not booking:
            logger.warning(f"Бронь не найдена: ID {booking_id}")
            raise HTTPException(status_code=404, detail="Бронь не найдена")
        return booking

    @app.post("/booking/new", response_model=BookingBase)
    async def create_booking(
        booking_data: BookingBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(
            f"Создание новой брони: user_id={booking_data.user_id}, tariff_id={booking_data.tariff_id}"
        )
        user = db.query(User).get(booking_data.user_id)
        if not user:
            logger.warning(f"Пользователь не найден: ID {booking_data.user_id}")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        tariff = db.query(Tariff).get(booking_data.tariff_id)
        if not tariff:
            logger.warning(f"Тариф не найден: ID {booking_data.tariff_id}")
            raise HTTPException(status_code=404, detail="Тариф не найден")
        promocode = (
            db.query(Promocode).get(booking_data.promocode_id)
            if booking_data.promocode_id
            else None
        )
        amount = booking_data.amount
        if promocode and promocode.is_active:
            amount = amount * (1 - promocode.discount / 100)
            promocode.usage_quantity += 1
        # Создание записи в Rubitime
        rubitime_params = {
            "service_id": tariff.service_id,
            "date": booking_data.visit_date.strftime("%Y-%m-%d")
            + (
                f" {booking_data.visit_time.strftime('%H:%M:%S')}"
                if booking_data.visit_time
                else " 09:00:00"
            ),
            "phone": user.phone or "Не указано",
            "duration": booking_data.duration * 60 if booking_data.duration else None,
        }
        rubitime_id = await rubitime("create_record", rubitime_params)
        # Создание платежа в Yookassa
        try:
            payment = await Payment.create(
                {
                    "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "return_url": "https://example.com/return",
                    },
                    "description": f"Бронь: {tariff.name}, дата: {booking_data.visit_date}",
                }
            )
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {str(e)}")
            raise HTTPException(status_code=500, detail="Ошибка при создании платежа")
        booking = Booking(
            user_id=booking_data.user_id,
            tariff_id=booking_data.tariff_id,
            visit_date=booking_data.visit_date,
            visit_time=booking_data.visit_time,
            duration=booking_data.duration,
            promocode_id=booking_data.promocode_id,
            amount=amount,
            payment_id=payment.id,
            rubitime_id=rubitime_id,
            paid=booking_data.paid,
            confirmed=booking_data.confirmed,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        # Отправка уведомления администратору
        admin_message = format_booking_notification(
            user,
            tariff,
            {
                "tariff_name": tariff.name,
                "tariff_purpose": tariff.purpose,
                "visit_date": booking.visit_date,
                "visit_time": booking.visit_time,
                "duration": booking.duration,
                "amount": booking.amount,
                "promocode_name": promocode.name if promocode else None,
                "discount": promocode.discount if promocode else 0,
                "rubitime_id": booking.rubitime_id,
            },
        )
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору: {str(e)}")
        logger.info(f"Бронь успешно создана: ID {booking.id}")
        return booking

    @app.post("/booking/{booking_id}/edit", response_model=BookingBase)
    async def edit_booking(
        booking_id: int,
        booking_data: BookingBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Редактирование брони: ID {booking_id}")
        booking = db.query(Booking).get(booking_id)
        if not booking:
            logger.warning(f"Бронь не найдена: ID {booking_id}")
            raise HTTPException(status_code=404, detail="Бронь не найдена")
        booking.user_id = booking_data.user_id
        booking.tariff_id = booking_data.tariff_id
        booking.visit_date = booking_data.visit_date
        booking.visit_time = booking_data.visit_time
        booking.duration = booking_data.duration
        booking.promocode_id = booking_data.promocode_id
        booking.amount = booking_data.amount
        booking.paid = booking_data.paid
        booking.confirmed = booking_data.confirmed
        db.commit()
        db.refresh(booking)
        logger.info(f"Бронь успешно отредактирована: ID {booking_id}")
        return booking

    @app.post("/booking/{booking_id}/confirm")
    async def confirm_booking(
        booking_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Подтверждение брони: ID {booking_id}")
        booking = db.query(Booking).get(booking_id)
        if not booking:
            logger.warning(f"Бронь не найдена: ID {booking_id}")
            raise HTTPException(status_code=404, detail="Бронь не найдена")
        booking.confirmed = True
        db.commit()
        user = db.query(User).get(booking.user_id)
        tariff = db.query(Tariff).get(booking.tariff_id)
        promocode = (
            db.query(Promocode).get(booking.promocode_id)
            if booking.promocode_id
            else None
        )
        admin_message = format_booking_notification(
            user,
            tariff,
            {
                "tariff_name": tariff.name,
                "tariff_purpose": tariff.purpose,
                "visit_date": booking.visit_date,
                "visit_time": booking.visit_time,
                "duration": booking.duration,
                "amount": booking.amount,
                "promocode_name": promocode.name if promocode else None,
                "discount": promocode.discount if promocode else 0,
                "rubitime_id": booking.rubitime_id,
            },
        )
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору: {str(e)}")
        logger.info(f"Бронь подтверждена: ID {booking_id}")
        return {"message": "Бронь подтверждена"}

    @app.delete("/booking/{booking_id}/delete")
    async def delete_booking(
        booking_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Удаление брони: ID {booking_id}")
        booking = db.query(Booking).get(booking_id)
        if not booking:
            logger.warning(f"Бронь не найдена: ID {booking_id}")
            raise HTTPException(status_code=404, detail="Бронь не найдена")
        db.delete(booking)
        db.commit()
        logger.info(f"Бронь удалена: ID {booking_id}")
        return {"message": "Бронь удалена"}

    # Маршруты тарифов
    @app.get("/tariffs", response_model=List[TariffBase])
    async def get_tariffs(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Запрос списка тарифов")
        return db.query(Tariff).filter_by(is_active=True).all()

    @app.get("/tariff/{tariff_id}", response_model=TariffBase)
    async def get_tariff(
        tariff_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос данных тарифа: ID {tariff_id}")
        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            logger.warning(f"Тариф не найден: ID {tariff_id}")
            raise HTTPException(status_code=404, detail="Тариф не найден")
        return tariff

    @app.post("/tariff/new", response_model=TariffBase)
    async def create_tariff(
        tariff_data: TariffBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Создание нового тарифа: {tariff_data.name}")
        tariff = Tariff(**tariff_data.dict())
        db.add(tariff)
        db.commit()
        db.refresh(tariff)
        logger.info(f"Тариф создан: ID {tariff.id}")
        return tariff

    @app.post("/tariff/{tariff_id}/edit", response_model=TariffBase)
    async def edit_tariff(
        tariff_id: int,
        tariff_data: TariffBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Редактирование тарифа: ID {tariff_id}")
        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            logger.warning(f"Тариф не найден: ID {tariff_id}")
            raise HTTPException(status_code=404, detail="Тариф не найден")
        tariff.name = tariff_data.name
        tariff.description = tariff_data.description
        tariff.price = tariff_data.price
        tariff.purpose = tariff_data.purpose
        tariff.service_id = tariff_data.service_id
        tariff.is_active = tariff_data.is_active
        db.commit()
        db.refresh(tariff)
        logger.info(f"Тариф отредактирован: ID {tariff_id}")
        return tariff

    @app.delete("/tariff/{tariff_id}/delete")
    async def delete_tariff(
        tariff_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Удаление тарифа: ID {tariff_id}")
        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            logger.warning(f"Тариф не найден: ID {tariff_id}")
            raise HTTPException(status_code=404, detail="Тариф не найден")
        db.delete(tariff)
        db.commit()
        logger.info(f"Тариф удален: ID {tariff_id}")
        return {"message": "Тариф удален"}

    # Маршруты промокодов
    @app.get("/promocodes", response_model=List[PromocodeBase])
    async def get_promocodes(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Запрос списка промокодов")
        return db.query(Promocode).all()

    @app.get("/promocode/{promocode_id}", response_model=PromocodeBase)
    async def get_promocode(
        promocode_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос данных промокода: ID {promocode_id}")
        promocode = db.query(Promocode).get(promocode_id)
        if not promocode:
            logger.warning(f"Промокод не найден: ID {promocode_id}")
            raise HTTPException(status_code=404, detail="Промокод не найден")
        return promocode

    @app.post("/promocode/new", response_model=PromocodeBase)
    async def create_promocode(
        promocode_data: PromocodeBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Создание нового промокода: {promocode_data.name}")
        promocode = Promocode(**promocode_data.dict())
        db.add(promocode)
        db.commit()
        db.refresh(promocode)
        logger.info(f"Промокод создан: ID {promocode.id}")
        return promocode

    @app.post("/promocode/{promocode_id}/edit", response_model=PromocodeBase)
    async def edit_promocode(
        promocode_id: int,
        promocode_data: PromocodeBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Редактирование промокода: ID {promocode_id}")
        promocode = db.query(Promocode).get(promocode_id)
        if not promocode:
            logger.warning(f"Промокод не найден: ID {promocode_id}")
            raise HTTPException(status_code=404, detail="Промокод не найден")
        promocode.name = promocode_data.name
        promocode.discount = promocode_data.discount
        promocode.usage_quantity = promocode_data.usage_quantity
        promocode.expiration_date = promocode_data.expiration_date
        promocode.is_active = promocode_data.is_active
        db.commit()
        db.refresh(promocode)
        logger.info(f"Промокод отредактирован: ID {promocode_id}")
        return promocode

    @app.delete("/promocode/{promocode_id}/delete")
    async def delete_promocode(
        promocode_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Удаление промокода: ID {promocode_id}")
        promocode = db.query(Promocode).get(promocode_id)
        if not promocode:
            logger.warning(f"Промокод не найден: ID {promocode_id}")
            raise HTTPException(status_code=404, detail="Промокод не найден")
        db.delete(promocode)
        db.commit()
        logger.info(f"Промокод удален: ID {promocode_id}")
        return {"message": "Промокод удален"}

    # Маршруты тикетов
    @app.get("/tickets", response_model=List[TicketBase])
    async def get_tickets(
        page: int = 1,
        per_page: int = 10,
        status: str = "",
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(
            f"Запрос списка тикетов: страница {page}, по {per_page} на страницу, статус={status}"
        )
        query = db.query(Ticket).order_by(Ticket.created_at.desc())
        if status:
            query = query.filter(Ticket.status == status)
        tickets = query.offset((page - 1) * per_page).limit(per_page).all()
        return tickets

    @app.get("/ticket/{ticket_id}", response_model=TicketBase)
    async def get_ticket(
        ticket_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос данных тикета: ID {ticket_id}")
        ticket = db.query(Ticket).get(ticket_id)
        if not ticket:
            logger.warning(f"Тикет не найден: ID {ticket_id}")
            raise HTTPException(status_code=404, detail="Тикет не найден")
        return ticket

    @app.post("/ticket/new", response_model=TicketBase)
    async def create_ticket(
        ticket_data: TicketBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Создание нового тикета: user_id={ticket_data.user_id}")
        user = db.query(User).get(ticket_data.user_id)
        if not user:
            logger.warning(f"Пользователь не найден: ID {ticket_data.user_id}")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        ticket = Ticket(
            user_id=ticket_data.user_id,
            description=ticket_data.description,
            photo_id=ticket_data.photo_id,
            status=ticket_data.status,
            comment=ticket_data.comment,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        admin_message = format_ticket_notification(
            user,
            {
                "description": ticket.description,
                "status": ticket.status,
                "photo_id": ticket.photo_id,
                "ticket_id": ticket.id,
            },
        )
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML")
            if ticket.photo_id:
                await bot.send_photo(ADMIN_TELEGRAM_ID, ticket.photo_id)
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления администратору: {str(e)}")
        logger.info(f"Тикет создан: ID {ticket.id}")
        return ticket

    @app.post("/ticket/{ticket_id}/edit", response_model=TicketBase)
    async def edit_ticket(
        ticket_id: int,
        ticket_data: TicketBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Редактирование тикета: ID {ticket_id}")
        ticket = db.query(Ticket).get(ticket_id)
        if not ticket:
            logger.warning(f"Тикет не найден: ID {ticket_id}")
            raise HTTPException(status_code=404, detail="Тикет не найден")
        ticket.description = ticket_data.description
        ticket.status = ticket_data.status
        ticket.comment = ticket_data.comment
        db.commit()
        db.refresh(ticket)
        logger.info(f"Тикет отредактирован: ID {ticket_id}")
        return ticket

    @app.delete("/ticket/{ticket_id}/delete")
    async def delete_ticket(
        ticket_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Удаление тикета: ID {ticket_id}")
        ticket = db.query(Ticket).get(ticket_id)
        if not ticket:
            logger.warning(f"Тикет не найден: ID {ticket_id}")
            raise HTTPException(status_code=404, detail="Тикет не найден")
        db.delete(ticket)
        db.commit()
        logger.info(f"Тикет удален: ID {ticket_id}")
        return {"message": "Тикет удален"}

    # Маршруты уведомлений
    @app.get("/notifications", response_model=List[NotificationBase])
    async def get_notifications(
        page: int = 1,
        per_page: int = 15,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(
            f"Запрос списка уведомлений: страница {page}, по {per_page} на страницу"
        )
        notifications = (
            db.query(Notification)
            .order_by(Notification.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return notifications

    @app.get("/get_notifications", response_model=List[NotificationBase])
    async def get_new_notifications(
        since_id: Optional[int] = None,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Запрос новых уведомлений: since_id={since_id}")
        query = db.query(Notification).order_by(Notification.created_at.desc())
        if since_id:
            query = query.filter(Notification.id > since_id)
        notifications = query.limit(5).all()
        return notifications

    @app.post("/notifications/mark_read/{notification_id}")
    async def mark_notification_read(
        notification_id: int,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Отметка уведомления как прочитанного: ID {notification_id}")
        notification = db.query(Notification).get(notification_id)
        if not notification:
            logger.warning(f"Уведомление не найдено: ID {notification_id}")
            raise HTTPException(status_code=404, detail="Уведомление не найдено")
        notification.is_read = True
        db.commit()
        logger.info(f"Уведомление отмечено как прочитанное: ID {notification_id}")
        return {"message": "Уведомление отмечено как прочитанное"}

    @app.post("/notifications/mark_all_read")
    async def mark_all_notifications_read(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Отметка всех уведомлений как прочитанных")
        db.query(Notification).filter(Notification.is_read == False).update(
            {"is_read": True}
        )
        db.commit()
        logger.info("Все уведомления отмечены как прочитанные")
        return {"message": "Все уведомления отмечены как прочитанные"}

    @app.post("/notifications/clear")
    async def clear_notifications(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Очистка всех уведомлений")
        db.query(Notification).delete()
        db.commit()
        logger.info("Все уведомления удалены")
        return {"message": "Все уведомления удалены"}

    # Маршруты рассылок
    @app.get("/newsletters", response_model=List[NewsletterBase])
    async def get_newsletters(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Запрос списка рассылок")
        return db.query(Newsletter).order_by(Newsletter.created_at.desc()).all()

    @app.post("/newsletter", response_model=NewsletterBase)
    async def create_newsletter(
        newsletter_data: NewsletterBase,
        db: Session = Depends(get_db),
        admin: Admin = Depends(verify_credentials),
    ):
        logger.info(f"Создание новой рассылки: {newsletter_data.message[:50]}...")
        newsletter = Newsletter(
            message=newsletter_data.message,
            recipient_count=newsletter_data.recipient_count,
        )
        db.add(newsletter)
        db.commit()
        db.refresh(newsletter)
        try:
            await bot.send_message(
                ADMIN_TELEGRAM_ID,
                f"📬 Новая рассылка: {newsletter.message}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о рассылке: {str(e)}")
        logger.info(f"Рассылка создана: ID {newsletter.id}")
        return newsletter

    @app.post("/newsletters/clear")
    async def clear_newsletters(
        db: Session = Depends(get_db), admin: Admin = Depends(verify_credentials)
    ):
        logger.info("Очистка всех рассылок")
        db.query(Newsletter).delete()
        db.commit()
        logger.info("Все рассылки удалены")
        return {"message": "Все рассылки удалены"}

    # Инициализация админа
    @app.on_event("startup")
    async def startup_event():
        logger.info("Запуск приложения")
        try:
            from models.models import create_admin

            admin_login = os.getenv("ADMIN_LOGIN", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
            create_admin(admin_login, admin_password)
            logger.info("Админ успешно создан или уже существует")
        except Exception as e:
            logger.error(f"Ошибка при инициализации админа: {str(e)}")
            raise

except Exception as e:
    logger.error(f"Критическая ошибка при запуске приложения: {str(e)}")
    raise
