"""
Утилита для отключения старых Telegram handlers
Новая система использует только централизованный notify_error()
"""

import logging

def setup_simple_telegram_logging(min_level: str = "ERROR"):
    """Отключает все старые Telegram handlers (новая система работает через notify_error)"""
    try:
        # Удаляем ВСЕ существующие Telegram handlers
        root_logger = logging.getLogger()
        handlers_to_remove = []
        
        for handler in root_logger.handlers:
            # Удаляем все handlers связанные с Telegram
            handler_name = handler.__class__.__name__.lower()
            if any(keyword in handler_name for keyword in ['telegram', 'telegramlog']):
                handlers_to_remove.append(handler)
        
        for handler in handlers_to_remove:
            root_logger.removeHandler(handler)
            
        logger = logging.getLogger(__name__)
        logger.info(f"Отключено {len(handlers_to_remove)} старых Telegram handlers")
        logger.info("Используется только централизованная система notify_error()")
        
        # НЕ добавляем новый handler - используем только notify_error()
        return True
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка отключения старых Telegram handlers: {e}")
        return None