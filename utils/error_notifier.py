"""
Централизованная система уведомлений об ошибках для Telegram
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import traceback

from config import FOR_LOGS, BOT_TOKEN, ENVIRONMENT, MOSCOW_TZ
from utils.bot_instance import get_bot

logger = logging.getLogger(__name__)

class ErrorNotifier:
    """Единственная точка отправки уведомлений об ошибках"""
    
    def __init__(self):
        self._sent_errors: Dict[str, datetime] = {}  # Хэш -> время отправки
        self._block_duration = 300  # 5 минут блокировка для одинаковых ошибок
        self._lock = asyncio.Lock()  # Для thread-safe операций
        
    def _is_enabled(self) -> bool:
        """Проверяет, включены ли уведомления"""
        return (
            os.getenv("TELEGRAM_LOGGING_ENABLED", "false").lower() == "true" and
            bool(FOR_LOGS) and
            bool(BOT_TOKEN)
        )
    
    def _create_error_hash(self, error_type: str, message: str, module: str, function: str) -> str:
        """Создает уникальный хэш для ошибки"""
        # Используем тип ошибки, модуль и функцию для хэширования
        # НЕ включаем точное сообщение, чтобы похожие ошибки группировались
        content = f"{error_type}:{module}:{function}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def _should_send_notification(self, error_hash: str) -> bool:
        """Проверяет, нужно ли отправлять уведомление"""
        now = datetime.now()
        
        # Если такой ошибки еще не было
        if error_hash not in self._sent_errors:
            self._sent_errors[error_hash] = now
            return True
        
        # Проверяем, прошло ли достаточно времени
        last_sent = self._sent_errors[error_hash]
        if (now - last_sent).total_seconds() > self._block_duration:
            self._sent_errors[error_hash] = now
            return True
        
        logger.debug(f"Уведомление заблокировано для хэша {error_hash}")
        return False
    
    def _format_message(self, 
                       error_type: str,
                       message: str,
                       module: str,
                       function: str,
                       line_number: int,
                       stack_trace: Optional[str] = None,
                       context: Optional[Dict[str, Any]] = None) -> str:
        """Форматирует сообщение для Telegram"""
        
        # Выбираем эмодзи и заголовок
        level_emoji = {
            "ERROR": "🔴",
            "CRITICAL": "💥", 
            "WARNING": "⚠️"
        }
        
        emoji = level_emoji.get("ERROR", "🔴")  # По умолчанию ERROR
        env_text = "🏭 PROD" if ENVIRONMENT == "production" else "🧪 DEV"
        
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message_text = f"{emoji} {env_text} ERROR\n\n"
        message_text += f"📍 <b>Модуль:</b> {module}\n"
        message_text += f"⚙️ <b>Функция:</b> {function}\n"
        message_text += f"📄 <b>Строка:</b> {line_number}\n"
        message_text += f"🕐 <b>Время:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n\n"
        
        # Определяем тип ошибки
        if error_type == "ZeroDivisionError":
            message_text += "🧮 <b>Тип:</b> Математическая ошибка\n"
            message_text += "⚠️ <b>Причина:</b> Деление на ноль\n"
        elif "TelegramNetworkError" in error_type or "ConnectionError" in error_type:
            message_text += "🌐 <b>Тип:</b> Сетевая ошибка\n"
            message_text += "🔄 <b>Статус:</b> Автоматическое переподключение\n"
        elif "bot handler" in message.lower():
            message_text += "🤖 <b>Тип:</b> Bot handler ошибка\n"
            # Извлекаем контекст из сообщения
            if "callback_query" in message:
                message_text += "📨 <b>Событие:</b> callback_query\n"
            elif "message" in message:
                message_text += "📨 <b>Событие:</b> message\n"
        elif "frontend" in message.lower():
            message_text += "🖥️ <b>Тип:</b> Frontend ошибка\n"
        else:
            message_text += f"⚡ <b>Тип:</b> {error_type}\n"
        
        # Добавляем контекст если есть
        if context:
            if "user_id" in context:
                message_text += f"👤 <b>Пользователь:</b> {context['user_id']}\n"
            if "event_type" in context:
                message_text += f"📨 <b>Событие:</b> {context['event_type']}\n"
        
        message_text += f"\n💬 <b>Сообщение:</b>\n<code>{message}</code>"
        
        # Добавляем stack trace если есть
        if stack_trace:
            if len(stack_trace) > 800:
                stack_trace = stack_trace[:800] + "... (обрезано)"
            message_text += f"\n\n📋 <b>Traceback:</b>\n<code>{stack_trace}</code>"
        
        return message_text
    
    async def send_error_notification(self,
                                    error_type: str,
                                    message: str,
                                    module: str = "unknown",
                                    function: str = "unknown", 
                                    line_number: int = 0,
                                    stack_trace: Optional[str] = None,
                                    context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Отправляет уведомление об ошибке в Telegram (ЕДИНСТВЕННАЯ точка отправки)
        """
        if not self._is_enabled():
            logger.debug("Telegram уведомления отключены")
            return False
        
        async with self._lock:
            # Создаем хэш для дедупликации
            error_hash = self._create_error_hash(error_type, message, module, function)
            
            # Проверяем, нужно ли отправлять
            if not self._should_send_notification(error_hash):
                return False
            
            try:
                bot = get_bot()
                if not bot:
                    logger.error("Не удалось получить экземпляр бота")
                    return False
                
                # Форматируем сообщение
                telegram_message = self._format_message(
                    error_type=error_type,
                    message=message,
                    module=module,
                    function=function,
                    line_number=line_number,
                    stack_trace=stack_trace,
                    context=context
                )
                
                # Ограничиваем длину
                if len(telegram_message) > 4000:
                    telegram_message = telegram_message[:4000] + "\n... (сообщение обрезано)"
                
                # Отправляем
                await bot.send_message(
                    chat_id=FOR_LOGS,
                    text=telegram_message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                
                logger.debug(f"Уведомление отправлено для хэша {error_hash}")
                return True
                
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления: {e}")
                return False

# Создаем единственный экземпляр
_error_notifier = ErrorNotifier()

def notify_error(exc_info: tuple = None, 
                message: str = None,
                context: Dict[str, Any] = None) -> None:
    """
    Публичная функция для отправки уведомлений об ошибках
    
    Args:
        exc_info: Информация об исключении из sys.exc_info()
        message: Дополнительное сообщение
        context: Контекст ошибки (user_id, event_type и т.д.)
    """
    try:
        if exc_info:
            error_type = exc_info[1].__class__.__name__
            error_message = str(exc_info[1])
            
            # Извлекаем информацию о месте ошибки
            tb = exc_info[2]
            frame = tb.tb_frame
            module_name = frame.f_globals.get('__name__', 'unknown')
            function_name = frame.f_code.co_name
            line_number = tb.tb_lineno
            
            # Получаем stack trace
            stack_trace = ''.join(traceback.format_exception(*exc_info))
            
        else:
            error_type = "MANUAL"
            error_message = message or "Неизвестная ошибка"
            module_name = "manual"
            function_name = "manual"
            line_number = 0
            stack_trace = None
        
        # Дополняем сообщение если передано
        if message and exc_info:
            error_message = f"{message}: {error_message}"
        
        # Создаем задачу для асинхронной отправки
        asyncio.create_task(_error_notifier.send_error_notification(
            error_type=error_type,
            message=error_message,
            module=module_name,
            function=function_name,
            line_number=line_number,
            stack_trace=stack_trace,
            context=context
        ))
        
    except Exception as e:
        logger.error(f"Ошибка в notify_error: {e}")

# Глобальная переменная для предотвращения дублирования запуска
_startup_notification_sent = False

async def send_startup_notification() -> bool:
    """Отправляет уведомление о запуске приложения (только один раз)"""
    global _startup_notification_sent
    
    # Если уведомление уже было отправлено, не отправляем повторно
    if _startup_notification_sent:
        logger.debug("Уведомление о запуске уже было отправлено")
        return True
    
    if not _error_notifier._is_enabled():
        return False
    
    try:
        bot = get_bot()
        if not bot:
            return False
        
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message = f"🚀 <b>ЗАПУСК ПРИЛОЖЕНИЯ</b> {env_text}\n\n"
        message += f"🕐 <b>Время:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
        message += f"📊 <b>Среда:</b> {ENVIRONMENT}\n"
        message += f"📝 <b>Уведомления:</b> включены\n"
        
        await bot.send_message(
            chat_id=FOR_LOGS,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        # Помечаем, что уведомление отправлено
        _startup_notification_sent = True
        logger.info("Уведомление о запуске отправлено")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о запуске: {e}")
        return False

async def send_shutdown_notification() -> bool:
    """Отправляет уведомление об остановке приложения"""
    if not _error_notifier._is_enabled():
        return False
    
    try:
        bot = get_bot()
        if not bot:
            return False
        
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message = f"⏹️ <b>ОСТАНОВКА ПРИЛОЖЕНИЯ</b> {env_text}\n\n"
        message += f"🕐 <b>Время:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
        message += f"📊 <b>Среда:</b> {ENVIRONMENT}\n"
        
        await bot.send_message(
            chat_id=FOR_LOGS,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об остановке: {e}")
        return False

async def send_test_notification(level: str = "TEST") -> bool:
    """Отправляет тестовое уведомление"""
    return await _error_notifier.send_error_notification(
        error_type="TEST",
        message=f"Тестовое уведомление уровня {level}",
        module="test",
        function="send_test_notification",
        line_number=1,
        context={"test": True}
    )