"""
Pydantic схемы для email рассылок
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, EmailStr


# ===================================
# Email Campaign схемы
# ===================================


class EmailCampaignCreate(BaseModel):
    """Схема создания email кампании"""

    name: str = Field(..., min_length=1, max_length=255, description="Название кампании")
    subject: str = Field(..., min_length=1, max_length=500, description="Тема письма")
    html_content: str = Field(..., min_length=1, description="HTML контент письма")
    unlayer_design: Optional[str] = Field(None, description="JSON дизайн Unlayer")

    # Получатели
    recipient_type: str = Field(..., description="Тип получателей: 'all', 'selected', 'segment', 'custom'")
    recipient_ids: Optional[List[int]] = Field(None, description="ID пользователей для 'selected'")
    segment_type: Optional[str] = Field(None, description="Тип сегмента")
    segment_params: Optional[Dict] = Field(None, description="Параметры сегмента")
    custom_emails: Optional[List[EmailStr]] = Field(None, description="Email адреса для ручного ввода (для 'custom')")

    # A/B тестирование
    is_ab_test: bool = Field(False, description="Включен ли A/B тест")
    ab_test_percentage: Optional[int] = Field(None, ge=1, le=99, description="% для варианта A")
    ab_variant_b_subject: Optional[str] = Field(None, max_length=500, description="Альтернативная тема")
    ab_variant_b_content: Optional[str] = Field(None, description="Альтернативный контент")

    @validator('recipient_type')
    def validate_recipient_type(cls, v):
        if v not in ['all', 'selected', 'segment', 'custom']:
            raise ValueError("recipient_type должен быть 'all', 'selected', 'segment' или 'custom'")
        return v

    @validator('recipient_ids')
    def validate_recipient_ids(cls, v, values):
        if values.get('recipient_type') == 'selected' and (not v or len(v) == 0):
            raise ValueError("Для recipient_type='selected' необходимо указать recipient_ids")
        return v

    @validator('custom_emails')
    def validate_custom_emails(cls, v, values):
        if values.get('recipient_type') == 'custom' and (not v or len(v) == 0):
            raise ValueError("Для recipient_type='custom' необходимо указать custom_emails")
        return v


class EmailCampaignUpdate(BaseModel):
    """Схема обновления email кампании"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, min_length=1, max_length=500)
    html_content: Optional[str] = Field(None, min_length=1)
    unlayer_design: Optional[str] = None
    status: Optional[str] = Field(None, description="Статус: 'draft', 'scheduled', 'sending', 'sent', 'failed'")

    @validator('status')
    def validate_status(cls, v):
        if v and v not in ['draft', 'scheduled', 'sending', 'sent', 'failed']:
            raise ValueError("Некорректный статус")
        return v


class EmailCampaignResponse(BaseModel):
    """Схема ответа с данными кампании"""

    id: int
    name: str
    subject: str
    html_content: str
    unlayer_design: Optional[str]

    recipient_type: str
    recipient_ids: Optional[str]
    segment_type: Optional[str]
    segment_params: Optional[str]
    custom_emails: Optional[str]

    status: str
    scheduled_at: Optional[datetime]

    # Статистика
    total_count: int
    sent_count: int
    delivered_count: int
    opened_count: int
    clicked_count: int
    failed_count: int
    bounced_count: int

    # A/B тест
    is_ab_test: bool
    ab_test_percentage: Optional[int]
    ab_variant_b_subject: Optional[str]
    ab_variant_b_content: Optional[str]

    created_at: datetime
    sent_at: Optional[datetime]
    created_by: Optional[str]

    class Config:
        from_attributes = True


class EmailCampaignListResponse(BaseModel):
    """Схема ответа со списком кампаний"""

    id: int
    name: str
    subject: str
    status: str
    recipient_type: str
    total_count: int
    sent_count: int
    opened_count: int
    clicked_count: int
    created_at: datetime
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


# ===================================
# Email Template схемы
# ===================================


class EmailTemplateCreate(BaseModel):
    """Схема создания шаблона"""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100, description="welcome, promotion, newsletter, event, etc.")
    unlayer_design: str = Field(..., description="JSON дизайн Unlayer")
    html_content: str = Field(..., description="HTML контент")
    thumbnail_url: Optional[str] = Field(None, max_length=500)


class EmailTemplateUpdate(BaseModel):
    """Схема обновления шаблона"""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    unlayer_design: Optional[str] = None
    html_content: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """Схема ответа с данными шаблона"""

    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    thumbnail_url: Optional[str]
    unlayer_design: str
    html_content: str
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


# ===================================
# Отправка и планирование
# ===================================


class EmailSendRequest(BaseModel):
    """Запрос на отправку кампании"""

    send_now: bool = Field(True, description="Отправить сейчас или запланировать")
    scheduled_at: Optional[datetime] = Field(None, description="Время отправки (если send_now=False)")

    @validator('scheduled_at')
    def validate_scheduled_at(cls, v, values):
        if not values.get('send_now') and not v:
            raise ValueError("Необходимо указать scheduled_at для отложенной отправки")
        if v and v < datetime.now():
            raise ValueError("scheduled_at не может быть в прошлом")
        return v


class EmailTestRequest(BaseModel):
    """Запрос на тестовую отправку"""

    test_email: EmailStr = Field(..., description="Email для тестовой отправки")


# ===================================
# A/B тестирование
# ===================================


class EmailABTestCreate(BaseModel):
    """Создание A/B теста"""

    variant_a_subject: str = Field(..., max_length=500)
    variant_a_content: str = Field(...)
    variant_b_subject: str = Field(..., max_length=500)
    variant_b_content: str = Field(...)
    test_percentage: int = Field(50, ge=1, le=99, description="% для варианта A (остальное - вариант B)")


class EmailABTestResults(BaseModel):
    """Результаты A/B теста"""

    variant_a_sent: int
    variant_a_opened: int
    variant_a_clicked: int
    variant_a_open_rate: float
    variant_a_click_rate: float

    variant_b_sent: int
    variant_b_opened: int
    variant_b_clicked: int
    variant_b_open_rate: float
    variant_b_click_rate: float

    winner: Optional[str] = Field(None, description="'A', 'B' или None если результаты равные")


# ===================================
# Получатели и статистика
# ===================================


class EmailRecipientResponse(BaseModel):
    """Схема ответа с данными получателя"""

    id: int
    campaign_id: int
    user_id: int
    email: str
    full_name: Optional[str]
    status: str
    error_message: Optional[str]
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    first_click_at: Optional[datetime]
    clicks_count: int
    ab_variant: Optional[str]

    class Config:
        from_attributes = True


class EmailCampaignAnalytics(BaseModel):
    """Аналитика кампании"""

    campaign_id: int
    campaign_name: str

    # Основная статистика
    total_recipients: int
    sent: int
    delivered: int
    failed: int
    bounced: int
    opened: int
    clicked: int

    # Проценты
    delivery_rate: float  # (delivered / sent) * 100
    open_rate: float      # (opened / delivered) * 100
    click_rate: float     # (clicked / delivered) * 100
    bounce_rate: float    # (bounced / sent) * 100

    # Временная статистика
    avg_time_to_open: Optional[float] = Field(None, description="Среднее время до открытия (минуты)")
    peak_open_hour: Optional[int] = Field(None, description="Час с максимальными открытиями (0-23)")

    # Топ ссылок
    top_links: List[Dict[str, Any]] = Field(default_factory=list, description="Топ кликнутых ссылок")


# ===================================
# Трекинг
# ===================================


class EmailTrackingEvent(BaseModel):
    """Событие трекинга"""

    event_type: str = Field(..., description="open, click, bounce, unsubscribe, spam_report")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    link_url: Optional[str] = Field(None, description="URL для события 'click'")


# ===================================
# Сегменты
# ===================================


class EmailSegmentPreview(BaseModel):
    """Предпросмотр сегмента (количество получателей)"""

    segment_type: str = Field(..., description="active, new_users, vip, inactive, etc.")
    segment_params: Optional[Dict] = None
    estimated_count: int = Field(..., description="Примерное количество получателей")


# ===================================
# Списки и фильтры
# ===================================


class EmailCampaignFilters(BaseModel):
    """Фильтры для списка кампаний"""

    status: Optional[str] = Field(None, description="Фильтр по статусу")
    search: Optional[str] = Field(None, description="Поиск по названию/теме")
    date_from: Optional[datetime] = Field(None, description="Дата создания от")
    date_to: Optional[datetime] = Field(None, description="Дата создания до")
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class PaginatedEmailCampaigns(BaseModel):
    """Пагинированный список кампаний"""

    items: List[EmailCampaignListResponse]
    total: int
    limit: int
    offset: int
