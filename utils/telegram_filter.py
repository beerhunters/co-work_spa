"""
Фильтр для блокировки отправки логов в Telegram
"""

import logging

class TelegramBlockingFilter(logging.Filter):
    """
    Фильтр, который блокирует отправку логов в Telegram handlers
    Оставляет только централизованную систему notify_error
    """
    
    def filter(self, record):
        """
        Блокирует записи для Telegram handlers
        Возвращает False для блокировки, True для пропуска
        """
        # Если это наша централизованная система - пропускаем
        if hasattr(record, 'telegram_skip') or getattr(record, 'from_notify_error', False):
            return True
            
        # Для всех остальных логов НЕ отправляем в Telegram handlers
        # (они должны идти только через notify_error)
        handler_name = getattr(self, 'handler_name', '')
        if 'telegram' in handler_name.lower():
            return False
            
        return True

def block_all_telegram_logging():
    """
    Блокирует все Telegram логирование кроме централизованной системы
    """
    root_logger = logging.getLogger()
    telegram_filter = TelegramBlockingFilter()
    
    # Добавляем фильтр ко всем handlers
    for handler in root_logger.handlers:
        handler_name = handler.__class__.__name__.lower()
        if 'telegram' in handler_name:
            # Помечаем handler для фильтра
            telegram_filter.handler_name = handler_name
            handler.addFilter(telegram_filter)
    
    # Также блокируем aiogram логгеры
    for logger_name in ['aiogram', 'aiogram.dispatcher', 'aiogram.dispatcher.dispatcher']:
        aiogram_logger = logging.getLogger(logger_name)
        aiogram_logger.addFilter(telegram_filter)
        
    logger = logging.getLogger(__name__)
    logger.info("Заблокировано автоматическое Telegram логирование - используется только notify_error()")