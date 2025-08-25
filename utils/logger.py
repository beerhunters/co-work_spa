"""
Единая система логирования с управлением через .env файл
Поддерживает JSON и текстовый формат, production и development режимы
"""
import os
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import pytz

# Загружаем настройки из конфигурации
try:
    from config import LOG_LEVEL, ENVIRONMENT, LOG_FORMAT, LOG_TO_FILE, LOGS_DIR
except ImportError:
    # Fallback для случаев когда config недоступен
    from dotenv import load_dotenv
    load_dotenv()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text")
    LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Импорт после инициализации основных настроек
def _import_telegram_logger():
    """Ленивый импорт для избежания циклических зависимостей"""
    try:
        from utils.telegram_logger import setup_telegram_logging
        return setup_telegram_logging
    except ImportError:
        return None

# Глобальная переменная для отслеживания настроенных логгеров
_configured_loggers = set()


class JSONFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON формате"""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
        self.hostname = os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        self.service_name = os.getenv('SERVICE_NAME', 'coworking-api')
        
    def format(self, record):
        # Базовая информация о логе
        log_entry = {
            "@timestamp": self._format_time(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "hostname": self.hostname,
        }
        
        # Добавляем информацию о местоположении для WARNING и выше
        if record.levelno >= logging.WARNING:
            log_entry.update({
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
                "path": record.pathname
            })
        
        # Добавляем информацию об исключении если есть
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Добавляем дополнительные поля
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                              'filename', 'module', 'lineno', 'funcName', 'created', 
                              'msecs', 'relativeCreated', 'thread', 'threadName', 
                              'processName', 'process', 'getMessage', 'exc_info', 
                              'exc_text', 'stack_info']:
                    log_entry[f"extra_{key}"] = value
        
        return json.dumps(log_entry, ensure_ascii=False, default=str)
    
    def _format_time(self, timestamp: float) -> str:
        """Форматирует время в ISO формате с московской временной зоной"""
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        dt_moscow = dt.astimezone(MOSCOW_TZ)
        return dt_moscow.isoformat()


class TextFormatter(logging.Formatter):
    """Форматтер для текстового вывода с поддержкой московского времени"""
    
    def converter(self, timestamp: float) -> time.struct_time:
        """Преобразует временную метку в struct_time с учётом московского времени"""
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        dt_moscow = dt.astimezone(MOSCOW_TZ)
        return dt_moscow.timetuple()
    
    def format(self, record):
        # Добавляем информацию о местоположении для WARNING и выше
        if record.levelno >= logging.WARNING:
            record.location = f" [{record.filename}:{record.lineno}]"
            if record.levelno >= logging.ERROR:
                record.location += f" in {record.funcName}()"
        else:
            record.location = ""
        
        return super().format(record)


class UnifiedLogger:
    """Единая система логирования с поддержкой JSON и текстового формата"""
    
    def __init__(self, name: str = "app"):
        self.name = name
        self.environment = ENVIRONMENT.lower()
        self.log_level = LOG_LEVEL.upper()
        self.log_format = LOG_FORMAT.lower()
        self.log_to_file = LOG_TO_FILE
        
        # Определяем эффективный уровень логирования для production
        self.effective_log_level = self._get_effective_log_level()
        
        # Создаем логгер
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:  # Настраиваем только если еще не настроен
            self._setup_logger()
    
    def _get_effective_log_level(self) -> str:
        """Определяет эффективный уровень логирования в зависимости от среды"""
        if self.environment == "production":
            # В продакшене по умолчанию только WARNING и выше
            if self.log_level in ["DEBUG", "INFO"]:
                return "WARNING"
            return self.log_level
        else:
            # В development - используем настройки как есть
            return self.log_level
    
    def _setup_logger(self):
        """Настройка логгера с обработчиками"""
        # Устанавливаем уровень
        level = getattr(logging, self.effective_log_level)
        self.logger.setLevel(level)
        
        # Создаем форматтеры
        if self.log_format == "json":
            formatter = JSONFormatter()
            console_formatter = JSONFormatter()
        else:
            # Текстовый формат
            detailed_format = "[%(asctime)s] [%(levelname)s] [%(name)s]%(location)s %(message)s"
            simple_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
            
            formatter = TextFormatter(detailed_format, datefmt="%Y-%m-%d %H:%M:%S")
            console_formatter = TextFormatter(simple_format, datefmt="%Y-%m-%d %H:%M:%S")
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый обработчик
        if self.log_to_file:
            self._add_file_handler(formatter, level)
        
        # Telegram обработчик для критических ошибок
        self._add_telegram_handler()
    
    def _add_file_handler(self, formatter, level):
        """Добавляет файловый обработчик"""
        # Создаем директорию для логов
        LOGS_DIR.mkdir(exist_ok=True, parents=True)
        
        # Выбираем тип ротации в зависимости от среды
        log_file = LOGS_DIR / "app.log"
        
        if self.environment == "production":
            # В продакшене используем ротацию по времени
            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=30,  # Храним 30 дней
                encoding='utf-8'
            )
            file_handler.suffix = "%Y-%m-%d"
        else:
            # В development используем ротацию по размеру
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
        
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def _add_telegram_handler(self):
        """Добавляет Telegram обработчик для критических ошибок"""
        try:
            setup_telegram_logging = _import_telegram_logger()
            if setup_telegram_logging:
                telegram_handler = setup_telegram_logging(
                    min_level="ERROR",
                    rate_limit_minutes=5
                )
                if telegram_handler:
                    self.logger.addHandler(telegram_handler)
        except Exception as e:
            # Не логируем ошибку через self.logger чтобы избежать рекурсии
            print(f"Warning: Could not initialize Telegram logging: {e}")
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.debug(message, extra=extra or {}, **kwargs)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.info(message, extra=extra or {}, **kwargs)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.warning(message, extra=extra or {}, **kwargs)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.error(message, extra=extra or {}, **kwargs)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.critical(message, extra=extra or {}, **kwargs)
    
    def exception(self, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger.exception(message, extra=extra or {}, **kwargs)


# Глобальный кэш логгеров
_logger_cache: Dict[str, UnifiedLogger] = {}


def get_logger(name: str = None) -> UnifiedLogger:
    """
    Получить логгер для модуля
    
    Args:
        name: Имя логгера, если None - используется __name__ вызывающего модуля
    
    Returns:
        UnifiedLogger: Настроенный логгер
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    if name not in _logger_cache:
        _logger_cache[name] = UnifiedLogger(name)
        
        # Логируем создание только для основных модулей
        if name in ['__main__', 'main'] or 'main' in name.lower():
            logger_key = f"{name}_{LOG_LEVEL}_{ENVIRONMENT}"
            if logger_key not in _configured_loggers:
                _logger_cache[name].info(f"Logger initialized for {name} (level: {LOG_LEVEL}, env: {ENVIRONMENT})")
                _configured_loggers.add(logger_key)
    
    return _logger_cache[name]


def setup_application_logging(
    app_name: str = "Application",
    log_level: Optional[str] = None,
    environment: Optional[str] = None,
    log_format: Optional[str] = None
) -> UnifiedLogger:
    """
    Централизованная настройка логирования для приложения
    
    Args:
        app_name: Имя приложения
        log_level: Уровень логирования (переопределяет .env)
        environment: Среда выполнения (переопределяет .env)
        log_format: Формат логов (переопределяет .env)
    
    Returns:
        UnifiedLogger: Основной логгер приложения
    """
    # Переопределяем настройки если переданы
    if log_level:
        os.environ["LOG_LEVEL"] = log_level.upper()
    if environment:
        os.environ["ENVIRONMENT"] = environment.lower()
    if log_format:
        os.environ["LOG_FORMAT"] = log_format.lower()
    
    # Создаем и возвращаем главный логгер
    main_logger = get_logger(app_name)
    main_logger.info(f"{app_name} logging initialized")
    return main_logger


def log_startup_info():
    """Логирует информацию о запуске приложения"""
    logger = get_logger("startup")
    
    logger.info("=" * 50)
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Log Format: {LOG_FORMAT}")
    logger.info(f"Log to File: {LOG_TO_FILE}")
    if LOG_TO_FILE:
        logger.info(f"Logs Directory: {LOGS_DIR}")
    logger.info("=" * 50)


def update_loggers_level(new_level: str):
    """Обновить уровень всех активных логгеров"""
    try:
        # Получаем числовое значение уровня
        numeric_level = getattr(logging, new_level.upper())
        
        # Обновляем все логгеры
        for name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(name)
            logger_obj.setLevel(numeric_level)
            
            # Обновляем обработчики
            for handler in logger_obj.handlers:
                handler.setLevel(numeric_level)
        
        # Обновляем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)
            
        logger = get_logger("logger_update")
        logger.info(f"Уровень логирования изменен на {new_level} для всех логгеров")
        
    except Exception as e:
        logger = get_logger("logger_update")
        logger.error(f"Ошибка обновления уровня логгеров: {e}")
        raise


class LoggerContext:
    """Контекстный менеджер для автоматического логирования операций"""
    
    def __init__(self, logger: UnifiedLogger, operation: str = "Operation", level: str = "INFO"):
        self.logger = logger
        self.operation = operation
        self.level = level.lower()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        getattr(self.logger, self.level)(f"{self.operation} started")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type:
            self.logger.error(
                f"{self.operation} failed after {duration:.2f}s: {exc_type.__name__}: {exc_val}",
                extra={"operation": self.operation, "duration": duration, "error": str(exc_val)}
            )
        else:
            getattr(self.logger, self.level)(
                f"{self.operation} completed in {duration:.2f}s",
                extra={"operation": self.operation, "duration": duration}
            )
        
        return False  # Не подавляем исключение


def log_function_call(func_name: str = None, level: str = "DEBUG"):
    """Декоратор для логирования вызовов функций"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or func.__name__
            logger = get_logger(func.__module__)
            
            with LoggerContext(logger, f"Function {name}", level):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator