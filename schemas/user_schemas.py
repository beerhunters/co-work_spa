from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, EmailStr, field_validator, field_serializer
import re


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
    birth_date: Optional[str] = None

    @field_serializer('birth_date')
    def serialize_birth_date(self, value: Any) -> Optional[str]:
        """Convert birth_date to string if it's a number."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            # Convert number like 30.12 to string "30.12"
            return str(value)
        return value

    @field_validator('email', mode='before')
    @classmethod
    def sanitize_email(cls, v: Any) -> Any:
        """Remove spaces from email addresses before validation."""
        if isinstance(v, str):
            return v.replace(' ', '').strip()
        return v

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
    birth_date: Optional[str] = None

    @field_validator('birth_date', mode='before')
    @classmethod
    def validate_birth_date(cls, v: Any) -> Any:
        """Validate birth_date format (DD.MM or DD.MM.YYYY)."""
        if v is None or v == '':
            return v
        if isinstance(v, str):
            # Check format DD.MM or DD.MM.YYYY
            if not re.match(r'^\d{2}\.\d{2}(\.\d{4})?$', v):
                raise ValueError('Дата рождения должна быть в формате ДД.ММ или ДД.ММ.ГГГГ (например, 25.12 или 25.12.1990)')
            # Validate day, month, and optionally year
            parts = v.split('.')
            day, month = int(parts[0]), int(parts[1])
            if not (1 <= day <= 31):
                raise ValueError('День должен быть от 01 до 31')
            if not (1 <= month <= 12):
                raise ValueError('Месяц должен быть от 01 до 12')
            if len(parts) == 3:
                year = int(parts[2])
                if not (1900 <= year <= datetime.now().year):
                    raise ValueError(f'Год должен быть от 1900 до {datetime.now().year}')
            return v
        return v

    @field_validator('email', mode='before')
    @classmethod
    def sanitize_email(cls, v: Any) -> Any:
        """Remove spaces from email addresses before validation."""
        if isinstance(v, str):
            return v.replace(' ', '').strip()
        return v


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
