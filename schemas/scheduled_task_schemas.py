"""
Pydantic схемы для запланированных задач (Scheduled Tasks).
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ScheduledTaskResponse(BaseModel):
    """Схема ответа с данными запланированной задачи."""
    id: int
    task_type: str
    celery_task_id: Optional[str] = None

    # Связи
    office_id: Optional[int] = None
    booking_id: Optional[int] = None

    # Планирование
    scheduled_datetime: datetime
    created_at: datetime
    created_by: str

    # Выполнение
    status: str
    executed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    # Метаданные
    params: Optional[Dict[str, Any]] = None
    retry_count: int

    # Вычисляемые поля
    is_overdue: bool = False
    time_until_execution_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class ScheduledTaskCreate(BaseModel):
    """Схема для создания задачи вручную (через админ-панель)."""
    task_type: str = Field(..., description="Тип задачи")
    scheduled_datetime: datetime = Field(..., description="Когда выполнить")
    office_id: Optional[int] = Field(None, description="ID офиса (для офисных задач)")
    booking_id: Optional[int] = Field(None, description="ID бронирования (для задач бронирований)")
    params: Optional[Dict[str, Any]] = Field(None, description="Дополнительные параметры")


class ScheduledTaskUpdate(BaseModel):
    """Схема для обновления задачи."""
    scheduled_datetime: Optional[datetime] = None
    status: Optional[str] = None
    params: Optional[Dict[str, Any]] = None


class ScheduledTaskStats(BaseModel):
    """Статистика по задачам."""
    total: int
    pending: int
    running: int
    completed: int
    failed: int
    cancelled: int
    overdue: int

    # По типам
    office_reminders: int
    booking_tasks: int


class TaskFilterParams(BaseModel):
    """Параметры фильтрации задач."""
    task_type: Optional[str] = None
    status: Optional[str] = None
    office_id: Optional[int] = None
    booking_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
