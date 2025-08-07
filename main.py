import os
import pytz
from datetime import datetime, timedelta, date, time
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import (
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
    HTTPAuthorizationCredentials,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash
from utils.logger import get_logger
from utils.bot_instance import get_bot
from models.models import (
    Session as DBSession,
    Admin,
    User,
    Tariff,
    Promocode,
    Booking,
    Newsletter,
    Ticket,
    Notification,
    TicketStatus,
    format_booking_notification,
    format_ticket_notification,
    init_db,
    create_admin,
)
from aiogram import Bot
from yookassa import Payment
import aiohttp
import jwt
from jwt.exceptions import InvalidTokenError

logger = get_logger(__name__)
app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

# JWT Configuration
SECRET_KEY_JWT = os.getenv("SECRET_KEY_JWT", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

try:
    bot = Bot(token=BOT_TOKEN)
except:
    bot = None

RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = "https://rubitime.ru/api2/"

# Security
security = HTTPBearer()


# Pydantic models
class AdminBase(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


class NotificationBase(BaseModel):
    id: int
    user_id: int
    message: str
    created_at: datetime
    booking_id: Optional[int]
    ticket_id: Optional[int]
    target_url: Optional[str]
    is_read: bool


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


# JWT functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


# Routes
@app.get("/")
async def root():
    return {"message": "API is running"}


@app.post("/login", response_model=TokenResponse)
async def login(credentials: AdminBase, db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": admin.login})
    return {"access_token": access_token}


@app.get("/verify_token")
async def verify_token_endpoint(username: str = Depends(verify_token)):
    return {"valid": True, "username": username}


@app.get("/logout")
async def logout():
    # Token invalidation should be handled on the client side
    return {"message": "Successfully logged out"}


# Protected routes
@app.get("/users", response_model=List[UserBase])
async def get_users(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
    return users


@app.get("/users/{user_id}", response_model=UserBase)
async def get_user(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/bookings", response_model=List[BookingBase])
async def get_bookings(
    page: int = 1,
    per_page: int = 20,
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    query = db.query(Booking).order_by(Booking.created_at.desc())

    if user_query:
        query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))

    if date_query:
        query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
        query = query.filter(Booking.visit_date == query_date)

    bookings = query.offset((page - 1) * per_page).limit(per_page).all()
    return bookings


@app.get("/bookings/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@app.post("/bookings", response_model=dict)
async def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tariff = db.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    amount = booking_data.amount
    promocode = None
    if booking_data.promocode_id:
        promocode = (
            db.query(Promocode)
            .filter(Promocode.id == booking_data.promocode_id)
            .first()
        )
        if promocode:
            amount = amount * (1 - promocode.discount / 100)

    rubitime_id = None
    if RUBITIME_API_KEY:
        rubitime_params = {
            "user_id": str(user.telegram_id),
            "service_id": tariff.service_id,
            "date": booking_data.visit_date.strftime("%Y-%m-%d"),
            "time": (
                booking_data.visit_time.strftime("%H:%M")
                if booking_data.visit_time
                else "09:00"
            ),
            "duration": booking_data.duration * 60 if booking_data.duration else 540,
        }
        rubitime_id = await rubitime("create_record", rubitime_params)

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
        rubitime_id=rubitime_id,
        confirmed=booking_data.confirmed,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    # Create notification for admin
    booking_data_dict = {
        "tariff_purpose": tariff.purpose,
        "tariff_name": tariff.name,
        "visit_date": booking_data.visit_date,
        "visit_time": booking_data.visit_time,
        "duration": booking_data.duration,
        "promocode_name": promocode.name if promocode else None,
        "discount": promocode.discount if promocode else 0,
        "amount": amount,
    }

    admin_message = format_booking_notification(user, tariff, booking_data_dict)

    # Create notification in database
    notification = Notification(
        user_id=user.id,
        message=admin_message,
        booking_id=booking.id,
        target_url=f"/bookings/{booking.id}",
    )
    db.add(notification)
    db.commit()

    # Send to Telegram if bot is available
    if bot and ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    return {"id": booking.id, "message": "Booking created successfully"}


@app.put("/bookings/{booking_id}", response_model=dict)
async def update_booking(
    booking_id: int,
    confirmed: bool,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.confirmed = confirmed
    db.commit()

    if bot and confirmed:
        user = db.query(User).get(booking.user_id)
        tariff = db.query(Tariff).get(booking.tariff_id)
        if user and tariff:
            try:
                message = f"✅ Ваша бронь подтверждена!\n\n📋 Тариф: {tariff.name}\n📅 Дата: {booking.visit_date}"
                await bot.send_message(
                    chat_id=user.telegram_id, text=message, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send confirmation: {e}")

    return {"message": "Booking updated successfully"}


@app.delete("/bookings/{booking_id}", response_model=dict)
async def delete_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted successfully"}


@app.get("/tariffs", response_model=List[TariffBase])
async def get_tariffs(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    tariffs = db.query(Tariff).all()
    return tariffs


@app.get("/tariffs/{tariff_id}", response_model=TariffBase)
async def get_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    return tariff


@app.post("/tariffs", response_model=dict)
async def create_tariff(
    tariff_data: TariffBase,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    tariff = Tariff(**tariff_data.dict(exclude={"id"}))
    db.add(tariff)
    db.commit()
    return {"id": tariff.id, "message": "Tariff created successfully"}


@app.delete("/tariffs/{tariff_id}", response_model=dict)
async def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    db.delete(tariff)
    db.commit()
    return {"message": "Tariff deleted successfully"}


@app.get("/promocodes", response_model=List[PromocodeBase])
async def get_promocodes(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    promocodes = db.query(Promocode).all()
    return promocodes


@app.get("/promocodes/{promocode_id}", response_model=PromocodeBase)
async def get_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return promocode


@app.post("/promocodes", response_model=dict)
async def create_promocode(
    promocode_data: PromocodeBase,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    promocode = Promocode(**promocode_data.dict(exclude={"id"}))
    db.add(promocode)
    db.commit()
    return {"id": promocode.id, "message": "Promocode created successfully"}


@app.delete("/promocodes/{promocode_id}", response_model=dict)
async def delete_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    db.delete(promocode)
    db.commit()
    return {"message": "Promocode deleted successfully"}


@app.get("/tickets", response_model=List[TicketBase])
async def get_tickets(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    query = db.query(Ticket).order_by(Ticket.created_at.desc())

    if status:
        query = query.filter(Ticket.status == status)

    tickets = query.offset((page - 1) * per_page).limit(per_page).all()
    return tickets


@app.get("/tickets/{ticket_id}", response_model=TicketBase)
async def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/tickets", response_model=dict)
async def create_ticket(
    ticket_data: TicketCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        status_enum = TicketStatus.OPEN
        if ticket_data.status:
            status_enum = TicketStatus(ticket_data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket status")

    ticket = Ticket(
        user_id=user.id,
        description=ticket_data.description,
        photo_id=ticket_data.photo_id,
        status=status_enum,
        comment=ticket_data.comment,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Create notification
    ticket_data_dict = {
        "description": ticket_data.description,
        "photo_id": ticket_data.photo_id,
        "status": status_enum.name,
    }

    admin_message = format_ticket_notification(user, ticket_data_dict)

    notification = Notification(
        user_id=user.id,
        message=admin_message,
        ticket_id=ticket.id,
        target_url=f"/tickets/{ticket.id}",
    )
    db.add(notification)
    db.commit()

    if bot and ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    return {"id": ticket.id, "message": "Ticket created successfully"}


@app.put("/tickets/{ticket_id}", response_model=dict)
async def update_ticket(
    ticket_id: int,
    status: str,
    comment: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    try:
        ticket.status = TicketStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket status")

    if comment:
        ticket.comment = comment

    ticket.updated_at = datetime.now(MOSCOW_TZ)
    db.commit()

    return {"message": "Ticket updated successfully"}


@app.delete("/tickets/{ticket_id}", response_model=dict)
async def delete_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.delete(ticket)
    db.commit()
    return {"message": "Ticket deleted successfully"}


@app.get("/notifications", response_model=List[NotificationBase])
async def get_notifications(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    notifications = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return notifications


@app.get("/notifications/check_new")
async def check_new_notifications(
    since_id: int = 0, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    query = db.query(Notification).order_by(Notification.created_at.desc())

    if since_id > 0:
        query = query.filter(Notification.id > since_id)

    notifications = query.limit(5).all()
    return {"recent_notifications": notifications}


@app.post("/notifications/mark_read/{notification_id}", response_model=dict)
async def mark_notification_read(
    notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    notification = (
        db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}


@app.post("/notifications/mark_all_read", response_model=dict)
async def mark_all_notifications_read(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    db.query(Notification).filter(Notification.is_read == False).update(
        {"is_read": True}
    )
    db.commit()
    return {"message": "All notifications marked as read"}


@app.get("/newsletters", response_model=List[NewsletterBase])
async def get_newsletters(
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    newsletters = (
        db.query(Newsletter)
        .order_by(Newsletter.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return newsletters


@app.post("/newsletters", response_model=dict)
async def create_newsletter(
    message: str, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    users = db.query(User).all()

    newsletter = Newsletter(message=message, recipient_count=len(users))
    db.add(newsletter)
    db.commit()

    if bot:
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.telegram_id, text=message, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send newsletter to {user.telegram_id}: {e}")

    return {"id": newsletter.id, "message": "Newsletter sent successfully"}


# Dashboard stats endpoint
@app.get("/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    total_users = db.query(User).count()
    total_bookings = db.query(Booking).count()
    # Count only open tickets (not closed)
    open_tickets = db.query(Ticket).filter(Ticket.status != TicketStatus.CLOSED).count()

    return {
        "total_users": total_users,
        "total_bookings": total_bookings,
        "open_tickets": open_tickets,
    }


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    if not RUBITIME_API_KEY:
        return None

    url = f"{RUBITIME_BASE_URL}create-record"
    params = {"api_key": RUBITIME_API_KEY, **extra_params}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", {}).get("id")

    return None


async def check_payment_status(payment_id: str) -> Optional[str]:
    try:
        payment = await Payment.find_one(payment_id)
        return payment.status if payment else None
    except Exception as e:
        logger.error(f"Failed to check payment status: {e}")
        return None


@app.on_event("startup")
async def startup_event():
    init_db()
    admin_login = os.getenv("ADMIN_LOGIN", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    create_admin(admin_login, admin_password)
    logger.info("Application started successfully")
