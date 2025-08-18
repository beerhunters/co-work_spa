from datetime import datetime, date, time as time_type
from typing import Optional
from pydantic import BaseModel


class PromocodeBase(BaseModel):
    id: int
    name: str
    discount: int
    usage_quantity: int
    expiration_date: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class PromocodeCreate(BaseModel):
    name: str
    discount: int
    usage_quantity: int = 0
    expiration_date: Optional[datetime] = None
    is_active: bool = True


class PromocodeUpdate(BaseModel):
    name: Optional[str] = None
    discount: Optional[int] = None
    usage_quantity: Optional[int] = None
    expiration_date: Optional[datetime] = None
    is_active: Optional[bool] = None
