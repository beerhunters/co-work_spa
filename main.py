# import os
# import pytz
# from datetime import datetime, timedelta, date, time
# from typing import List, Optional
# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import (
#     HTTPBearer,
#     HTTPAuthorizationCredentials,
# )
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from fastapi import File, UploadFile
# from pydantic import BaseModel
# from sqlalchemy.orm import Session
# from werkzeug.security import check_password_hash
# from utils.logger import get_logger
# from models.models import (
#     Session as DBSession,
#     Admin,
#     User,
#     Tariff,
#     Promocode,
#     Booking,
#     Newsletter,
#     Ticket,
#     Notification,
#     TicketStatus,
#     format_booking_notification,
#     format_ticket_notification,
#     init_db,
#     create_admin,
# )
# from aiogram import Bot
# from yookassa import Payment
# import aiohttp
# import jwt
# from jwt.exceptions import InvalidTokenError
# from pathlib import Path
#
# logger = get_logger(__name__)
# app = FastAPI()
#
# AVATARS_DIR = Path(__file__).parent / "avatars"
# app.mount("/avatars", StaticFiles(directory=AVATARS_DIR), name="avatars")
#
# # Добавляем CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost", "http://localhost:80", "http://localhost:5173"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# MOSCOW_TZ = pytz.timezone("Europe/Moscow")
# BOT_TOKEN = os.getenv("BOT_TOKEN")
# ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
#
# # JWT Configuration
# SECRET_KEY_JWT = os.getenv("SECRET_KEY_JWT", "your-secret-key-change-in-production")
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_HOURS = 24
#
# try:
#     bot = Bot(token=BOT_TOKEN)
# except:
#     bot = None
#
# RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
# RUBITIME_BASE_URL = "https://rubitime.ru/api2/"
#
# # Security
# security = HTTPBearer()
#
#
# # Pydantic models
# class AdminBase(BaseModel):
#     login: str
#     password: str
#
#
# class TokenResponse(BaseModel):
#     access_token: str
#     token_type: str = "bearer"
#
#
# # class UserBase(BaseModel):
# #     id: int
# #     telegram_id: int
# #     full_name: Optional[str]
# #     phone: Optional[str]
# #     email: Optional[str]
# #     username: Optional[str]
# #     successful_bookings: int
# #     language_code: str
# #     invited_count: int
# #     reg_date: Optional[datetime]
# #     first_join_time: datetime
# #     agreed_to_terms: bool
# #     avatar: Optional[str]
# #     referrer_id: Optional[int]
# #
# #
# # class UserUpdate(BaseModel):
# #     full_name: Optional[str] = None
# #     phone: Optional[str] = None
# #     email: Optional[str] = None
# class UserBase(BaseModel):
#     """Базовая модель пользователя для API"""
#
#     id: int
#     telegram_id: int
#     full_name: Optional[str]
#     phone: Optional[str]
#     email: Optional[str]
#     username: Optional[str]
#     successful_bookings: int
#     language_code: str
#     invited_count: int
#     reg_date: Optional[datetime]
#     first_join_time: datetime
#     agreed_to_terms: bool
#     avatar: Optional[str]
#     referrer_id: Optional[int]
#
#     class Config:
#         from_attributes = True
#
#
# class UserUpdate(BaseModel):
#     """Модель для обновления пользователя"""
#
#     full_name: Optional[str] = None
#     phone: Optional[str] = None
#     email: Optional[str] = None
#     username: Optional[str] = None
#     language_code: Optional[str] = None
#     avatar: Optional[str] = None
#     agreed_to_terms: Optional[bool] = None
#     reg_date: Optional[str] = None  # Принимаем как строку ISO format
#     successful_bookings: Optional[int] = None
#     invited_count: Optional[int] = None
#
#
# class UserCreate(BaseModel):
#     """Модель для создания пользователя"""
#
#     telegram_id: int
#     username: Optional[str] = None
#     language_code: str = "ru"
#     referrer_id: Optional[int] = None
#     full_name: Optional[str] = None
#     phone: Optional[str] = None
#     email: Optional[str] = None
#
#
# class TariffBase(BaseModel):
#     id: int
#     name: str
#     description: str
#     price: float
#     purpose: Optional[str]
#     service_id: Optional[int]
#     is_active: bool
#
#
# class PromocodeBase(BaseModel):
#     id: int
#     name: str
#     discount: int
#     usage_quantity: int
#     expiration_date: Optional[datetime]
#     is_active: bool
#
#
# class BookingBase(BaseModel):
#     id: int
#     user_id: int
#     tariff_id: int
#     visit_date: date
#     visit_time: Optional[time]
#     duration: Optional[int]
#     promocode_id: Optional[int]
#     amount: float
#     payment_id: Optional[str]
#     paid: bool
#     rubitime_id: Optional[str]
#     confirmed: bool
#     created_at: datetime
#
#     class Config:
#         from_attributes = True
#
#
# class NewsletterBase(BaseModel):
#     id: int
#     message: str
#     created_at: datetime
#     recipient_count: int
#
#
# class TicketBase(BaseModel):
#     id: int
#     user_id: int
#     description: str
#     photo_id: Optional[str]
#     status: str
#     comment: Optional[str]
#     created_at: datetime
#     updated_at: datetime
#
#
# class NotificationBase(BaseModel):
#     id: int
#     user_id: int
#     message: str
#     created_at: datetime
#     booking_id: Optional[int]
#     ticket_id: Optional[int]
#     target_url: Optional[str]
#     is_read: bool
#
#
# class BookingCreate(BaseModel):
#     user_id: int
#     tariff_id: int
#     visit_date: date
#     visit_time: Optional[time] = None
#     duration: Optional[int] = None
#     promocode_id: Optional[int] = None
#     amount: float
#     payment_id: Optional[str] = None
#     paid: bool = False
#     confirmed: bool = False
#
#
# class TicketCreate(BaseModel):
#     user_id: int
#     description: str
#     photo_id: Optional[str] = None
#     status: Optional[str] = "OPEN"
#     comment: Optional[str] = None
#
#
# class NotificationUpdate(BaseModel):
#     is_read: bool = True
#
#
# # JWT functions
# def create_access_token(data: dict):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)
#     return encoded_jwt
#
#
# def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     token = credentials.credentials
#     try:
#         payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
#         username: str = payload.get("sub")
#         if username is None:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Could not validate credentials",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )
#         return username
#     except InvalidTokenError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#
#
# def get_db():
#     db = DBSession()
#     try:
#         yield db
#     finally:
#         db.close()
#
#
# # Routes
# @app.get("/")
# async def root():
#     return {"message": "API is running"}
#
#
# @app.post("/login", response_model=TokenResponse)
# async def login(credentials: AdminBase, db: Session = Depends(get_db)):
#     admin = db.query(Admin).filter(Admin.login == credentials.login).first()
#     if not admin or not check_password_hash(admin.password, credentials.password):
#         raise HTTPException(status_code=401, detail="Invalid credentials")
#
#     access_token = create_access_token(data={"sub": admin.login})
#     return {"access_token": access_token}
#
#
# @app.get("/verify_token")
# async def verify_token_endpoint(username: str = Depends(verify_token)):
#     return {"valid": True, "username": username}
#
#
# @app.get("/logout")
# async def logout():
#     return {"message": "Successfully logged out"}
#
#
# @app.get("/users", response_model=List[UserBase])
# async def get_users(
#     # Убираем параметры пагинации - теперь возвращаем всех пользователей
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Получить всех пользователей (пагинация на фронтенде)"""
#     users = (
#         db.query(User).order_by(User.reg_date.desc()).all()
#     )  # Получаем всех пользователей
#     return users
#
#
# @app.get("/users/{user_id}", response_model=UserBase)
# async def get_user(
#     user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user
#
#
# # Эндпоинт для обновления пользователя
# @app.put("/users/{user_id}", response_model=UserBase)
# async def update_user(
#     user_id: int,
#     user_update: UserUpdate,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Обновляем только переданные поля
#     if user_update.full_name is not None:
#         user.full_name = user_update.full_name
#     if user_update.phone is not None:
#         user.phone = user_update.phone
#     if user_update.email is not None:
#         user.email = user_update.email
#
#     db.commit()
#     db.refresh(user)
#     return user
#
#
# @app.post("/users/{user_id}/avatar")
# async def upload_user_avatar(
#     user_id: int,
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Загрузить аватар пользователя"""
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#     # Проверяем тип файла
#     if not file.content_type.startswith("image/"):
#         raise HTTPException(status_code=400, detail="Файл должен быть изображением")
#
#     # Создаём директорию если её нет
#     AVATARS_DIR.mkdir(exist_ok=True)
#
#     # Удаляем старый аватар пользователя если он есть
#     if user.avatar:
#         old_avatar_path = AVATARS_DIR / user.avatar
#         if old_avatar_path.exists():
#             old_avatar_path.unlink()
#
#     # Сохраняем новый аватар с именем telegram_id.jpg
#     avatar_filename = f"{user.telegram_id}.jpg"
#     avatar_path = AVATARS_DIR / avatar_filename
#
#     try:
#         contents = await file.read()
#         with open(avatar_path, "wb") as f:
#             f.write(contents)
#
#         # ✅ ПРАВИЛЬНО - сохраняем только имя файла
#         user.avatar = avatar_filename  # Например: "267863612.jpg"
#         db.commit()
#
#         return {"message": "Аватар успешно загружен", "filename": avatar_filename}
#
#     except Exception as e:
#         logger.error(f"Ошибка при сохранении аватара: {e}")
#         raise HTTPException(status_code=500, detail="Ошибка при сохранении файла")
#
#
# @app.delete("/users/{user_id}/avatar")
# async def delete_user_avatar(
#     user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Удалить аватар пользователя"""
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="Пользователь не найден")
#
#     deleted = False
#
#     # Удаляем файл аватара если он есть
#     if user.avatar:
#         # avatar содержит только имя файла, например "267863612.jpg"
#         avatar_path = AVATARS_DIR / user.avatar
#         if avatar_path.exists():
#             try:
#                 avatar_path.unlink()
#                 deleted = True
#             except Exception as e:
#                 logger.error(f"Ошибка при удалении файла аватара {avatar_path}: {e}")
#
#     # Также пытаемся удалить по стандартному пути
#     standard_path = AVATARS_DIR / f"{user.telegram_id}.jpg"
#     if standard_path.exists():
#         try:
#             standard_path.unlink()
#             deleted = True
#         except Exception as e:
#             logger.error(
#                 f"Ошибка при удалении стандартного аватара {standard_path}: {e}"
#             )
#
#     # Очищаем запись в базе данных
#     user.avatar = None
#     db.commit()
#
#     return {
#         "message": (
#             "Аватар успешно удалён" if deleted else "Запись аватара удалена из БД"
#         )
#     }
#
#
# @app.get("/bookings", response_model=List[BookingBase])
# async def get_bookings(
#     page: int = 1,
#     per_page: int = 20,
#     user_query: Optional[str] = None,
#     date_query: Optional[str] = None,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     query = db.query(Booking).order_by(Booking.created_at.desc())
#
#     if user_query:
#         query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))
#
#     if date_query:
#         query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
#         query = query.filter(Booking.visit_date == query_date)
#
#     bookings = query.offset((page - 1) * per_page).limit(per_page).all()
#     return bookings
#
#
# @app.get("/bookings/{booking_id}", response_model=BookingBase)
# async def get_booking(
#     booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     booking = db.query(Booking).filter(Booking.id == booking_id).first()
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
#     return booking
#
#
# @app.post("/bookings", response_model=dict)
# async def create_booking(
#     booking_data: BookingCreate,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     tariff = db.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
#     if not tariff:
#         raise HTTPException(status_code=404, detail="Tariff not found")
#
#     amount = booking_data.amount
#     promocode = None
#     if booking_data.promocode_id:
#         promocode = (
#             db.query(Promocode)
#             .filter(Promocode.id == booking_data.promocode_id)
#             .first()
#         )
#         if promocode:
#             amount = amount * (1 - promocode.discount / 100)
#
#     rubitime_id = None
#     if RUBITIME_API_KEY:
#         rubitime_params = {
#             "user_id": str(user.telegram_id),
#             "service_id": tariff.service_id,
#             "date": booking_data.visit_date.strftime("%Y-%m-%d"),
#             "time": (
#                 booking_data.visit_time.strftime("%H:%M")
#                 if booking_data.visit_time
#                 else "09:00"
#             ),
#             "duration": booking_data.duration * 60 if booking_data.duration else 540,
#         }
#         rubitime_id = await rubitime("create_record", rubitime_params)
#
#     booking = Booking(
#         user_id=user.id,
#         tariff_id=booking_data.tariff_id,
#         visit_date=booking_data.visit_date,
#         visit_time=booking_data.visit_time,
#         duration=booking_data.duration,
#         promocode_id=booking_data.promocode_id,
#         amount=amount,
#         payment_id=booking_data.payment_id,
#         paid=booking_data.paid,
#         rubitime_id=rubitime_id,
#         confirmed=booking_data.confirmed,
#     )
#     db.add(booking)
#     db.commit()
#     db.refresh(booking)
#
#     # Create notification for admin
#     booking_data_dict = {
#         "tariff_purpose": tariff.purpose,
#         "tariff_name": tariff.name,
#         "visit_date": booking_data.visit_date,
#         "visit_time": booking_data.visit_time,
#         "duration": booking_data.duration,
#         "promocode_name": promocode.name if promocode else None,
#         "discount": promocode.discount if promocode else 0,
#         "amount": amount,
#     }
#
#     admin_message = format_booking_notification(user, tariff, booking_data_dict)
#
#     # Create notification in database
#     notification = Notification(
#         user_id=user.id,
#         message=admin_message,
#         booking_id=booking.id,
#         target_url=f"/bookings/{booking.id}",
#     )
#     db.add(notification)
#     db.commit()
#
#     # Send to Telegram if bot is available
#     if bot and ADMIN_TELEGRAM_ID:
#         try:
#             await bot.send_message(
#                 chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
#             )
#         except Exception as e:
#             logger.error(f"Failed to send Telegram notification: {e}")
#
#     return {"id": booking.id, "message": "Booking created successfully"}
#
#
# @app.put("/bookings/{booking_id}", response_model=dict)
# async def update_booking(
#     booking_id: int,
#     confirmed: bool,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     booking = db.query(Booking).get(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
#
#     booking.confirmed = confirmed
#     db.commit()
#
#     if bot and confirmed:
#         user = db.query(User).get(booking.user_id)
#         tariff = db.query(Tariff).get(booking.tariff_id)
#         if user and tariff:
#             try:
#                 message = f"✅ Ваша бронь подтверждена!\n\n📋 Тариф: {tariff.name}\n📅 Дата: {booking.visit_date}"
#                 await bot.send_message(
#                     chat_id=user.telegram_id, text=message, parse_mode="HTML"
#                 )
#             except Exception as e:
#                 logger.error(f"Failed to send confirmation: {e}")
#
#     return {"message": "Booking updated successfully"}
#
#
# @app.delete("/bookings/{booking_id}", response_model=dict)
# async def delete_booking(
#     booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     booking = db.query(Booking).get(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
#
#     db.delete(booking)
#     db.commit()
#     return {"message": "Booking deleted successfully"}
#
#
# @app.get("/tariffs/active", response_model=List[TariffBase])
# async def get_active_tariffs(
#     db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Получить только активные тарифы"""
#     # tariffs = db.query(Tariff).filter(Tariff.is_active == True).all()
#     tariffs = db.query(Tariff).filter_by(is_active=True).all()
#     return tariffs
#
#
# @app.get("/tariffs", response_model=List[TariffBase])
# async def get_tariffs(db: Session = Depends(get_db), _: str = Depends(verify_token)):
#     tariffs = db.query(Tariff).all()
#     return tariffs
#
#
# @app.get("/tariffs/{tariff_id}", response_model=TariffBase)
# async def get_tariff(
#     tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     tariff = db.query(Tariff).get(tariff_id)
#     if not tariff:
#         raise HTTPException(status_code=404, detail="Tariff not found")
#     return tariff
#
#
# @app.post("/tariffs", response_model=dict)
# async def create_tariff(
#     tariff_data: TariffBase,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     tariff = Tariff(**tariff_data.dict(exclude={"id"}))
#     db.add(tariff)
#     db.commit()
#     return {"id": tariff.id, "message": "Tariff created successfully"}
#
#
# @app.delete("/tariffs/{tariff_id}", response_model=dict)
# async def delete_tariff(
#     tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     tariff = db.query(Tariff).get(tariff_id)
#     if not tariff:
#         raise HTTPException(status_code=404, detail="Tariff not found")
#
#     db.delete(tariff)
#     db.commit()
#     return {"message": "Tariff deleted successfully"}
#
#
# @app.get("/promocodes", response_model=List[PromocodeBase])
# async def get_promocodes(db: Session = Depends(get_db), _: str = Depends(verify_token)):
#     promocodes = db.query(Promocode).all()
#     return promocodes
#
#
# @app.get("/promocodes/{promocode_id}", response_model=PromocodeBase)
# async def get_promocode(
#     promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     promocode = db.query(Promocode).get(promocode_id)
#     if not promocode:
#         raise HTTPException(status_code=404, detail="Promocode not found")
#     return promocode
#
#
# @app.post("/promocodes", response_model=dict)
# async def create_promocode(
#     promocode_data: PromocodeBase,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     promocode = Promocode(**promocode_data.dict(exclude={"id"}))
#     db.add(promocode)
#     db.commit()
#     return {"id": promocode.id, "message": "Promocode created successfully"}
#
#
# @app.delete("/promocodes/{promocode_id}", response_model=dict)
# async def delete_promocode(
#     promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     promocode = db.query(Promocode).get(promocode_id)
#     if not promocode:
#         raise HTTPException(status_code=404, detail="Promocode not found")
#
#     db.delete(promocode)
#     db.commit()
#     return {"message": "Promocode deleted successfully"}
#
#
# @app.get("/tickets", response_model=List[TicketBase])
# async def get_tickets(
#     page: int = 1,
#     per_page: int = 20,
#     status: Optional[str] = None,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     query = db.query(Ticket).order_by(Ticket.created_at.desc())
#
#     if status:
#         query = query.filter(Ticket.status == status)
#
#     tickets = query.offset((page - 1) * per_page).limit(per_page).all()
#     return tickets
#
#
# @app.get("/tickets/{ticket_id}", response_model=TicketBase)
# async def get_ticket(
#     ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
#     if not ticket:
#         raise HTTPException(status_code=404, detail="Ticket not found")
#     return ticket
#
#
# @app.post("/tickets", response_model=dict)
# async def create_ticket(
#     ticket_data: TicketCreate,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     try:
#         status_enum = TicketStatus.OPEN
#         if ticket_data.status:
#             status_enum = TicketStatus(ticket_data.status)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid ticket status")
#
#     ticket = Ticket(
#         user_id=user.id,
#         description=ticket_data.description,
#         photo_id=ticket_data.photo_id,
#         status=status_enum,
#         comment=ticket_data.comment,
#     )
#     db.add(ticket)
#     db.commit()
#     db.refresh(ticket)
#
#     # Create notification
#     ticket_data_dict = {
#         "description": ticket_data.description,
#         "photo_id": ticket_data.photo_id,
#         "status": status_enum.name,
#     }
#
#     admin_message = format_ticket_notification(user, ticket_data_dict)
#
#     notification = Notification(
#         user_id=user.id,
#         message=admin_message,
#         ticket_id=ticket.id,
#         target_url=f"/tickets/{ticket.id}",
#     )
#     db.add(notification)
#     db.commit()
#
#     if bot and ADMIN_TELEGRAM_ID:
#         try:
#             await bot.send_message(
#                 chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
#             )
#         except Exception as e:
#             logger.error(f"Failed to send Telegram notification: {e}")
#
#     return {"id": ticket.id, "message": "Ticket created successfully"}
#
#
# @app.put("/tickets/{ticket_id}", response_model=dict)
# async def update_ticket(
#     ticket_id: int,
#     status: str,
#     comment: Optional[str] = None,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     ticket = db.query(Ticket).get(ticket_id)
#     if not ticket:
#         raise HTTPException(status_code=404, detail="Ticket not found")
#
#     try:
#         ticket.status = TicketStatus(status)
#     except ValueError:
#         raise HTTPException(status_code=400, detail="Invalid ticket status")
#
#     if comment:
#         ticket.comment = comment
#
#     ticket.updated_at = datetime.now(MOSCOW_TZ)
#     db.commit()
#
#     return {"message": "Ticket updated successfully"}
#
#
# @app.delete("/tickets/{ticket_id}", response_model=dict)
# async def delete_ticket(
#     ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     ticket = db.query(Ticket).get(ticket_id)
#     if not ticket:
#         raise HTTPException(status_code=404, detail="Ticket not found")
#
#     db.delete(ticket)
#     db.commit()
#     return {"message": "Ticket deleted successfully"}
#
#
# @app.get("/notifications", response_model=List[NotificationBase])
# async def get_notifications(
#     page: int = 1,
#     per_page: int = 20,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     notifications = (
#         db.query(Notification)
#         .order_by(Notification.created_at.desc())
#         .offset((page - 1) * per_page)
#         .limit(per_page)
#         .all()
#     )
#     return notifications
#
#
# @app.get("/notifications/check_new")
# async def check_new_notifications(
#     since_id: int = 0, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     query = db.query(Notification).order_by(Notification.created_at.desc())
#
#     if since_id > 0:
#         query = query.filter(Notification.id > since_id)
#
#     notifications = query.limit(5).all()
#     return {"recent_notifications": notifications}
#
#
# @app.post("/notifications/mark_read/{notification_id}", response_model=dict)
# async def mark_notification_read(
#     notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     notification = (
#         db.query(Notification).filter(Notification.id == notification_id).first()
#     )
#     if not notification:
#         raise HTTPException(status_code=404, detail="Notification not found")
#
#     notification.is_read = True
#     db.commit()
#     return {"message": "Notification marked as read"}
#
#
# @app.post("/notifications/mark_all_read", response_model=dict)
# async def mark_all_notifications_read(
#     db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     db.query(Notification).filter(Notification.is_read == False).update(
#         {"is_read": True}
#     )
#     db.commit()
#     return {"message": "All notifications marked as read"}
#
#
# @app.get("/newsletters", response_model=List[NewsletterBase])
# async def get_newsletters(
#     page: int = 1,
#     per_page: int = 20,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     newsletters = (
#         db.query(Newsletter)
#         .order_by(Newsletter.created_at.desc())
#         .offset((page - 1) * per_page)
#         .limit(per_page)
#         .all()
#     )
#     return newsletters
#
#
# @app.post("/newsletters", response_model=dict)
# async def create_newsletter(
#     message: str, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     users = db.query(User).all()
#
#     newsletter = Newsletter(message=message, recipient_count=len(users))
#     db.add(newsletter)
#     db.commit()
#
#     if bot:
#         for user in users:
#             try:
#                 await bot.send_message(
#                     chat_id=user.telegram_id, text=message, parse_mode="HTML"
#                 )
#             except Exception as e:
#                 logger.error(f"Failed to send newsletter to {user.telegram_id}: {e}")
#
#     return {"id": newsletter.id, "message": "Newsletter sent successfully"}
#
#
# # Dashboard stats endpoint
# @app.get("/dashboard/stats")
# async def get_dashboard_stats(
#     db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     total_users = db.query(User).count()
#     total_bookings = db.query(Booking).count()
#     # Count only open tickets (not closed)
#     open_tickets = db.query(Ticket).filter(Ticket.status != TicketStatus.CLOSED).count()
#
#     return {
#         "total_users": total_users,
#         "total_bookings": total_bookings,
#         "open_tickets": open_tickets,
#     }
#
#
# async def rubitime(method: str, extra_params: dict) -> Optional[str]:
#     if not RUBITIME_API_KEY:
#         return None
#
#     url = f"{RUBITIME_BASE_URL}create-record"
#     params = {"api_key": RUBITIME_API_KEY, **extra_params}
#
#     async with aiohttp.ClientSession() as session:
#         async with session.post(url, json=params) as response:
#             if response.status == 200:
#                 data = await response.json()
#                 return data.get("data", {}).get("id")
#
#     return None
#
#
# async def check_payment_status(payment_id: str) -> Optional[str]:
#     try:
#         payment = await Payment.find_one(payment_id)
#         return payment.status if payment else None
#     except Exception as e:
#         logger.error(f"Failed to check payment status: {e}")
#         return None
#
#
# """
# Обновленный main.py с дополнительными эндпоинтами для бота
# Добавить эти эндпоинты в существующий main.py
# """
#
#
# # === Добавить эти эндпоинты в существующий main.py ===
#
#
# # User endpoints для бота
# @app.get("/users/telegram/{telegram_id}", response_model=UserBase)
# async def get_user_by_telegram(
#     telegram_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Получить пользователя по Telegram ID"""
#     user = db.query(User).filter(User.telegram_id == telegram_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     return user
#
#
# @app.post("/users/check_and_add")
# async def check_and_add_user(
#     user_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Проверить и добавить пользователя если его нет"""
#     telegram_id = user_data.get("telegram_id")
#
#     # Проверяем существующего пользователя
#     user = db.query(User).filter(User.telegram_id == telegram_id).first()
#
#     if user:
#         # Обновляем username если изменился
#         if user_data.get("username") and user.username != user_data.get("username"):
#             user.username = user_data.get("username")
#             db.commit()
#
#         # Проверяем полноту данных
#         is_complete = all(
#             [user.full_name, user.phone, user.email, user.agreed_to_terms]
#         )
#
#         return {
#             "user": {
#                 "id": user.id,
#                 "telegram_id": user.telegram_id,
#                 "full_name": user.full_name,
#                 "phone": user.phone,
#                 "email": user.email,
#                 "username": user.username,
#                 "successful_bookings": user.successful_bookings,
#                 "language_code": user.language_code,
#                 "invited_count": user.invited_count,
#                 "reg_date": user.reg_date,
#                 "first_join_time": user.first_join_time,
#                 "agreed_to_terms": user.agreed_to_terms,
#                 "avatar": user.avatar,
#                 "referrer_id": user.referrer_id,
#             },
#             "is_new": False,
#             "is_complete": is_complete,
#         }
#
#     # Создаем нового пользователя с минимальными данными
#     user = User(
#         telegram_id=telegram_id,
#         username=user_data.get("username"),
#         language_code=user_data.get("language_code", "ru"),
#         referrer_id=user_data.get("referrer_id"),
#         first_join_time=datetime.now(MOSCOW_TZ),
#         invited_count=0,
#         successful_bookings=0,
#         agreed_to_terms=False,
#     )
#
#     db.add(user)
#
#     # Обновляем счетчик приглашенных у реферера
#     if user.referrer_id:
#         referrer = db.query(User).filter(User.telegram_id == user.referrer_id).first()
#         if referrer:
#             referrer.invited_count += 1
#
#     db.commit()
#     db.refresh(user)
#
#     return {
#         "user": {
#             "id": user.id,
#             "telegram_id": user.telegram_id,
#             "full_name": user.full_name,
#             "phone": user.phone,
#             "email": user.email,
#             "username": user.username,
#             "successful_bookings": user.successful_bookings,
#             "language_code": user.language_code,
#             "invited_count": user.invited_count,
#             "reg_date": user.reg_date,
#             "first_join_time": user.first_join_time,
#             "agreed_to_terms": user.agreed_to_terms,
#             "avatar": user.avatar,
#             "referrer_id": user.referrer_id,
#         },
#         "is_new": True,
#         "is_complete": False,
#     }
#
#
# # Обновленный эндпоинт для обновления пользователя с поддержкой аватара
#
#
# @app.put("/users/{user_id}", response_model=UserBase)
# async def update_user_api(
#     user_id: int,
#     user_data: UserUpdate,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Обновить данные пользователя"""
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Обновляем поля если они переданы
#     update_dict = user_data.dict(exclude_unset=True)
#
#     for field, value in update_dict.items():
#         if value is not None:
#             setattr(user, field, value)
#
#     # Если передано имя файла аватара, сохраняем его
#     if "avatar" in update_dict:
#         user.avatar = update_dict["avatar"]
#
#     # Если передан флаг согласия с условиями
#     if "agreed_to_terms" in update_dict:
#         user.agreed_to_terms = update_dict["agreed_to_terms"]
#
#     # Если передана дата регистрации
#     if "reg_date" in update_dict:
#         if isinstance(update_dict["reg_date"], str):
#             try:
#                 user.reg_date = datetime.fromisoformat(
#                     update_dict["reg_date"].replace("Z", "+00:00")
#                 )
#             except:
#                 user.reg_date = datetime.now(MOSCOW_TZ)
#         else:
#             user.reg_date = update_dict["reg_date"]
#
#     db.commit()
#     db.refresh(user)
#
#     return user
#
#
# # Promocode endpoints
# @app.get("/promocodes/by_name/{name}", response_model=PromocodeBase)
# async def get_promocode_by_name(
#     name: str, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Получить промокод по имени"""
#     promocode = (
#         db.query(Promocode)
#         .filter(Promocode.name == name, Promocode.is_active == True)
#         .first()
#     )
#
#     if not promocode:
#         raise HTTPException(status_code=404, detail="Promocode not found or inactive")
#
#     # Проверяем срок действия
#     if promocode.expiration_date and promocode.expiration_date < datetime.now(
#         MOSCOW_TZ
#     ):
#         raise HTTPException(status_code=400, detail="Promocode expired")
#
#     return promocode
#
#
# @app.post("/promocodes/{promocode_id}/use")
# async def use_promocode(
#     promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Использовать промокод"""
#     promocode = db.query(Promocode).get(promocode_id)
#     if not promocode:
#         raise HTTPException(status_code=404, detail="Promocode not found")
#
#     promocode.usage_quantity += 1
#     db.commit()
#
#     return {"success": True, "usage_count": promocode.usage_quantity}
#
#
# # Enhanced Booking endpoints
# @app.post("/bookings", response_model=BookingBase)
# async def create_booking_api(
#     booking_data: BookingCreate,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Создать новое бронирование через API"""
#
#     # Получаем пользователя
#     user = db.query(User).filter(User.telegram_id == booking_data.user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Получаем тариф
#     tariff = db.query(Tariff).get(booking_data.tariff_id)
#     if not tariff:
#         raise HTTPException(status_code=404, detail="Tariff not found")
#
#     # Создаем бронирование
#     booking = Booking(
#         user_id=user.id,
#         tariff_id=booking_data.tariff_id,
#         visit_date=booking_data.visit_date,
#         visit_time=booking_data.visit_time,
#         duration=booking_data.duration,
#         promocode_id=booking_data.promocode_id,
#         amount=booking_data.amount,
#         payment_id=booking_data.payment_id,
#         paid=booking_data.paid,
#         confirmed=booking_data.confirmed,
#         created_at=datetime.now(MOSCOW_TZ),
#     )
#
#     db.add(booking)
#
#     # Создаем уведомление
#     notification = Notification(
#         user_id=user.id,
#         booking_id=booking.id,
#         message=f"Создана новая бронь на {booking.visit_date}",
#         target_url=f"/bookings/{booking.id}",
#         created_at=datetime.now(MOSCOW_TZ),
#         is_read=False,
#     )
#     db.add(notification)
#
#     # Обновляем счетчик успешных бронирований если оплачено
#     if booking.paid:
#         user.successful_bookings += 1
#
#     db.commit()
#     db.refresh(booking)
#
#     return booking
#
#
# @app.put("/bookings/{booking_id}/payment")
# async def update_booking_payment(
#     booking_id: int,
#     payment_data: dict,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Обновить статус оплаты бронирования"""
#     booking = db.query(Booking).get(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
#
#     booking.payment_id = payment_data.get("payment_id")
#     booking.paid = payment_data.get("paid", False)
#
#     if booking.paid:
#         # Обновляем счетчик пользователя
#         user = db.query(User).get(booking.user_id)
#         if user:
#             user.successful_bookings += 1
#
#     db.commit()
#
#     return {"success": True, "booking_id": booking_id, "paid": booking.paid}
#
#
# @app.put("/bookings/{booking_id}/confirm")
# async def confirm_booking_api(
#     booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Подтвердить бронирование"""
#     booking = db.query(Booking).get(booking_id)
#     if not booking:
#         raise HTTPException(status_code=404, detail="Booking not found")
#
#     booking.confirmed = True
#     db.commit()
#
#     # Отправляем уведомление пользователю
#     user = db.query(User).get(booking.user_id)
#     if user and bot:
#         tariff = db.query(Tariff).get(booking.tariff_id)
#         message = f"✅ Ваша бронь подтверждена!\n\n📋 Тариф: {tariff.name}\n📅 Дата: {booking.visit_date}"
#
#         try:
#             await bot.send_message(user.telegram_id, message)
#         except Exception as e:
#             logger.error(f"Ошибка отправки уведомления: {e}")
#
#     return {"success": True, "booking_id": booking_id}
#
#
# # Payment endpoints
# @app.post("/payments/create")
# async def create_payment_api(
#     payment_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Создать платеж через YooKassa"""
#     try:
#         from yookassa import Payment
#
#         payment = Payment.create(
#             {
#                 "amount": {"value": str(payment_data["amount"]), "currency": "RUB"},
#                 "confirmation": {
#                     "type": "redirect",
#                     "return_url": payment_data.get(
#                         "return_url", "https://t.me/your_bot"
#                     ),
#                 },
#                 "capture": True,
#                 "description": payment_data.get("description", "Оплата бронирования"),
#                 "metadata": payment_data.get("metadata", {}),
#             }
#         )
#
#         return {
#             "payment_id": payment.id,
#             "confirmation_url": payment.confirmation.confirmation_url,
#             "status": payment.status,
#         }
#     except Exception as e:
#         logger.error(f"Ошибка создания платежа: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.get("/payments/{payment_id}/status")
# async def check_payment_status_api(payment_id: str, _: str = Depends(verify_token)):
#     """Проверить статус платежа"""
#     try:
#         from yookassa import Payment
#
#         payment = Payment.find_one(payment_id)
#         return {
#             "payment_id": payment.id,
#             "status": payment.status,
#             "paid": payment.paid,
#             "amount": float(payment.amount.value) if payment.amount else 0,
#         }
#     except Exception as e:
#         logger.error(f"Ошибка проверки статуса платежа: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.post("/payments/{payment_id}/cancel")
# async def cancel_payment_api(payment_id: str, _: str = Depends(verify_token)):
#     """Отменить платеж"""
#     try:
#         from yookassa import Payment, Refund
#
#         # Проверяем статус платежа
#         payment = Payment.find_one(payment_id)
#
#         if payment.status == "succeeded":
#             # Если платеж прошел, делаем возврат
#             refund = Refund.create({"payment_id": payment_id, "amount": payment.amount})
#             return {"success": True, "refund_id": refund.id, "status": "refunded"}
#         else:
#             # Если платеж еще не завершен, отменяем
#             Payment.cancel(payment_id)
#             return {"success": True, "status": "cancelled"}
#     except Exception as e:
#         logger.error(f"Ошибка отмены платежа: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# # Rubitime integration
# @app.post("/rubitime/create_record")
# async def create_rubitime_record_api(
#     rubitime_params: dict, _: str = Depends(verify_token)
# ):
#     """Создать запись в Rubitime"""
#     try:
#         rubitime_id = await rubitime("create_record", rubitime_params)
#         return {"rubitime_id": rubitime_id}
#     except Exception as e:
#         logger.error(f"Ошибка создания записи в Rubitime: {e}")
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# # Notification endpoints
# @app.post("/notifications/send")
# async def send_notification_api(
#     notification_data: dict,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Отправить уведомление пользователю через бота"""
#     user_id = notification_data.get("user_id")
#     message = notification_data.get("message")
#     target_url = notification_data.get("target_url")
#
#     # Получаем пользователя
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Создаем уведомление в БД
#     notification = Notification(
#         user_id=user_id,
#         message=message,
#         target_url=target_url,
#         created_at=datetime.now(MOSCOW_TZ),
#         is_read=False,
#     )
#     db.add(notification)
#     db.commit()
#
#     # Отправляем через бота если он доступен
#     if bot:
#         try:
#             await bot.send_message(user.telegram_id, message, parse_mode="HTML")
#             return {"success": True, "sent": True}
#         except Exception as e:
#             logger.error(f"Ошибка отправки сообщения: {e}")
#             return {"success": True, "sent": False, "error": str(e)}
#
#     return {"success": True, "sent": False, "error": "Bot not available"}
#
#
# """
# Дополнительные эндпоинты для работы с тикетами
# Добавить в существующий main.py
# """
#
#
# # === Ticket endpoints для бота ===
#
#
# @app.post("/tickets", response_model=TicketBase)
# async def create_ticket_api(
#     ticket_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Создать новый тикет через API"""
#
#     # Получаем пользователя по telegram_id
#     telegram_id = ticket_data.get("user_id")  # В данном случае это telegram_id
#     user = db.query(User).filter(User.telegram_id == telegram_id).first()
#
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Определяем статус
#     status_str = ticket_data.get("status", "OPEN")
#     try:
#         status_enum = TicketStatus[status_str]
#     except KeyError:
#         status_enum = TicketStatus.OPEN
#
#     # Создаем тикет
#     ticket = Ticket(
#         user_id=user.id,
#         description=ticket_data.get("description"),
#         photo_id=ticket_data.get("photo_id"),
#         status=status_enum,
#         comment=ticket_data.get("comment"),
#         created_at=datetime.now(MOSCOW_TZ),
#         updated_at=datetime.now(MOSCOW_TZ),
#     )
#
#     db.add(ticket)
#
#     # Создаем уведомление
#     notification = Notification(
#         user_id=user.id,
#         ticket_id=ticket.id,
#         message=f"Создано обращение #{ticket.id}",
#         target_url=f"/tickets/{ticket.id}",
#         created_at=datetime.now(MOSCOW_TZ),
#         is_read=False,
#     )
#     db.add(notification)
#
#     db.commit()
#     db.refresh(ticket)
#
#     # Возвращаем данные тикета
#     return {
#         "id": ticket.id,
#         "user_id": ticket.user_id,
#         "description": ticket.description,
#         "photo_id": ticket.photo_id,
#         "status": ticket.status.value,
#         "comment": ticket.comment,
#         "created_at": ticket.created_at,
#         "updated_at": ticket.updated_at,
#     }
#
#
# @app.get("/users/{user_id}/tickets", response_model=List[TicketBase])
# async def get_user_tickets(
#     user_id: int,
#     status: Optional[str] = None,
#     page: int = 1,
#     per_page: int = 20,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Получить тикеты пользователя"""
#
#     # Проверяем существование пользователя
#     user = db.query(User).get(user_id)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Формируем запрос
#     query = db.query(Ticket).filter(Ticket.user_id == user_id)
#
#     # Фильтр по статусу если указан
#     if status:
#         try:
#             status_enum = TicketStatus[status]
#             query = query.filter(Ticket.status == status_enum)
#         except KeyError:
#             pass
#
#     # Сортировка и пагинация
#     query = query.order_by(Ticket.created_at.desc())
#     tickets = query.offset((page - 1) * per_page).limit(per_page).all()
#
#     # Возвращаем список тикетов
#     return [
#         {
#             "id": t.id,
#             "user_id": t.user_id,
#             "description": t.description,
#             "photo_id": t.photo_id,
#             "status": t.status.value,
#             "comment": t.comment,
#             "created_at": t.created_at,
#             "updated_at": t.updated_at,
#         }
#         for t in tickets
#     ]
#
#
# @app.get("/users/telegram/{telegram_id}/tickets", response_model=List[TicketBase])
# async def get_user_tickets_by_telegram(
#     telegram_id: int,
#     status: Optional[str] = None,
#     page: int = 1,
#     per_page: int = 20,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Получить тикеты пользователя по Telegram ID"""
#
#     # Получаем пользователя по telegram_id
#     user = db.query(User).filter(User.telegram_id == telegram_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     # Формируем запрос
#     query = db.query(Ticket).filter(Ticket.user_id == user.id)
#
#     # Фильтр по статусу если указан
#     if status:
#         try:
#             status_enum = TicketStatus[status]
#             query = query.filter(Ticket.status == status_enum)
#         except KeyError:
#             pass
#
#     # Сортировка и пагинация
#     query = query.order_by(Ticket.created_at.desc())
#     tickets = query.offset((page - 1) * per_page).limit(per_page).all()
#
#     # Возвращаем список тикетов
#     return [
#         {
#             "id": t.id,
#             "user_id": t.user_id,
#             "description": t.description,
#             "photo_id": t.photo_id,
#             "status": t.status.value,
#             "comment": t.comment,
#             "created_at": t.created_at,
#             "updated_at": t.updated_at,
#         }
#         for t in tickets
#     ]
#
#
# @app.put("/tickets/{ticket_id}/status")
# async def update_ticket_status(
#     ticket_id: int,
#     status_data: dict,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Обновить статус тикета"""
#
#     ticket = db.query(Ticket).get(ticket_id)
#     if not ticket:
#         raise HTTPException(status_code=404, detail="Ticket not found")
#
#     # Обновляем статус
#     new_status = status_data.get("status")
#     if new_status:
#         try:
#             ticket.status = TicketStatus[new_status]
#         except KeyError:
#             raise HTTPException(status_code=400, detail="Invalid status")
#
#     # Обновляем комментарий если есть
#     comment = status_data.get("comment")
#     if comment:
#         ticket.comment = comment
#
#     ticket.updated_at = datetime.now(MOSCOW_TZ)
#
#     # Создаем уведомление для пользователя
#     user = db.query(User).get(ticket.user_id)
#     if user:
#         status_text = {
#             TicketStatus.OPEN: "открыто",
#             TicketStatus.IN_PROGRESS: "в работе",
#             TicketStatus.CLOSED: "закрыто",
#         }.get(ticket.status, "изменен")
#
#         notification = Notification(
#             user_id=user.id,
#             ticket_id=ticket.id,
#             message=f"Статус обращения #{ticket.id} изменен на: {status_text}",
#             target_url=f"/tickets/{ticket.id}",
#             created_at=datetime.now(MOSCOW_TZ),
#             is_read=False,
#         )
#         db.add(notification)
#
#         # Отправляем уведомление через бота если он доступен
#         if bot:
#             try:
#                 message = f"📋 Обращение #{ticket.id}\n"
#                 message += f"Статус изменен на: {status_text}\n"
#                 if comment:
#                     message += f"Комментарий: {comment}"
#
#                 await bot.send_message(user.telegram_id, message, parse_mode="HTML")
#             except Exception as e:
#                 logger.error(f"Ошибка отправки уведомления: {e}")
#
#     db.commit()
#
#     return {"success": True, "ticket_id": ticket_id, "status": ticket.status.value}
#
#
# @app.get("/tickets/stats")
# async def get_tickets_stats(
#     db: Session = Depends(get_db), _: str = Depends(verify_token)
# ):
#     """Получить статистику по тикетам"""
#
#     total_tickets = db.query(Ticket).count()
#     open_tickets = db.query(Ticket).filter(Ticket.status == TicketStatus.OPEN).count()
#     in_progress_tickets = (
#         db.query(Ticket).filter(Ticket.status == TicketStatus.IN_PROGRESS).count()
#     )
#     closed_tickets = (
#         db.query(Ticket).filter(Ticket.status == TicketStatus.CLOSED).count()
#     )
#
#     # Среднее время закрытия тикетов (в часах)
#     closed_tickets_times = (
#         db.query(Ticket.created_at, Ticket.updated_at)
#         .filter(Ticket.status == TicketStatus.CLOSED)
#         .all()
#     )
#
#     avg_resolution_time = 0
#     if closed_tickets_times:
#         total_time = sum(
#             (updated - created).total_seconds() / 3600
#             for created, updated in closed_tickets_times
#         )
#         avg_resolution_time = round(total_time / len(closed_tickets_times), 1)
#
#     return {
#         "total": total_tickets,
#         "open": open_tickets,
#         "in_progress": in_progress_tickets,
#         "closed": closed_tickets,
#         "avg_resolution_hours": avg_resolution_time,
#     }
#
#
# """
# Дополнительный эндпоинт для создания уведомлений в БД
# Добавить в существующий main.py
# """
#
#
# # === Notification endpoint для создания уведомлений в БД ===
#
#
# @app.post("/notifications/create")
# async def create_notification(
#     notification_data: dict,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Создать уведомление в БД (для отображения в админке)"""
#
#     user_id = notification_data.get("user_id")
#     message = notification_data.get("message")
#     target_url = notification_data.get("target_url")
#
#     # Проверяем существование пользователя
#     user = db.query(User).get(user_id)
#     if not user:
#         # Если передан user_id как telegram_id, пытаемся найти по нему
#         user = db.query(User).filter(User.telegram_id == user_id).first()
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
#         user_id = user.id
#
#     # Создаем уведомление в БД
#     notification = Notification(
#         user_id=user_id,
#         message=message,
#         target_url=target_url,
#         created_at=datetime.now(MOSCOW_TZ),
#         is_read=False,
#     )
#
#     db.add(notification)
#     db.commit()
#     db.refresh(notification)
#
#     return {
#         "success": True,
#         "notification_id": notification.id,
#         "created_at": notification.created_at,
#     }
#
#
# @app.on_event("startup")
# async def startup_event():
#     init_db()
#     admin_login = os.getenv("ADMIN_LOGIN", "admin")
#     admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
#     create_admin(admin_login, admin_password)
#
#     # Создаем placeholder аватар если его нет
#     placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
#     if not placeholder_path.exists():
#         # Создаем простой placeholder (серый квадрат)
#         try:
#             from PIL import Image, ImageDraw
#
#             img = Image.new("RGB", (200, 200), color="#E2E8F0")
#             draw = ImageDraw.Draw(img)
#             # Рисуем круг
#             draw.ellipse([10, 10, 190, 190], fill="#CBD5E0")
#             # Рисуем силуэт пользователя
#             draw.ellipse([75, 50, 125, 100], fill="#718096")  # голова
#             draw.ellipse([50, 100, 150, 180], fill="#718096")  # тело
#             img.save(placeholder_path)
#             logger.info("Placeholder avatar created")
#         except ImportError:
#             logger.warning("PIL not installed, placeholder avatar not created")
#
#     logger.info("Application started successfully")
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, time, date
from typing import Optional, List, Dict, Any
import pytz

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import jwt
from werkzeug.security import check_password_hash

# from PIL import Image, ImageDraw
from aiogram import Bot
import aiohttp

# Импорты моделей и утилит
from models.models import *
from utils.logger import get_logger
from yookassa import Payment, Refund

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
    promocodes = db.query(Promocode).all()
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
    promocode_data: dict, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Создание нового промокода."""
    promocode = Promocode(**promocode_data)
    db.add(promocode)
    db.commit()
    db.refresh(promocode)
    return promocode


@app.delete("/promocodes/{promocode_id}")
async def delete_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление промокода."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    db.delete(promocode)
    db.commit()
    return {"message": "Promocode deleted"}


# ================== TICKET ENDPOINTS ==================


@app.get("/tickets", response_model=List[TicketBase])
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение списка тикетов с фильтрацией."""
    query = db.query(Ticket).order_by(Ticket.created_at.desc())

    if status:
        try:
            status_enum = TicketStatus[status]
            query = query.filter(Ticket.status == status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid status")

    tickets = query.offset((page - 1) * per_page).limit(per_page).all()
    return tickets


@app.get("/tickets/{ticket_id}", response_model=TicketBase)
async def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение тикета по ID."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


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

    admin_message = format_ticket_notification(user, ticket_data_dict)

    if bot and ADMIN_TELEGRAM_ID:
        try:
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")

    return {"id": ticket.id, "message": "Ticket created successfully"}


@app.get("/tickets/user/{user_id}")
async def get_user_tickets(
    user_id: int, status: Optional[str] = None, db: Session = Depends(get_db)
):
    """Получение тикетов пользователя. Используется ботом."""
    # Сначала находим пользователя по telegram_id
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Ticket).filter(Ticket.user_id == user.id)

    if status:
        try:
            status_enum = TicketStatus[status]
            query = query.filter(Ticket.status == status_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail="Invalid status")

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
    """Обновление статуса тикета."""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    new_status = status_data.get("status")
    comment = status_data.get("comment")

    if new_status:
        try:
            ticket.status = TicketStatus(new_status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")

    if comment:
        ticket.comment = comment

    ticket.updated_at = datetime.now(MOSCOW_TZ)
    db.commit()

    # Уведомляем пользователя
    if bot:
        user = db.query(User).get(ticket.user_id)
        status_text = {
            "Открыта": "🟢 Открыта",
            "В работе": "🟡 В работе",
            "Закрыта": "🔴 Закрыта",
        }

        message = f"📋 Обращение #{ticket.id}\n"
        message += f"Статус изменен на: {status_text.get(new_status, new_status)}\n"
        if comment:
            message += f"\n💬 Комментарий: {comment}"

        try:
            await bot.send_message(user.telegram_id, message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю: {e}")

    return {"message": "Ticket updated successfully"}


@app.delete("/tickets/{ticket_id}")
async def delete_ticket(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тикета."""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

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


# ================== STARTUP EVENT ==================


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    logger.info("Запуск приложения...")
    init_db()
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
