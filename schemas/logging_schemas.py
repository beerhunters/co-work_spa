from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


class TelegramNotificationConfig(BaseModel):
    enabled: bool = False
    chat_id: Optional[str] = None
    min_level: LogLevel = LogLevel.ERROR
    rate_limit_minutes: int = Field(default=5, ge=1, le=60)


class LoggingConfig(BaseModel):
    log_level: LogLevel
    log_format: LogFormat
    log_to_file: bool
    environment: str
    logs_directory: str
    telegram_notifications: TelegramNotificationConfig
    log_retention_days: int = Field(default=30, ge=1, le=365)
    max_log_file_size_mb: int = Field(default=10, ge=1, le=100)


class LoggingConfigUpdate(BaseModel):
    log_level: Optional[LogLevel] = None
    log_format: Optional[LogFormat] = None
    log_to_file: Optional[bool] = None
    telegram_notifications: Optional[TelegramNotificationConfig] = None
    log_retention_days: Optional[int] = Field(default=None, ge=1, le=365)
    max_log_file_size_mb: Optional[int] = Field(default=None, ge=1, le=100)
    
    @validator('telegram_notifications', pre=True)
    def validate_telegram_config(cls, v):
        if v is not None and isinstance(v, dict):
            if v.get('enabled') and not v.get('chat_id'):
                raise ValueError("chat_id обязателен при включенных уведомлениях")
        return v


class LogEntry(BaseModel):
    timestamp: datetime
    level: LogLevel
    logger: str
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line: Optional[int] = None
    extra: Optional[Dict] = None


class LogFileInfo(BaseModel):
    name: str
    path: str
    size: int
    modified: datetime
    is_current: bool = False
    
    @property
    def size_mb(self) -> float:
        return round(self.size / (1024 * 1024), 2)


class LogStatistics(BaseModel):
    total_entries: int
    levels_count: Dict[str, int]
    errors_count: int
    warnings_count: int
    period_hours: int
    
    @property
    def error_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return round((self.errors_count / self.total_entries) * 100, 2)
    
    @property
    def warning_rate(self) -> float:
        if self.total_entries == 0:
            return 0.0
        return round((self.warnings_count / self.total_entries) * 100, 2)


class TelegramTestResult(BaseModel):
    success: bool
    message: str
    sent_at: Optional[datetime] = None


class LogSearchParams(BaseModel):
    search: Optional[str] = None
    level: Optional[LogLevel] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=10000)
    
    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if v is not None and 'start_date' in values and values['start_date'] is not None:
            if v <= values['start_date']:
                raise ValueError('end_date должна быть после start_date')
        return v