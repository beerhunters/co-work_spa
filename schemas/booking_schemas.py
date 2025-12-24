from datetime import datetime, date, time as time_type
from typing import Optional
from pydantic import BaseModel


class BookingBase(BaseModel):
    """Базовая модель бронирования."""

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
    """Модель создания бронирования."""

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
    reminder_days: Optional[int] = None  # За сколько дней до окончания напомнить


class BookingUpdate(BaseModel):
    """Модель обновления бронирования."""

    confirmed: Optional[bool] = None
    paid: Optional[bool] = None
    rubitime_id: Optional[str] = None
    payment_id: Optional[str] = None


class BookingStats(BaseModel):
    """Статистика бронирований."""

    total_bookings: int
    paid_bookings: int
    confirmed_bookings: int
    total_revenue: float
    current_month_bookings: int
    current_month_revenue: float
    top_tariffs: list

    class Config:
        from_attributes = True


class BookingDetailed(BaseModel):
    """Детальная информация о бронировании с пользователем и тарифом."""

    id: int
    user_id: int
    tariff_id: int
    visit_date: str
    visit_time: Optional[str]
    duration: Optional[int]
    promocode_id: Optional[int]
    amount: float
    payment_id: Optional[str]
    paid: bool
    rubitime_id: Optional[str]
    confirmed: bool
    created_at: str
    user: dict
    tariff: dict
    promocode: Optional[dict] = None

    class Config:
        from_attributes = True
