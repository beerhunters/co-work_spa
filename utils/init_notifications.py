"""
Инициализация системы уведомлений
Заменяет старую систему telegram_logger
"""

import logging
from utils.simple_telegram_handler import setup_simple_telegram_logging

def init_error_notifications():
    """
    Инициализирует централизованную систему уведомлений об ошибках
    Полностью блокирует все автоматические Telegram уведомления
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Удаляем все старые Telegram handlers
        root_logger = logging.getLogger()
        handlers_to_remove = []
        
        for handler in root_logger.handlers:
            handler_class = handler.__class__.__name__.lower()
            if any(keyword in handler_class for keyword in ['telegram', 'telegramlog']):
                handlers_to_remove.append(handler)
                
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
            logger.info(f"Удален старый handler: {handler.__class__.__name__}")
        
        # Устанавливаем блокирующий фильтр для оставшихся handlers
        from utils.telegram_filter import block_all_telegram_logging
        block_all_telegram_logging()
        
        # Настраиваем новую систему (только отключение)
        setup_simple_telegram_logging(min_level="ERROR")
        logger.info("Централизованная система уведомлений настроена")
        logger.info("Все автоматические Telegram уведомления заблокированы")
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка инициализации системы уведомлений: {e}")
        return False