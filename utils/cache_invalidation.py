"""
Утилиты для инвалидации кэша при изменении данных
"""
from typing import List, Optional
from utils.cache_manager import cache_manager
from utils.logger import get_logger

logger = get_logger(__name__)


class CacheInvalidator:
    """Класс для инвалидации связанных кэшей при изменении данных"""
    
    @staticmethod
    async def invalidate_dashboard_cache():
        """Инвалидация всех кэшей дашборда"""
        try:
            patterns = [
                "dashboard:*",
                "bookings:stats"
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            logger.info(f"Dashboard cache invalidated: {total_deleted} keys total")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating dashboard cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_user_related_cache(user_id: Optional[int] = None):
        """Инвалидация кэшей связанных с пользователями"""
        try:
            patterns = [
                "users:*"
            ]
            
            if user_id:
                patterns.append(f"user:{user_id}:*")
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            if total_deleted > 0:
                logger.info(f"User cache invalidated: {total_deleted} keys total")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating user cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_booking_related_cache():
        """Инвалидация кэшей связанных с бронированиями"""
        try:
            patterns = [
                "bookings:*",
                "dashboard:*"  # Дашборд зависит от бронирований
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            logger.info(f"Booking cache invalidated: {total_deleted} keys total")
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating booking cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_ticket_related_cache():
        """Инвалидация кэшей связанных с тикетами"""
        try:
            patterns = [
                "tickets:*",
                "dashboard:*"  # Дашборд зависит от тикетов
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            if total_deleted > 0:
                logger.info(f"Ticket cache invalidated: {total_deleted} keys total")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating ticket cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_tariff_related_cache():
        """Инвалидация кэшей связанных с тарифами"""
        try:
            patterns = [
                "tariffs:*",
                "bookings:*",  # Бронирования зависят от тарифов
                "dashboard:*"  # Дашборд зависит от тарифов через бронирования
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            if total_deleted > 0:
                logger.info(f"Tariff cache invalidated: {total_deleted} keys total")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating tariff cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_all_cache():
        """Полная очистка всего кэша"""
        try:
            await cache_manager.clear_all()
            logger.info("All cache invalidated")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating all cache: {e}")
            return False
    
    @staticmethod
    async def invalidate_patterns(patterns: List[str]):
        """Инвалидация кэша по списку паттернов"""
        try:
            total_deleted = 0
            for pattern in patterns:
                deleted = await cache_manager.clear_pattern(pattern)
                total_deleted += deleted
                logger.debug(f"Invalidated cache pattern '{pattern}': {deleted} keys")
            
            if total_deleted > 0:
                logger.info(f"Custom patterns cache invalidated: {total_deleted} keys total")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"Error invalidating patterns {patterns}: {e}")
            return 0


# Глобальный экземпляр для удобства использования
cache_invalidator = CacheInvalidator()