from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field, validator, ConfigDict, field_serializer
from datetime import datetime


class OpenspaceRentalBase(BaseModel):
    """Базовая схема аренды опенспейса."""
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    user_id: int
    rental_type: Literal["one_day", "monthly_fixed", "monthly_floating"]
    workplace_number: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    is_active: bool
    price: float
    tariff_id: Optional[int] = None
    payment_status: Optional[Literal["pending", "paid", "overdue"]] = None
    last_payment_date: Optional[datetime] = None
    next_payment_date: Optional[datetime] = None
    admin_reminder_enabled: bool = False
    admin_reminder_days: int = 5
    tenant_reminder_enabled: bool = False
    tenant_reminder_days: int = 5
    created_at: datetime
    updated_at: Optional[datetime] = None
    deactivated_at: Optional[datetime] = None
    notes: Optional[str] = None

    @field_serializer('rental_type', 'payment_status')
    def serialize_enum(self, value: Any) -> Optional[str]:
        """Преобразует enum в строковое значение."""
        if value is None:
            return None
        if hasattr(value, 'value'):
            return value.value
        return str(value)


class OpenspaceRentalCreate(BaseModel):
    """Схема создания аренды опенспейса."""
    rental_type: Literal["one_day", "monthly_fixed", "monthly_floating"]
    workplace_number: Optional[str] = Field(None, max_length=20)
    start_date: datetime
    price: float = Field(..., gt=0)
    tariff_id: Optional[int] = None
    duration_months: Optional[int] = Field(None, ge=1, le=12)
    admin_reminder_enabled: bool = False
    admin_reminder_days: int = Field(5, ge=1, le=30)
    tenant_reminder_enabled: bool = False
    tenant_reminder_days: int = Field(5, ge=1, le=30)
    notes: Optional[str] = None

    @validator("workplace_number")
    def validate_workplace_number(cls, v, values):
        if values.get("rental_type") == "monthly_fixed" and not v:
            raise ValueError("Для фиксированного места необходимо указать номер рабочего места")
        if values.get("rental_type") != "monthly_fixed" and v:
            raise ValueError("Номер рабочего места указывается только для фиксированного типа")
        return v

    @validator("duration_months")
    def validate_duration(cls, v, values):
        rental_type = values.get("rental_type")
        if rental_type in ["monthly_fixed", "monthly_floating"] and not v:
            raise ValueError("Для месячных тарифов необходимо указать длительность")
        if rental_type == "one_day" and v:
            raise ValueError("Для однодневного тарифа длительность не указывается")
        return v


class OpenspaceRentalUpdate(BaseModel):
    """Схема обновления аренды опенспейса."""
    workplace_number: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    admin_reminder_enabled: Optional[bool] = None
    admin_reminder_days: Optional[int] = Field(None, ge=1, le=30)
    tenant_reminder_enabled: Optional[bool] = None
    tenant_reminder_days: Optional[int] = Field(None, ge=1, le=30)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class OpenspacePaymentRecord(BaseModel):
    """Схема записи платежа по аренде опенспейса."""
    amount: Optional[float] = None
    payment_date: Optional[datetime] = None
    notes: Optional[str] = None

    @validator("amount")
    def validate_amount(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Сумма платежа должна быть больше 0")
        return v


class UserOpenspaceInfo(BaseModel):
    """Информация об аренде опенспейса для модального окна пользователя."""
    model_config = ConfigDict(from_attributes=True)

    has_active_rental: bool
    active_rental: Optional[OpenspaceRentalBase] = None
    rental_history: List[OpenspaceRentalBase] = []
