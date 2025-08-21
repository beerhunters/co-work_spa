"""
Модуль для валидации и очистки входных данных
"""
import re
import html
import urllib.parse
from typing import Any, Optional, List, Dict, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime, date

from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class SecurityConfig:
    """Конфигурация безопасности для валидации"""
    
    # Максимальные длины полей
    MAX_NAME_LENGTH = 100
    MAX_DESCRIPTION_LENGTH = 2000
    MAX_PHONE_LENGTH = 20
    MAX_EMAIL_LENGTH = 254
    MAX_USERNAME_LENGTH = 50
    MAX_MESSAGE_LENGTH = 5000
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Разрешенные форматы файлов
    ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.txt'}
    
    # Регулярные выражения для валидации
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
    TELEGRAM_ID_PATTERN = re.compile(r'^\d{1,15}$')
    
    # Опасные символы и паттерны
    XSS_PATTERNS = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
    ]
    
    SQL_INJECTION_PATTERNS = [
        re.compile(r'(\b(union|select|insert|update|delete|drop|create|alter)\b)', re.IGNORECASE),
        re.compile(r'(;|\-\-|/\*|\*/)', re.IGNORECASE),
        re.compile(r"('|('')|(\")|(\"\")|(%27)|(%22))", re.IGNORECASE),
    ]


def sanitize_string(
    value: Optional[str], 
    max_length: Optional[int] = None,
    allow_html: bool = False,
    strip_whitespace: bool = True
) -> Optional[str]:
    """
    Очистка строковых значений
    
    Args:
        value: Входная строка
        max_length: Максимальная длина
        allow_html: Разрешить HTML теги
        strip_whitespace: Удалить лишние пробелы
        
    Returns:
        Очищенная строка или None
    """
    if value is None:
        return None
    
    if not isinstance(value, str):
        value = str(value)
    
    # Удаляем лишние пробелы
    if strip_whitespace:
        value = value.strip()
    
    # Проверяем длину
    if max_length and len(value) > max_length:
        logger.warning(f"String too long: {len(value)} > {max_length}")
        value = value[:max_length]
    
    # HTML санитизация
    if not allow_html:
        value = html.escape(value)
    
    # Проверяем на XSS
    for pattern in SecurityConfig.XSS_PATTERNS:
        if pattern.search(value):
            logger.warning(f"Potential XSS detected in input: {value[:100]}")
            value = pattern.sub('', value)
    
    # Проверяем на SQL injection
    for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            logger.warning(f"Potential SQL injection detected in input: {value[:100]}")
            # Не удаляем, а экранируем для безопасности
            value = html.escape(value)
    
    return value


def validate_phone(phone: Optional[str]) -> Optional[str]:
    """Валидация и нормализация номера телефона"""
    if not phone:
        return None
    
    # Удаляем все кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if not SecurityConfig.PHONE_PATTERN.match(cleaned):
        raise ValueError("Invalid phone number format")
    
    return cleaned


def validate_email(email: Optional[str]) -> Optional[str]:
    """Валидация email адреса"""
    if not email:
        return None
    
    email = sanitize_string(email, SecurityConfig.MAX_EMAIL_LENGTH).lower()
    
    if not SecurityConfig.EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email format")
    
    return email


def validate_telegram_id(telegram_id: Union[int, str]) -> int:
    """Валидация Telegram ID"""
    if isinstance(telegram_id, str):
        if not telegram_id.isdigit():
            raise ValueError("Telegram ID must be numeric")
        telegram_id = int(telegram_id)
    
    if not (1 <= telegram_id <= 999999999999999):  # Максимальный ID в Telegram
        raise ValueError("Invalid Telegram ID range")
    
    return telegram_id


def validate_file_upload(
    filename: str, 
    file_size: int, 
    content_type: str,
    allowed_extensions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Валидация загружаемого файла
    
    Returns:
        Dict с результатом валидации
    """
    result = {
        "valid": True,
        "errors": [],
        "sanitized_filename": None
    }
    
    # Проверка размера
    if file_size > SecurityConfig.MAX_FILE_SIZE:
        result["valid"] = False
        result["errors"].append(f"File size {file_size} exceeds limit {SecurityConfig.MAX_FILE_SIZE}")
    
    # Проверка расширения
    if filename:
        # Санитизация имени файла
        safe_filename = sanitize_string(filename, max_length=255)
        # Удаляем опасные символы из имени файла
        safe_filename = re.sub(r'[^\w\-_\.]', '_', safe_filename)
        result["sanitized_filename"] = safe_filename
        
        file_ext = '.' + filename.split('.')[-1].lower() if '.' in filename else ''
        
        if allowed_extensions:
            if file_ext not in allowed_extensions:
                result["valid"] = False
                result["errors"].append(f"File extension {file_ext} not allowed")
        else:
            # По умолчанию разрешаем только изображения
            if file_ext not in SecurityConfig.ALLOWED_IMAGE_EXTENSIONS:
                result["valid"] = False
                result["errors"].append(f"File extension {file_ext} not in allowed list")
    
    # Проверка MIME типа
    if content_type:
        allowed_mime_types = {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'text/plain'
        }
        if content_type not in allowed_mime_types:
            result["valid"] = False
            result["errors"].append(f"MIME type {content_type} not allowed")
    
    if result["errors"]:
        logger.warning(f"File validation failed: {result['errors']}")
    
    return result


# Валидаторы для Pydantic моделей
class SecureBaseModel(BaseModel):
    """Базовая модель с встроенной безопасностью"""
    
    @validator('*', pre=True)
    def sanitize_strings(cls, v):
        """Автоматическая санитизация всех строковых полей"""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class SecureUserInput(SecureBaseModel):
    """Модель для безопасного ввода пользовательских данных"""
    
    full_name: Optional[str] = Field(None, max_length=SecurityConfig.MAX_NAME_LENGTH)
    phone: Optional[str] = Field(None, max_length=SecurityConfig.MAX_PHONE_LENGTH)
    email: Optional[str] = Field(None, max_length=SecurityConfig.MAX_EMAIL_LENGTH)
    username: Optional[str] = Field(None, max_length=SecurityConfig.MAX_USERNAME_LENGTH)
    
    @validator('phone')
    def validate_phone_format(cls, v):
        if v:
            return validate_phone(v)
        return v
    
    @validator('email')
    def validate_email_format(cls, v):
        if v:
            return validate_email(v)
        return v
    
    @validator('username')
    def validate_username_format(cls, v):
        if v and not SecurityConfig.USERNAME_PATTERN.match(v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v


class SecureMessageInput(SecureBaseModel):
    """Модель для безопасного ввода сообщений"""
    
    message: str = Field(..., max_length=SecurityConfig.MAX_MESSAGE_LENGTH)
    title: Optional[str] = Field(None, max_length=SecurityConfig.MAX_NAME_LENGTH)
    
    @validator('message')
    def validate_message_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")
        return sanitize_string(v, SecurityConfig.MAX_MESSAGE_LENGTH)


class SecureDateRange(BaseModel):
    """Модель для безопасной валидации диапазона дат"""
    
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if v and values.get('start_date'):
            if v < values['start_date']:
                raise ValueError("End date cannot be before start date")
            
            # Ограничиваем диапазон разумными пределами
            from datetime import timedelta
            max_range = timedelta(days=365 * 2)  # 2 года
            if v - values['start_date'] > max_range:
                raise ValueError("Date range too large")
        
        return v


# Функции для проверки безопасности запросов
def check_request_security(
    request_data: Dict[str, Any],
    max_params: int = 50,
    max_param_length: int = 1000
) -> Dict[str, Any]:
    """
    Проверка безопасности HTTP запроса
    
    Args:
        request_data: Данные запроса
        max_params: Максимальное количество параметров
        max_param_length: Максимальная длина значения параметра
        
    Returns:
        Dict с результатом проверки
    """
    result = {
        "secure": True,
        "warnings": [],
        "sanitized_data": {}
    }
    
    if len(request_data) > max_params:
        result["secure"] = False
        result["warnings"].append(f"Too many parameters: {len(request_data)} > {max_params}")
        return result
    
    for key, value in request_data.items():
        # Санитизация ключа
        safe_key = sanitize_string(str(key), 100)
        
        # Санитизация значения
        if isinstance(value, str):
            if len(value) > max_param_length:
                result["warnings"].append(f"Parameter {key} too long: {len(value)}")
                value = value[:max_param_length]
            
            safe_value = sanitize_string(value, max_param_length)
        else:
            safe_value = value
        
        result["sanitized_data"][safe_key] = safe_value
    
    return result


def validate_api_input(data: Any, model_class: type) -> Any:
    """
    Валидация входных данных API с помощью Pydantic модели
    
    Args:
        data: Входные данные
        model_class: Класс модели для валидации
        
    Returns:
        Валидированные данные
    """
    try:
        return model_class.parse_obj(data)
    except Exception as e:
        logger.warning(f"API input validation failed: {e}")
        raise ValueError(f"Invalid input data: {e}")


# Middleware для автоматической проверки безопасности
class SecurityValidationMiddleware:
    """Middleware для автоматической валидации безопасности запросов"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Здесь можно добавить автоматические проверки
            # Например, проверка User-Agent, размера тела запроса и т.д.
            pass
        
        await self.app(scope, receive, send)