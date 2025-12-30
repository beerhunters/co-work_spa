from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class OfficeSubscriptionCreate(BaseModel):
    """Схема для создания подписки на офис."""
    office_1: bool = False
    office_2: bool = False
    office_4: bool = False
    office_6: bool = False

    def has_selection(self) -> bool:
        """Проверяет, выбран ли хотя бы один размер офиса."""
        return any([self.office_1, self.office_2, self.office_4, self.office_6])


class OfficeSubscriptionUpdate(BaseModel):
    """Схема для обновления подписки."""
    office_1: Optional[bool] = None
    office_2: Optional[bool] = None
    office_4: Optional[bool] = None
    office_6: Optional[bool] = None


class OfficeSubscriptionResponse(BaseModel):
    """Схема ответа с данными подписки."""
    id: int
    user_id: int
    telegram_id: int
    full_name: Optional[str] = None
    username: Optional[str] = None
    office_1: bool
    office_2: bool
    office_4: bool
    office_6: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotifySubscribersRequest(BaseModel):
    """Схема для запроса массовой рассылки подписчикам."""
    message: str = Field(..., min_length=1, max_length=1000, description="Текст сообщения")
    office_size: Optional[int] = Field(None, description="Размер офиса для фильтрации (1, 2, 4, 6). Если None - всем.")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Освободился офис на 4 человека! Успейте забронировать.",
                "office_size": 4
            }
        }
