from datetime import datetime, date, time as time_type
from typing import Optional
from pydantic import BaseModel


class NewsletterResponse(BaseModel):
    id: int
    message: str
    status: str
    total_count: int
    success_count: int
    photo_count: int
    created_at: datetime
