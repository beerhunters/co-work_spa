from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AdminRoleEnum(str, Enum):
    SUPER_ADMIN = "super_admin"
    MANAGER = "manager"


class PermissionEnum(str, Enum):
    # Пользователи
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    BAN_USERS = "ban_users"

    # Бронирования
    VIEW_BOOKINGS = "view_bookings"
    CREATE_BOOKINGS = "create_bookings"
    EDIT_BOOKINGS = "edit_bookings"
    DELETE_BOOKINGS = "delete_bookings"
    CONFIRM_BOOKINGS = "confirm_bookings"

    # Тарифы
    VIEW_TARIFFS = "view_tariffs"
    CREATE_TARIFFS = "create_tariffs"
    EDIT_TARIFFS = "edit_tariffs"
    DELETE_TARIFFS = "delete_tariffs"

    # Промокоды
    VIEW_PROMOCODES = "view_promocodes"
    CREATE_PROMOCODES = "create_promocodes"
    EDIT_PROMOCODES = "edit_promocodes"
    DELETE_PROMOCODES = "delete_promocodes"

    # Тикеты
    VIEW_TICKETS = "view_tickets"
    EDIT_TICKETS = "edit_tickets"
    DELETE_TICKETS = "delete_tickets"

    # Уведомления
    VIEW_NOTIFICATIONS = "view_notifications"
    MANAGE_NOTIFICATIONS = "manage_notifications"

    # Telegram рассылки
    VIEW_TELEGRAM_NEWSLETTERS = "view_telegram_newsletters"
    SEND_TELEGRAM_NEWSLETTERS = "send_telegram_newsletters"
    MANAGE_TELEGRAM_NEWSLETTERS = "manage_telegram_newsletters"

    # Email рассылки
    VIEW_EMAIL_CAMPAIGNS = "view_email_campaigns"
    CREATE_EMAIL_CAMPAIGNS = "create_email_campaigns"
    EDIT_EMAIL_CAMPAIGNS = "edit_email_campaigns"
    DELETE_EMAIL_CAMPAIGNS = "delete_email_campaigns"
    SEND_EMAIL_CAMPAIGNS = "send_email_campaigns"
    MANAGE_EMAIL_TEMPLATES = "manage_email_templates"

    # Управление администраторами
    MANAGE_ADMINS = "manage_admins"

    # Дашборд
    VIEW_DASHBOARD = "view_dashboard"

    # Логирование и мониторинг
    VIEW_LOGS = "view_logs"
    MANAGE_LOGGING = "manage_logging"
    
    # Бэкапы
    MANAGE_BACKUPS = "manage_backups"

    # Офисы
    VIEW_OFFICES = "view_offices"
    CREATE_OFFICES = "create_offices"
    EDIT_OFFICES = "edit_offices"
    DELETE_OFFICES = "delete_offices"

    # Подписки на офисы
    VIEW_OFFICE_SUBSCRIPTIONS = "view_office_subscriptions"
    MANAGE_OFFICE_SUBSCRIPTIONS = "manage_office_subscriptions"


class AdminBase(BaseModel):
    id: int
    login: str
    role: AdminRoleEnum
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None
    permissions: List[str] = []

    class Config:
        from_attributes = True


class AdminCreate(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    permissions: List[PermissionEnum] = []

    @validator("login")
    def validate_login(cls, v):
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Логин может содержать только буквы, цифры, дефисы и подчеркивания"
            )
        return v.lower()


class AdminUpdate(BaseModel):
    login: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=6)
    permissions: Optional[List[PermissionEnum]] = None
    is_active: Optional[bool] = None

    @validator("login")
    def validate_login(cls, v):
        if v and not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Логин может содержать только буквы, цифры, дефисы и подчеркивания"
            )
        return v.lower() if v else v


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class AdminResponse(BaseModel):
    id: int
    login: str
    role: AdminRoleEnum
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None
    creator_login: Optional[str] = None
    permissions: List[str] = []

    class Config:
        from_attributes = True


class AvailablePermissions(BaseModel):
    permissions: List[dict] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.permissions = [
            {
                "value": perm.value,
                "label": self._get_permission_label(perm.value),
                "category": self._get_permission_category(perm.value),
            }
            for perm in PermissionEnum
        ]

    def _get_permission_label(self, permission: str) -> str:
        labels = {
            # Пользователи
            "view_users": "Просмотр пользователей",
            "edit_users": "Редактирование пользователей",
            "delete_users": "Удаление пользователей",
            "ban_users": "Бан пользователей",
            # Бронирования
            "view_bookings": "Просмотр бронирований",
            "create_bookings": "Создание бронирований",
            "edit_bookings": "Редактирование бронирований",
            "delete_bookings": "Удаление бронирований",
            "confirm_bookings": "Подтверждение бронирований",
            # Тарифы
            "view_tariffs": "Просмотр тарифов",
            "create_tariffs": "Создание тарифов",
            "edit_tariffs": "Редактирование тарифов",
            "delete_tariffs": "Удаление тарифов",
            # Промокоды
            "view_promocodes": "Просмотр промокодов",
            "create_promocodes": "Создание промокодов",
            "edit_promocodes": "Редактирование промокодов",
            "delete_promocodes": "Удаление промокодов",
            # Тикеты
            "view_tickets": "Просмотр тикетов",
            "edit_tickets": "Редактирование тикетов",
            "delete_tickets": "Удаление тикетов",
            # Уведомления
            "view_notifications": "Просмотр уведомлений",
            "manage_notifications": "Управление уведомлениями",
            # Telegram рассылки
            "view_telegram_newsletters": "Просмотр Telegram рассылок",
            "send_telegram_newsletters": "Отправка Telegram рассылок",
            "manage_telegram_newsletters": "Управление Telegram рассылками",
            # Email рассылки
            "view_email_campaigns": "Просмотр Email рассылок",
            "create_email_campaigns": "Создание Email рассылок",
            "edit_email_campaigns": "Редактирование Email рассылок",
            "delete_email_campaigns": "Удаление Email рассылок",
            "send_email_campaigns": "Отправка Email рассылок",
            "manage_email_templates": "Управление Email шаблонами",
            # Администраторы
            "manage_admins": "Управление администраторами",
            # Дашборд
            "view_dashboard": "Просмотр дашборда",
            # Логирование
            "view_logs": "Просмотр логов",
            "manage_logging": "Управление логированием",
            # Бэкапы
            "manage_backups": "Управление бэкапами",
            # Офисы
            "view_offices": "Просмотр офисов",
            "create_offices": "Создание офисов",
            "edit_offices": "Редактирование офисов",
            "delete_offices": "Удаление офисов",
            # Подписки на офисы
            "view_office_subscriptions": "Просмотр подписок на офисы",
            "manage_office_subscriptions": "Управление подписками на офисы",
        }
        return labels.get(permission, permission)

    def _get_permission_category(self, permission: str) -> str:
        categories = {
            "view_users": "Пользователи",
            "edit_users": "Пользователи",
            "delete_users": "Пользователи",
            "ban_users": "Пользователи",
            "view_bookings": "Бронирования",
            "create_bookings": "Бронирования",
            "edit_bookings": "Бронирования",
            "delete_bookings": "Бронирования",
            "confirm_bookings": "Бронирования",
            "view_tariffs": "Тарифы",
            "create_tariffs": "Тарифы",
            "edit_tariffs": "Тарифы",
            "delete_tariffs": "Тарифы",
            "view_promocodes": "Промокоды",
            "create_promocodes": "Промокоды",
            "edit_promocodes": "Промокоды",
            "delete_promocodes": "Промокоды",
            "view_tickets": "Тикеты",
            "edit_tickets": "Тикеты",
            "delete_tickets": "Тикеты",
            "view_notifications": "Уведомления",
            "manage_notifications": "Уведомления",
            "view_telegram_newsletters": "Telegram рассылки",
            "send_telegram_newsletters": "Telegram рассылки",
            "manage_telegram_newsletters": "Telegram рассылки",
            "view_email_campaigns": "Email рассылки",
            "create_email_campaigns": "Email рассылки",
            "edit_email_campaigns": "Email рассылки",
            "delete_email_campaigns": "Email рассылки",
            "send_email_campaigns": "Email рассылки",
            "manage_email_templates": "Email рассылки",
            "manage_admins": "Администрирование",
            "view_dashboard": "Система",
            "view_logs": "Система",
            "manage_logging": "Система",
            "manage_backups": "Администрирование",
            "view_offices": "Офисы",
            "create_offices": "Офисы",
            "edit_offices": "Офисы",
            "delete_offices": "Офисы",
            "view_office_subscriptions": "Подписки на офисы",
            "manage_office_subscriptions": "Подписки на офисы",
        }
        return categories.get(permission, "Другое")
