from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserBase(BaseModel):
    """Базовая модель пользователя."""

    id: int
    telegram_id: int
    full_name: Optional[str]
    phone: Optional[str]
    email: Optional[EmailStr]
    username: Optional[str]
    successful_bookings: int
    language_code: str
    invited_count: int
    reg_date: Optional[datetime]
    first_join_time: datetime
    agreed_to_terms: bool
    avatar: Optional[str]
    referrer_id: Optional[int]
    admin_comment: Optional[str]
    is_banned: bool = False
    banned_at: Optional[datetime] = None
    ban_reason: Optional[str] = None
    banned_by: Optional[str] = None
    bot_blocked: bool = False
    bot_blocked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Модель для обновления данных пользователя."""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    avatar: Optional[str] = None
    agreed_to_terms: Optional[bool] = None
    reg_date: Optional[str] = None  # ISO строка
    successful_bookings: Optional[int] = None
    invited_count: Optional[int] = None
    admin_comment: Optional[str] = Field(None, max_length=500)
    bot_blocked: Optional[bool] = None
    bot_blocked_at: Optional[datetime] = None


class UserCreate(BaseModel):
    """Модель создания нового пользователя."""

    telegram_id: int
    username: Optional[str] = None
    language_code: str = "ru"
    referrer_id: Optional[int] = None


class UserStats(BaseModel):
    """Статистика пользователей."""

    total_users: int
    active_users: int
    new_users_today: int
    new_users_week: int
    new_users_month: int
    completed_registrations: int
    incomplete_registrations: int
    users_with_avatars: int

    class Config:
        from_attributes = True
