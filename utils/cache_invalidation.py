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
        """Инвалидация всех кэшей дашборда (P-HIGH-2: используем clear_patterns)"""
        try:
            patterns = [
                "dashboard:*",
                "bookings:stats"
            ]

            # P-HIGH-2: Используем clear_patterns для batch удаления
            # Было: 2 последовательных clear_pattern (4 round trips: 2×KEYS + 2×DELETE)
            # Стало: 1 batch operation (2 round trips: 1×all KEYS + 1×DELETE all)
            total_deleted = await cache_manager.clear_patterns(patterns)

            logger.info(f"Dashboard cache invalidated: {total_deleted} keys total (batch)")
            return total_deleted

        except Exception as e:
            logger.error(f"Error invalidating dashboard cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_user_related_cache(user_id: Optional[int] = None):
        """Инвалидация кэшей связанных с пользователями (P-HIGH-2: batch)"""
        try:
            patterns = [
                "users:*"
            ]

            if user_id:
                patterns.append(f"user:{user_id}:*")

            # P-HIGH-2: Batch operation вместо цикла
            total_deleted = await cache_manager.clear_patterns(patterns)

            if total_deleted > 0:
                logger.info(f"User cache invalidated: {total_deleted} keys total (batch)")

            return total_deleted

        except Exception as e:
            logger.error(f"Error invalidating user cache: {e}")
            return 0
    
    @staticmethod
    async def invalidate_booking_related_cache():
        """Инвалидация кэшей связанных с бронированиями (P-HIGH-2: batch)"""
        try:
            patterns = [
                "bookings:*",
                "dashboard:*"  # Дашборд зависит от бронирований
            ]

            # P-HIGH-2: Batch operation
            total_deleted = await cache_manager.clear_patterns(patterns)

            logger.info(f"Booking cache invalidated: {total_deleted} keys total (batch)")
            return total_deleted

        except Exception as e:
            logger.error(f"Error invalidating booking cache: {e}")
            return 0

    @staticmethod
    async def invalidate_ticket_related_cache():
        """Инвалидация кэшей связанных с тикетами (P-HIGH-2: batch)"""
        try:
            patterns = [
                "tickets:*",
                "dashboard:*"  # Дашборд зависит от тикетов
            ]

            # P-HIGH-2: Batch operation
            total_deleted = await cache_manager.clear_patterns(patterns)

            if total_deleted > 0:
                logger.info(f"Ticket cache invalidated: {total_deleted} keys total (batch)")

            return total_deleted

        except Exception as e:
            logger.error(f"Error invalidating ticket cache: {e}")
            return 0

    @staticmethod
    async def invalidate_tariff_related_cache():
        """Инвалидация кэшей связанных с тарифами (P-HIGH-2: batch)"""
        try:
            patterns = [
                "tariffs:*",
                "bookings:*",  # Бронирования зависят от тарифов
                "dashboard:*"  # Дашборд зависит от тарифов через бронирования
            ]

            # P-HIGH-2: Batch operation
            total_deleted = await cache_manager.clear_patterns(patterns)

            if total_deleted > 0:
                logger.info(f"Tariff cache invalidated: {total_deleted} keys total (batch)")

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
        """Инвалидация кэша по списку паттернов (P-HIGH-2: batch)"""
        try:
            # P-HIGH-2: Используем clear_patterns для batch operation
            # Было: N последовательных clear_pattern (2N round trips: N×KEYS + N×DELETE)
            # Стало: 1 batch operation (2 round trips: 1×all KEYS + 1×DELETE all)
            total_deleted = await cache_manager.clear_patterns(patterns)

            if total_deleted > 0:
                logger.info(f"Custom patterns cache invalidated: {total_deleted} keys total (batch)")

            return total_deleted

        except Exception as e:
            logger.error(f"Error invalidating patterns {patterns}: {e}")
            return 0


# Глобальный экземпляр для удобства использования
cache_invalidator = CacheInvalidator()