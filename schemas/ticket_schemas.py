from datetime import datetime, date, time as time_type
from typing import Optional
from pydantic import BaseModel


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


class TicketCreate(BaseModel):
    user_id: int
    description: str
    photo_id: Optional[str] = None
    status: Optional[str] = "OPEN"
    comment: Optional[str] = None
