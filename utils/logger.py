import time
from typing import Optional
from logging import getLogger, Formatter, StreamHandler, Logger
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
import sys
from datetime import datetime
import pytz
import inspect
from pathlib import Path


class MoscowFormatter(Formatter):
    """Форматировщик логов с часовым поясом Europe/Moscow.

    Сложность: O(1) для форматирования записи.
    """

    def converter(self, timestamp: float) -> time.struct_time:
        """Преобразует временную метку в struct_time с учетом часового пояса.

        Args:
            timestamp: Временная метка в секундах.

        Returns:
            struct_time в часовом поясе Europe/Moscow.
        """
        moscow_tz = pytz.timezone("Europe/Moscow")
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        dt_moscow = dt.astimezone(moscow_tz)
        return dt_moscow.timetuple()

    def format(self, record):
        """Форматирует запись лога с информацией о файле и строке.

        Args:
            record: Запись лога.

        Returns:
            Отформатированная строка лога.

        Сложность: O(1).
        """
        record.location = f"{record.filename}:{record.lineno}"
        record.func_info = (
            f" ({record.funcName})" if record.funcName != "<module>" else ""
        )
        return super().format(record)


def get_caller_info() -> tuple:
    """Получает информацию о вызывающем коде.

    Returns:
        Кортеж (filename, line_number, function_name).

    Сложность: O(1).
    """
    frame = inspect.currentframe().f_back.f_back
    return (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)


def setup_logger(
    name: str,
    log_dir: str = "logs",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    use_timed_rotation: bool = False,
    rotation_interval: str = "midnight",
    silent_setup: bool = False,
    log_level: Optional[str] = None,
) -> Logger:
    """Настраивает логгер с ротацией и часовым поясом.

    Args:
        name: Имя логгера.
        log_dir: Директория для логов.
        max_bytes: Максимальный размер файла лога.
        backup_count: Количество резервных копий.
        use_timed_rotation: Использовать ротацию по времени.
        rotation_interval: Интервал ротации ('midnight', 'H', 'D').
        silent_setup: Не выводить информацию о настройке.
        log_level: Уровень логирования.

    Returns:
        Настроенный логгер.

    Сложность: O(1).
    """
    _configured_loggers = set()
    logger_key = f"{name}_{log_level}_{log_dir}"
    if logger_key in _configured_loggers:
        return getLogger(name)

    log_level_str = (
        os.getenv("LOG_LEVEL", "INFO").upper()
        if log_level is None
        else log_level.upper()
    )
    log_levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
    default_level = "INFO"
    log_level = log_levels.get(log_level_str, log_levels[default_level])

    logger = getLogger(name)
    logger.setLevel(log_level)
    logger.handlers.clear()

    detailed_format = "[%(asctime)s] [%(levelname)s] [%(name)s] [%(location)s%(func_info)s] %(message)s"
    simple_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    console_formatter = MoscowFormatter(simple_format, datefmt="%Y-%m-%d %H:%M:%S")
    file_formatter = MoscowFormatter(detailed_format, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    log_file_path = log_path / "app.log"

    if use_timed_rotation:
        file_handler = TimedRotatingFileHandler(
            log_file_path, when=rotation_interval, interval=1, backupCount=backup_count
        )
    else:
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=max_bytes, backupCount=backup_count
        )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    if not silent_setup:
        logger.info(
            f"Логгер настроен: {name}, уровень: {log_level_str}, файл: {log_file_path}"
        )
    _configured_loggers.add(logger_key)
    return logger


def get_logger(name: str) -> Logger:
    """Получает логгер для модуля.

    Args:
        name: Имя логгера.

    Returns:
        Настроенный логгер.

    Сложность: O(1).
    """
    return setup_logger(name, silent_setup=True)


def init_simple_logging(app_name: str = "App", log_level: str = None) -> Logger:
    """Инициализирует простое логирование.

    Args:
        app_name: Имя приложения.
        log_level: Уровень логирования.

    Returns:
        Основной логгер приложения.

    Сложность: O(1).
    """
    main_logger = setup_logger(app_name, silent_setup=True, log_level=log_level)
    main_logger.info(f"Запуск приложения {app_name}")
    return main_logger


class LoggerContext:
    """Контекстный менеджер для логирования исключений.

    Args:
        logger: Логгер.
        message: Сообщение для лога.

    Сложность: O(1).
    """

    def __init__(self, logger: Logger, message: str = "Operation failed"):
        self.logger = logger
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"{self.message}: {str(exc_val)}")
        return False
