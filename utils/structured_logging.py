"""
Модуль для structured logging с JSON форматом и мониторингом
"""
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import pytz

from config import LOG_LEVEL, LOGS_DIR

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

class JSONFormatter(logging.Formatter):
    """
    Форматтер для вывода логов в JSON формате
    """
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
        self.hostname = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        self.service_name = os.getenv('SERVICE_NAME', 'coworking-api')
        
    def format(self, record: logging.LogRecord) -> str:
        # Базовые поля лога
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "hostname": self.hostname,
        }
        
        # Добавляем контекстную информацию
        if hasattr(record, 'pathname'):
            log_entry["file"] = f"{record.filename}:{record.lineno}"
        
        if hasattr(record, 'funcName'):
            log_entry["function"] = record.funcName
            
        if hasattr(record, 'process'):
            log_entry["process_id"] = record.process
            
        if hasattr(record, 'thread'):
            log_entry["thread_id"] = record.thread
        
        # Добавляем exception информацию если есть
        if record.exc_info:
            log_entry["exception"] = {
                "class": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": self.formatException(record.exc_info)
            }
        
        # Добавляем extra поля из логирования
        if self.include_extra and hasattr(record, '__dict__'):
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in [
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'lineno', 'funcName', 'created',
                    'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'message', 'exc_info', 'exc_text',
                    'stack_info', 'getMessage'
                ]:
                    try:
                        # Проверяем что значение JSON-serializable
                        json.dumps(value, default=str)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)
    
    def formatTime(self, record, datefmt=None):
        """Форматирование времени в ISO формате с timezone"""
        dt = datetime.fromtimestamp(record.created, tz=MOSCOW_TZ)
        return dt.isoformat()

class StructuredLogger:
    """
    Класс для создания structured логгеров с различными конфигурациями
    """
    
    def __init__(self, name: str, level: str = None, use_json: bool = True):
        self.name = name
        self.level = level or LOG_LEVEL
        self.use_json = use_json
        self.logger = logging.getLogger(name)
        
        # Настраиваем логгер только один раз
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self):
        """Настройка логгера с handlers"""
        self.logger.setLevel(getattr(logging, self.level.upper()))
        self.logger.propagate = False
        
        # Создаем директорию для логов
        LOGS_DIR.mkdir(exist_ok=True)
        
        # JSON форматтер для файлов и structured логирования
        json_formatter = JSONFormatter(include_extra=True)
        
        # Простой форматтер для консоли в dev режиме
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if self.use_json and os.getenv('ENVIRONMENT', 'development') == 'production':
            console_handler.setFormatter(json_formatter)
        else:
            console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler - всегда JSON для парсинга
        if self.use_json:
            # Основной лог файл с ротацией по размеру
            file_handler = RotatingFileHandler(
                filename=LOGS_DIR / f"{self.name}.json",
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=10,
                encoding='utf-8'
            )
            file_handler.setFormatter(json_formatter)
            self.logger.addHandler(file_handler)
            
            # Отдельный лог для ошибок
            error_handler = RotatingFileHandler(
                filename=LOGS_DIR / f"{self.name}_errors.json",
                maxBytes=20 * 1024 * 1024,  # 20MB
                backupCount=5,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(json_formatter)
            self.logger.addHandler(error_handler)
        else:
            # Обычный текстовый лог файл
            file_handler = TimedRotatingFileHandler(
                filename=LOGS_DIR / f"{self.name}.log",
                when='midnight',
                interval=1,
                backupCount=30,
                encoding='utf-8'
            )
            file_handler.setFormatter(simple_formatter)
            self.logger.addHandler(file_handler)
    
    def get_logger(self) -> logging.Logger:
        """Возвращает настроенный logger"""
        return self.logger

class ApplicationMetrics:
    """
    Класс для сбора и трекинга метрик приложения
    """
    
    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "requests_by_endpoint": {},
            "requests_by_status": {},
            "response_times": [],
            "errors_total": 0,
            "auth_failures": 0,
            "rate_limits_exceeded": 0,
            "active_sessions": 0,
        }
        self.logger = StructuredLogger("metrics").get_logger()
    
    def increment_counter(self, metric: str, labels: Dict[str, str] = None, value: int = 1):
        """Увеличить счетчик метрики"""
        if labels:
            key = f"{metric}_{hash(frozenset(labels.items()))}"
            self.metrics[key] = self.metrics.get(key, 0) + value
        else:
            self.metrics[metric] = self.metrics.get(metric, 0) + value
        
        # Логируем важные метрики
        if metric in ["errors_total", "auth_failures", "rate_limits_exceeded"]:
            self.logger.info(
                f"Metric incremented: {metric}",
                extra={
                    "metric_name": metric,
                    "metric_value": self.metrics.get(metric, 0),
                    "labels": labels,
                    "increment": value
                }
            )
    
    def record_histogram(self, metric: str, value: float, labels: Dict[str, str] = None):
        """Записать значение для гистограммы"""
        key = f"{metric}_histogram"
        if key not in self.metrics:
            self.metrics[key] = []
        
        self.metrics[key].append({
            "value": value,
            "timestamp": time.time(),
            "labels": labels
        })
        
        # Ограничиваем размер истории
        if len(self.metrics[key]) > 1000:
            self.metrics[key] = self.metrics[key][-500:]  # Оставляем последние 500
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получить текущие метрики"""
        return {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "metrics": self.metrics.copy()
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Получить сводку метрик"""
        summary = {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "counters": {},
            "histograms": {}
        }
        
        for key, value in self.metrics.items():
            if isinstance(value, list):
                # Это гистограмма
                if value:
                    values = [item["value"] for item in value[-100:]]  # Последние 100 значений
                    summary["histograms"][key] = {
                        "count": len(values),
                        "mean": sum(values) / len(values) if values else 0,
                        "min": min(values) if values else 0,
                        "max": max(values) if values else 0,
                        "p95": sorted(values)[int(len(values) * 0.95)] if values else 0
                    }
            else:
                # Это счетчик
                summary["counters"][key] = value
        
        return summary

# Глобальные экземпляры
_metrics = ApplicationMetrics()
_loggers = {}

def get_structured_logger(name: str, use_json: bool = True) -> logging.Logger:
    """
    Получить structured logger
    
    Args:
        name: Имя логгера
        use_json: Использовать JSON формат
        
    Returns:
        Настроенный logger
    """
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, use_json=use_json)
    return _loggers[name].get_logger()

def get_metrics() -> ApplicationMetrics:
    """Получить глобальный экземпляр метрик"""
    return _metrics

def log_request_metrics(method: str, path: str, status_code: int, duration: float, client_ip: str = None):
    """
    Логирование метрик HTTP запросов
    
    Args:
        method: HTTP метод
        path: Путь запроса
        status_code: Статус код ответа
        duration: Время выполнения в секундах
        client_ip: IP адрес клиента
    """
    metrics = get_metrics()
    logger = get_structured_logger("requests")
    
    # Увеличиваем счетчики
    metrics.increment_counter("requests_total")
    metrics.increment_counter("requests_by_endpoint", {"method": method, "path": path})
    metrics.increment_counter("requests_by_status", {"status_code": str(status_code)})
    
    # Записываем время ответа
    metrics.record_histogram("response_time", duration, {"endpoint": f"{method} {path}"})
    
    # Считаем ошибки
    if status_code >= 400:
        metrics.increment_counter("errors_total")
        if status_code == 401:
            metrics.increment_counter("auth_failures")
        elif status_code == 429:
            metrics.increment_counter("rate_limits_exceeded")
    
    # Логируем запрос с контекстом
    log_level = logging.WARNING if status_code >= 400 else logging.INFO
    logger.log(
        log_level,
        f"HTTP {method} {path} -> {status_code}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "response_time_ms": round(duration * 1000, 2),
            "client_ip": client_ip,
            "user_agent": None,  # Можно добавить если нужно
        }
    )

def log_application_event(event_type: str, message: str, **kwargs):
    """
    Логирование событий приложения
    
    Args:
        event_type: Тип события (auth, database, api, etc.)
        message: Сообщение события
        **kwargs: Дополнительные поля для логирования
    """
    logger = get_structured_logger("application")
    
    logger.info(
        message,
        extra={
            "event_type": event_type,
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            **kwargs
        }
    )

# Функция для обратной совместимости
def get_logger(name: str) -> logging.Logger:
    """Получить logger (обратная совместимость)"""
    return get_structured_logger(name, use_json=True)