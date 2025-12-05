# schemas/tariff_schemas.py
from typing import Optional
from pydantic import BaseModel, Field, validator


class TariffBase(BaseModel):
    id: int
    name: str
    description: str
    price: float
    purpose: Optional[str] = None
    service_id: int = Field(default=0)  # Устанавливаем значение по умолчанию
    is_active: bool = True
    color: str = "#3182CE"

    @validator("service_id", pre=True)
    def validate_service_id(cls, v):
        """Преобразуем None в 0 для service_id"""
        return 0 if v is None else v

    class Config:
        from_attributes = True


class TariffCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=64)
    description: str = Field(..., min_length=1)
    price: float = Field(..., ge=0)
    purpose: Optional[str] = None
    service_id: Optional[int] = Field(default=0)
    is_active: bool = True
    color: str = "#3182CE"

    @validator("service_id", pre=True)
    def validate_service_id(cls, v):
        """Преобразуем None в 0 для service_id"""
        return 0 if v is None else v


class TariffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=64)
    description: Optional[str] = Field(None, min_length=1)
    price: Optional[float] = Field(None, ge=0)
    purpose: Optional[str] = None
    service_id: Optional[int] = None
    is_active: Optional[bool] = None
    color: Optional[str] = None

    @validator("service_id", pre=True)
    def validate_service_id(cls, v):
        """Преобразуем None в 0 для service_id"""
        return 0 if v is None else v
