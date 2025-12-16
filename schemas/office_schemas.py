from typing import Optional, List, Literal
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Схема для постояльца офиса
class OfficeTenantBase(BaseModel):
    id: int
    telegram_id: int
    full_name: str

    class Config:
        from_attributes = True


# Схема для настройки напоминания постояльцу
class TenantReminderSetting(BaseModel):
    user_id: int
    is_enabled: bool = True


# Базовая схема офиса (для отображения)
class OfficeBase(BaseModel):
    id: int
    office_number: str
    floor: int
    capacity: int
    price_per_month: float
    duration_months: Optional[int] = None
    rental_start_date: Optional[datetime] = None
    rental_end_date: Optional[datetime] = None
    payment_day: Optional[int] = None
    admin_reminder_enabled: bool = False
    admin_reminder_days: int = 5
    admin_reminder_type: Literal["days_before", "specific_datetime"] = "days_before"
    admin_reminder_datetime: Optional[datetime] = None
    tenant_reminder_enabled: bool = False
    tenant_reminder_days: int = 5
    tenant_reminder_type: Literal["days_before", "specific_datetime"] = "days_before"
    tenant_reminder_datetime: Optional[datetime] = None
    comment: Optional[str] = None
    payment_type: Optional[Literal["monthly", "one_time"]] = None
    last_payment_date: Optional[datetime] = None
    next_payment_date: Optional[datetime] = None
    payment_status: Optional[Literal["pending", "paid", "overdue"]] = None
    payment_notes: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    tenants: List[OfficeTenantBase] = []
    tenant_reminder_settings: List[TenantReminderSetting] = []

    class Config:
        from_attributes = True


# Схема для создания офиса
class OfficeCreate(BaseModel):
    office_number: str = Field(..., min_length=1, max_length=20)
    floor: int = Field(..., ge=0)
    capacity: int = Field(..., ge=1)
    price_per_month: float = Field(..., gt=0)
    duration_months: Optional[int] = Field(None, ge=1, le=120)
    rental_start_date: Optional[datetime] = None
    rental_end_date: Optional[datetime] = None
    payment_day: Optional[int] = Field(None, ge=1, le=31)
    admin_reminder_enabled: bool = False
    admin_reminder_days: int = Field(5, ge=1, le=30)
    admin_reminder_type: Literal["days_before", "specific_datetime"] = "days_before"
    admin_reminder_datetime: Optional[datetime] = None
    tenant_reminder_enabled: bool = False
    tenant_reminder_days: int = Field(5, ge=1, le=30)
    tenant_reminder_type: Literal["days_before", "specific_datetime"] = "days_before"
    tenant_reminder_datetime: Optional[datetime] = None
    tenant_ids: List[int] = []  # ID пользователей-постояльцев
    tenant_reminder_settings: List[TenantReminderSetting] = []
    comment: Optional[str] = None
    payment_type: Optional[Literal["monthly", "one_time"]] = "monthly"
    payment_notes: Optional[str] = None
    is_active: bool = True

    @validator("office_number")
    def validate_office_number(cls, v):
        if not v.strip():
            raise ValueError("Номер офиса не может быть пустым")
        return v.strip()

    @validator("duration_months")
    def validate_duration_months(cls, v):
        if v is not None:
            if v < 1 or v > 120:
                raise ValueError("Длительность аренды должна быть от 1 до 120 месяцев")
        return v

    @validator("rental_end_date", always=True)
    def validate_rental_end_date(cls, v, values):
        # Если указаны duration_months и rental_start_date, вычислить rental_end_date
        if "rental_start_date" in values and "duration_months" in values:
            start = values.get("rental_start_date")
            duration = values.get("duration_months")
            if start and duration:
                from dateutil.relativedelta import relativedelta

                return start + relativedelta(months=duration)
        return v


# Схема для обновления офиса
class OfficeUpdate(BaseModel):
    office_number: Optional[str] = Field(None, min_length=1, max_length=20)
    floor: Optional[int] = Field(None, ge=0)
    capacity: Optional[int] = Field(None, ge=1)
    price_per_month: Optional[float] = Field(None, gt=0)
    duration_months: Optional[int] = Field(None, ge=1, le=120)
    rental_start_date: Optional[datetime] = None
    rental_end_date: Optional[datetime] = None
    payment_day: Optional[int] = Field(None, ge=1, le=31)
    admin_reminder_enabled: Optional[bool] = None
    admin_reminder_days: Optional[int] = Field(None, ge=1, le=30)
    admin_reminder_type: Optional[Literal["days_before", "specific_datetime"]] = None
    admin_reminder_datetime: Optional[datetime] = None
    tenant_reminder_enabled: Optional[bool] = None
    tenant_reminder_days: Optional[int] = Field(None, ge=1, le=30)
    tenant_reminder_type: Optional[Literal["days_before", "specific_datetime"]] = None
    tenant_reminder_datetime: Optional[datetime] = None
    tenant_ids: Optional[List[int]] = None
    tenant_reminder_settings: Optional[List[TenantReminderSetting]] = None
    comment: Optional[str] = None
    payment_type: Optional[Literal["monthly", "one_time"]] = None
    payment_notes: Optional[str] = None
    is_active: Optional[bool] = None

    @validator("duration_months")
    def validate_duration_months(cls, v):
        if v is not None:
            if v < 1 or v > 120:
                raise ValueError("Длительность аренды должна быть от 1 до 120 месяцев")
        return v

    @validator("rental_end_date", always=True)
    def validate_rental_end_date(cls, v, values):
        # Если указаны duration_months и rental_start_date, вычислить rental_end_date
        if "rental_start_date" in values and "duration_months" in values:
            start = values.get("rental_start_date")
            duration = values.get("duration_months")
            if start and duration:
                from dateutil.relativedelta import relativedelta

                return start + relativedelta(months=duration)
        return v


# Схема для записи платежа
class OfficePaymentRecord(BaseModel):
    """Схема для записи платежа по офису."""
    amount: Optional[float] = None  # По умолчанию price_per_month
    payment_date: Optional[datetime] = None  # По умолчанию сейчас
    notes: Optional[str] = None
    update_rental_start_date: Optional[bool] = False  # Обновить дату начала аренды

    @validator("amount")
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Сумма платежа должна быть больше 0")
        return v


# Схема для статуса кнопки оплаты
class OfficePaymentButtonStatus(BaseModel):
    """Статус отображения кнопки оплаты."""
    show_button: bool
    days_until_due: Optional[int] = None
    next_payment_date: Optional[datetime] = None
    payment_status: Optional[str] = None
    can_pay_early: bool = True
