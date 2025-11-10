from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TrendIndicator(BaseModel):
    """Индикатор тренда для метрики."""

    value: float = Field(..., description="Процент изменения")
    direction: str = Field(..., description="Направление: 'up', 'down', 'neutral'")
    is_positive: bool = Field(..., description="Является ли изменение позитивным для бизнеса")

    class Config:
        from_attributes = True


class SparklineData(BaseModel):
    """Данные для sparkline графика (последние 7 дней)."""

    values: List[int] = Field(..., description="Значения по дням (последние 7 дней)")
    labels: List[str] = Field(..., description="Метки дней (например, ['Пн', 'Вт', ...])")

    class Config:
        from_attributes = True


class StatCard(BaseModel):
    """Карточка статистики с трендом и sparkline."""

    current_value: int = Field(..., description="Текущее значение метрики")
    previous_value: int = Field(..., description="Значение за предыдущий период")
    change_percentage: float = Field(..., description="Процент изменения")
    trend: TrendIndicator = Field(..., description="Индикатор тренда")
    label: str = Field(..., description="Название метрики")
    icon: str = Field(..., description="Название иконки для frontend")
    sparkline: Optional[SparklineData] = Field(None, description="Данные для sparkline графика")

    class Config:
        from_attributes = True


class PeriodInfo(BaseModel):
    """Информация о периоде данных."""

    start: datetime = Field(..., description="Начало периода")
    end: datetime = Field(..., description="Конец периода")
    label: str = Field(..., description="Текстовое описание периода (например, 'Ноябрь 2025')")

    class Config:
        from_attributes = True


class DashboardStatsResponse(BaseModel):
    """Основная статистика дашборда с трендами."""

    users: StatCard = Field(..., description="Статистика по пользователям")
    bookings: StatCard = Field(..., description="Статистика по бронированиям")
    tickets: StatCard = Field(..., description="Статистика по тикетам")

    # Дополнительная статистика (из старого формата)
    active_tariffs: int = Field(..., description="Количество активных тарифов")
    paid_bookings: int = Field(..., description="Оплаченные бронирования")
    total_revenue: float = Field(..., description="Общий доход")
    ticket_stats: Dict[str, int] = Field(..., description="Статистика по статусам тикетов")
    unread_notifications: int = Field(..., description="Непрочитанные уведомления")

    period: PeriodInfo = Field(..., description="Период данных")

    class Config:
        from_attributes = True


class ChartDataPoint(BaseModel):
    """Точка данных для графика."""

    label: str = Field(..., description="Метка (день/неделя/месяц)")
    users: int = Field(0, description="Регистрации пользователей")
    tickets: int = Field(0, description="Создано тикетов")
    bookings: int = Field(0, description="Создано бронирований")

    class Config:
        from_attributes = True


class ChartDataResponse(BaseModel):
    """Данные для основного графика активности."""

    labels: List[str] = Field(..., description="Метки оси X (дни месяца)")
    datasets: Dict[str, List[int]] = Field(..., description="Наборы данных для графика")
    period: Dict[str, Any] = Field(..., description="Информация о периоде")
    totals: Dict[str, int] = Field(..., description="Суммы за период")

    class Config:
        from_attributes = True


class BookingCalendarDay(BaseModel):
    """Бронирование для календаря."""

    id: int
    visit_date: str = Field(..., description="Дата визита в ISO формате")
    visit_time: Optional[str] = Field(None, description="Время визита")
    confirmed: bool
    paid: bool
    amount: float
    user_name: Optional[str]
    telegram_id: int
    tariff_name: Optional[str]

    class Config:
        from_attributes = True


class BookingsCalendarResponse(BaseModel):
    """Ответ с данными календаря бронирований."""

    bookings: List[BookingCalendarDay] = Field(..., description="Список бронирований")
    period: Dict[str, Any] = Field(..., description="Информация о периоде")

    class Config:
        from_attributes = True


class CacheInvalidateRequest(BaseModel):
    """Запрос на инвалидацию кэша."""

    pattern: str = Field(..., description="Паттерн для очистки (например, 'dashboard:*')")

    class Config:
        from_attributes = True


class RefreshStatsRequest(BaseModel):
    """Запрос на принудительное обновление статистики."""

    clear_cache: bool = Field(True, description="Очистить кэш перед обновлением")
    include_sparklines: bool = Field(True, description="Включить данные sparkline")

    class Config:
        from_attributes = True
