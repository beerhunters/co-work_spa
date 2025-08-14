import enum
from datetime import datetime
from sqlite3 import IntegrityError
from typing import Optional

import pytz
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    text,
    Boolean,
    Float,
    ForeignKey,
    Date,
    Time,
    select,
    Enum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from werkzeug.security import generate_password_hash, check_password_hash
import os
from pathlib import Path
from utils.logger import get_logger

# Тихая настройка логгера для модуля
logger = get_logger(__name__)

Base = declarative_base()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Создаем директорию data если её нет
DB_DIR = Path("/app/data")
DB_DIR.mkdir(exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_DIR}/coworking.db",  # Используем абсолютный путь
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    echo=False,  # Для отладки можно поставить True
)
Session = sessionmaker(bind=engine)


class Admin(Base):
    """Модель администратора."""

    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    @property
    def is_active(self) -> bool:
        return True

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)


class User(Base):
    """Модель пользователя."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_join_time = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False
    )
    full_name = Column(String)
    phone = Column(String)
    email = Column(String)
    username = Column(String)
    successful_bookings = Column(Integer, default=0)
    language_code = Column(String, default="ru")
    invited_count = Column(Integer, default=0)
    reg_date = Column(DateTime)
    agreed_to_terms = Column(Boolean, default=False)
    avatar = Column(String, nullable=True)
    referrer_id = Column(BigInteger, nullable=True)  # Убрать ForeignKey пока что

    # Связи
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bookings = relationship(
        "Booking",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tickets = relationship(
        "Ticket",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User {self.telegram_id} - {self.full_name}>"


class Tariff(Base):
    """Модель тарифа."""

    __tablename__ = "tariffs"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, index=True)
    description = Column(String(255), default="Описание тарифа", nullable=False)
    price = Column(Float, nullable=False)
    purpose = Column(String(50), nullable=True)
    service_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, index=True)


class Promocode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    discount = Column(Integer, nullable=False)
    usage_quantity = Column(Integer, default=0)  # Количество оставшихся использований
    expiration_date = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=False, index=True)

    def __repr__(self) -> str:
        return f"<Promocode(id={self.id}, name='{self.name}', discount={self.discount}%, uses={self.usage_quantity})>"

    @property
    def is_available(self) -> bool:
        """Проверяет, доступен ли промокод для использования."""
        if not self.is_active:
            return False

        if self.expiration_date and self.expiration_date < datetime.now(MOSCOW_TZ):
            return False

        if self.usage_quantity <= 0:
            return False

        return True


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,  # Изменено с BigInteger на Integer
    )
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=False)
    visit_date = Column(Date, nullable=False)
    visit_time = Column(Time, nullable=True)
    duration = Column(Integer, nullable=True)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=True)
    amount = Column(Float, nullable=False)
    payment_id = Column(String(100), nullable=True)
    paid = Column(Boolean, default=False)
    rubitime_id = Column(String(100), nullable=True)
    confirmed = Column(Boolean, default=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False
    )

    # Связи
    user = relationship("User", back_populates="bookings")
    tariff = relationship("Tariff", backref="bookings")
    promocode = relationship("Promocode", backref="promocodes")
    notifications = relationship("Notification", back_populates="booking")


class Newsletter(Base):
    __tablename__ = "newsletters"
    id = Column(Integer, primary_key=True)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    recipient_count = Column(Integer, nullable=False)


class TicketStatus(enum.Enum):
    """Перечисление для статусов заявки."""

    OPEN = "Открыта"
    IN_PROGRESS = "В работе"
    CLOSED = "Закрыта"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(String, nullable=False)
    photo_id = Column(String, nullable=True)  # Фото от пользователя
    response_photo_id = Column(String, nullable=True)  # Фото в ответе от администратора
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(MOSCOW_TZ),
        onupdate=lambda: datetime.now(MOSCOW_TZ),
    )

    user = relationship("User", back_populates="tickets")
    notifications = relationship("Notification", back_populates="ticket")

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,  # Изменено с BigInteger на Integer
    )
    message = Column(String, nullable=False)
    target_url = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False
    )
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)

    # Связи
    user = relationship("User", back_populates="notifications")
    booking = relationship("Booking", back_populates="notifications")
    ticket = relationship("Ticket", back_populates="notifications")


def init_db() -> None:
    """Инициализация базы данных с WAL-режимом."""
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
        logger.info("WAL-режим успешно включён")
        Base.metadata.create_all(engine)
        logger.info("Таблицы базы данных созданы")


def create_admin(admin_login: str, admin_password: str) -> None:
    """Создает или обновляет администратора в базе данных."""
    session = Session()
    try:
        admin = session.query(Admin).filter_by(login=admin_login).first()
        if not admin:
            hashed_password = generate_password_hash(
                admin_password, method="pbkdf2:sha256"
            )
            admin = Admin(login=admin_login, password=hashed_password)
            session.add(admin)
            session.commit()
            logger.info(f"Создан администратор с логином: {admin_login}")
        else:
            if not check_password_hash(admin.password, admin_password):
                admin.password = generate_password_hash(
                    admin_password, method="pbkdf2:sha256"
                )
                session.commit()
                logger.info(
                    f"Обновлен пароль для администратора с логином: {admin_login}"
                )
            else:
                logger.info(
                    f"Администратор с логином {admin_login} уже существует с корректным паролем"
                )
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Ошибка уникальности при создании администратора: {e}")
        logger.info("Администратор уже существует, пропускаем создание")
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при создании/обновлении администратора: {e}")
        raise
    finally:
        session.close()
