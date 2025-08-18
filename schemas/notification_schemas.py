from datetime import datetime, date, time as time_type
from typing import Optional
from pydantic import BaseModel


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
