import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
from pathlib import Path

from config import FOR_LOGS, BOT_TOKEN, ENVIRONMENT
from utils.bot_instance import get_bot

# Кэш для rate limiting
_last_sent: Dict[str, datetime] = {}
_rate_limit_cache_file = Path("telegram_log_cache.json")

logger = logging.getLogger(__name__)


class TelegramLogHandler(logging.Handler):
    """Handler для отправки критических логов в Telegram"""
    
    def __init__(self, min_level: str = "ERROR", rate_limit_minutes: int = 5):
        super().__init__()
        self.min_level = getattr(logging, min_level.upper())
        self.rate_limit_minutes = rate_limit_minutes
        self.setLevel(self.min_level)
        
        # Загружаем кэш rate limiting
        self._load_rate_limit_cache()
    
    def emit(self, record):
        """Отправляет лог-запись в Telegram"""
        try:
            if not self._should_send(record):
                return
            
            # Создаем задачу для асинхронной отправки
            asyncio.create_task(self._send_log_async(record))
            
        except Exception as e:
            logger.error(f"Ошибка в TelegramLogHandler: {e}")
    
    def _should_send(self, record) -> bool:
        """Проверяет, нужно ли отправлять данную запись"""
        # Проверяем уровень
        if record.levelno < self.min_level:
            return False
        
        # Проверяем конфигурацию
        if not _is_telegram_logging_enabled():
            return False
        
        # Rate limiting
        cache_key = f"{record.module}_{record.funcName}_{record.getMessage()[:50]}"
        
        if cache_key in _last_sent:
            time_diff = datetime.now() - _last_sent[cache_key]
            if time_diff < timedelta(minutes=self.rate_limit_minutes):
                return False
        
        _last_sent[cache_key] = datetime.now()
        self._save_rate_limit_cache()
        
        return True
    
    async def _send_log_async(self, record):
        """Асинхронная отправка лога"""
        try:
            message = self._format_message(record)
            await send_log_message(message, record.levelname)
        except Exception as e:
            logger.error(f"Ошибка отправки лога в Telegram: {e}")
    
    def _format_message(self, record) -> str:
        """Форматирует сообщение для Telegram"""
        level_emoji = {
            "ERROR": "🔴",
            "CRITICAL": "💥",
            "WARNING": "⚠️"
        }
        
        emoji = level_emoji.get(record.levelname, "📝")
        env_text = "🏭 PROD" if ENVIRONMENT == "production" else "🧪 DEV"
        
        message = f"{emoji} {env_text} [{record.levelname}]\n\n"
        message += f"📍 **Модуль**: {record.module}\n"
        message += f"⚙️ **Функция**: {record.funcName}\n"
        message += f"📄 **Строка**: {record.lineno}\n"
        message += f"🕐 **Время**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"💬 **Сообщение**:\n```\n{record.getMessage()}\n```"
        
        # Добавляем stack trace для ошибок
        if record.exc_info:
            exc_text = self.format(record)
            if len(exc_text) > 500:
                exc_text = exc_text[:500] + "... (обрезано)"
            message += f"\n\n📋 **Stack Trace**:\n```\n{exc_text}\n```"
        
        return message
    
    def _load_rate_limit_cache(self):
        """Загружает кэш rate limiting из файла"""
        try:
            if _rate_limit_cache_file.exists():
                with open(_rate_limit_cache_file, 'r') as f:
                    cache_data = json.load(f)
                    for key, timestamp_str in cache_data.items():
                        _last_sent[key] = datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша rate limiting: {e}")
    
    def _save_rate_limit_cache(self):
        """Сохраняет кэш rate limiting в файл"""
        try:
            # Очищаем старые записи (старше 24 часов)
            cutoff_time = datetime.now() - timedelta(hours=24)
            _last_sent.clear()
            for key, timestamp in list(_last_sent.items()):
                if timestamp < cutoff_time:
                    del _last_sent[key]
            
            # Сохраняем в файл
            cache_data = {
                key: timestamp.isoformat()
                for key, timestamp in _last_sent.items()
            }
            
            with open(_rate_limit_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша rate limiting: {e}")


def _is_telegram_logging_enabled() -> bool:
    """Проверяет, включено ли логирование в Telegram"""
    telegram_enabled = os.getenv("TELEGRAM_LOGGING_ENABLED", "false").lower() == "true"
    has_for_logs = bool(FOR_LOGS)
    has_bot_token = bool(BOT_TOKEN)
    
    logger.debug(f"Telegram logging check: enabled={telegram_enabled}, for_logs={has_for_logs}, bot_token={has_bot_token}")
    
    return telegram_enabled and has_for_logs and has_bot_token


async def send_log_message(message: str, level: str = "INFO") -> bool:
    """Отправляет сообщение в Telegram канал для логов"""
    if not _is_telegram_logging_enabled():
        logger.debug("Telegram логирование отключено")
        return False
    
    try:
        bot = get_bot()
        if not bot:
            logger.error("Не удалось получить экземпляр бота")
            return False
        
        # Ограничиваем длину сообщения
        if len(message) > 4000:
            message = message[:4000] + "\n... (сообщение обрезано)"
        
        await bot.send_message(
            chat_id=FOR_LOGS,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        logger.debug(f"Лог отправлен в Telegram: {level}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки лога в Telegram: {e}")
        return False


async def send_critical_alert(message: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """Отправляет критическое предупреждение в Telegram"""
    try:
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        
        alert_message = f"💥 **КРИТИЧЕСКАЯ ОШИБКА** {env_text}\n\n"
        alert_message += f"🕐 **Время**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        alert_message += f"💬 **Сообщение**:\n{message}\n"
        
        if context:
            alert_message += f"\n📋 **Контекст**:\n```json\n{json.dumps(context, indent=2, ensure_ascii=False)}\n```"
        
        return await send_log_message(alert_message, "CRITICAL")
        
    except Exception as e:
        logger.error(f"Ошибка отправки критического предупреждения: {e}")
        return False


async def send_test_notification(level: str = "TEST", admin_login: str = "admin") -> bool:
    """Отправляет тестовое уведомление с форматированием в зависимости от уровня"""
    try:
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        
        # Выбираем эмодзи и заголовок в зависимости от уровня
        level_config = {
            "TEST": {"emoji": "🧪", "title": "ТЕСТОВОЕ УВЕДОМЛЕНИЕ"},
            "DEBUG": {"emoji": "🔍", "title": "DEBUG СООБЩЕНИЕ"}, 
            "INFO": {"emoji": "ℹ️", "title": "ИНФОРМАЦИОННОЕ СООБЩЕНИЕ"},
            "WARNING": {"emoji": "⚠️", "title": "ПРЕДУПРЕЖДЕНИЕ"},
            "ERROR": {"emoji": "🔴", "title": "ОШИБКА"},
            "CRITICAL": {"emoji": "💥", "title": "КРИТИЧЕСКАЯ ОШИБКА"}
        }
        
        config = level_config.get(level, level_config["TEST"])
        
        message = f"{config['emoji']} **{config['title']}** {env_text}\n\n"
        message += f"🕐 **Время**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"👤 **Инициатор**: {admin_login}\n"
        message += f"📊 **Среда**: {ENVIRONMENT}\n"
        message += f"🔧 **Уровень**: {level}\n\n"
        
        if level == "TEST":
            message += "✅ Тестовое сообщение от системы логирования\n"
            message += "🔧 Все настройки Telegram работают корректно"
        else:
            message += f"📝 Пример {level.lower()} уведомления от системы мониторинга"
        
        return await send_log_message(message, level)
        
    except Exception as e:
        logger.error(f"Ошибка отправки тестового уведомления: {e}")
        return False


async def send_startup_notification() -> bool:
    """Отправляет уведомление о запуске приложения"""
    try:
        if not _is_telegram_logging_enabled():
            logger.warning("Telegram logging disabled - startup notification not sent")
            return False
        
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        
        # Используем московское время
        from config import MOSCOW_TZ
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message = f"🚀 **ЗАПУСК ПРИЛОЖЕНИЯ** {env_text}\n\n"
        message += f"🕐 **Время**: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
        message += f"📊 **Среда**: {ENVIRONMENT}\n"
        message += f"📝 **Логирование**: включено\n"
        
        return await send_log_message(message, "INFO")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о запуске: {e}")
        return False


async def send_shutdown_notification() -> bool:
    """Отправляет уведомление об остановке приложения"""
    try:
        if not _is_telegram_logging_enabled():
            logger.warning("Telegram logging disabled - shutdown notification not sent")
            return False
        
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        
        # Используем московское время
        from config import MOSCOW_TZ
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message = f"⏹️ **ОСТАНОВКА ПРИЛОЖЕНИЯ** {env_text}\n\n"
        message += f"🕐 **Время**: {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
        message += f"📊 **Среда**: {ENVIRONMENT}\n"
        
        return await send_log_message(message, "INFO")
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об остановке: {e}")
        return False


def setup_telegram_logging(
    min_level: str = "ERROR",
    rate_limit_minutes: int = 5
) -> Optional[TelegramLogHandler]:
    """Настраивает Telegram логирование"""
    try:
        if not _is_telegram_logging_enabled():
            logger.info("Telegram логирование не настроено или отключено")
            return None
        
        # Создаем handler
        telegram_handler = TelegramLogHandler(
            min_level=min_level,
            rate_limit_minutes=rate_limit_minutes
        )
        
        # Добавляем к root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(telegram_handler)
        
        logger.info(f"Telegram логирование настроено (min_level={min_level}, rate_limit={rate_limit_minutes}min)")
        return telegram_handler
        
    except Exception as e:
        logger.error(f"Ошибка настройки Telegram логирования: {e}")
        return None


def remove_telegram_logging():
    """Удаляет Telegram логирование"""
    try:
        root_logger = logging.getLogger()
        handlers_to_remove = [
            handler for handler in root_logger.handlers
            if isinstance(handler, TelegramLogHandler)
        ]
        
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
            
        logger.info("Telegram логирование отключено")
        
    except Exception as e:
        logger.error(f"Ошибка отключения Telegram логирования: {e}")


# Функция для обновления конфигурации в рантайме
async def update_telegram_logging_config(
    enabled: bool,
    min_level: str = "ERROR",
    rate_limit_minutes: int = 5
):
    """Обновляет конфигурацию Telegram логирования"""
    try:
        # Сначала удаляем старые handlers
        remove_telegram_logging()
        
        # Обновляем переменную окружения
        os.environ["TELEGRAM_LOGGING_ENABLED"] = "true" if enabled else "false"
        
        if enabled:
            # Настраиваем заново
            handler = setup_telegram_logging(min_level, rate_limit_minutes)
            if handler:
                logger.info("Telegram логирование обновлено и включено")
                return True
        else:
            logger.info("Telegram логирование отключено")
            return True
            
    except Exception as e:
        logger.error(f"Ошибка обновления конфигурации Telegram логирования: {e}")
        return False
        
    return False