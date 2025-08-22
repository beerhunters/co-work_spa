"""
Модуль для кэширования часто используемых данных
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional, Callable, List
from functools import wraps
from datetime import datetime, timedelta

from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryCache:
    """Простой in-memory кэш с TTL поддержкой"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_times: Dict[str, float] = {}
        self.max_size = 1000  # Максимальное количество ключей

    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if key not in self._cache:
            return None

        cache_entry = self._cache[key]
        current_time = time.time()

        # Проверяем TTL
        if current_time > cache_entry["expires_at"]:
            self.delete(key)
            return None

        # Обновляем время последнего доступа
        self._access_times[key] = current_time
        return cache_entry["data"]

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Установка значения в кэш с TTL"""
        current_time = time.time()
        expires_at = current_time + ttl_seconds

        # Проверяем размер кэша
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()

        self._cache[key] = {
            "data": value,
            "expires_at": expires_at,
            "created_at": current_time,
        }
        self._access_times[key] = current_time

        logger.debug(f"Cache set: {key}, TTL: {ttl_seconds}s")

    def delete(self, key: str) -> bool:
        """Удаление ключа из кэша"""
        if key in self._cache:
            del self._cache[key]
            del self._access_times[key]
            logger.debug(f"Cache deleted: {key}")
            return True
        return False

    def clear(self) -> None:
        """Очистка всего кэша"""
        self._cache.clear()
        self._access_times.clear()
        logger.info("Cache cleared")

    def _evict_lru(self) -> None:
        """Удаление наименее недавно использованного элемента"""
        if not self._access_times:
            return

        # Находим ключ с наименьшим временем доступа
        lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        self.delete(lru_key)
        logger.debug(f"LRU evicted: {lru_key}")

    def stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        current_time = time.time()
        expired_count = 0

        for key, cache_entry in self._cache.items():
            if current_time > cache_entry["expires_at"]:
                expired_count += 1

        return {
            "total_keys": len(self._cache),
            "expired_keys": expired_count,
            "max_size": self.max_size,
            "hit_ratio": None,  # Можно добавить счетчики hit/miss для расчета
        }


# Глобальный экземпляр кэша
_cache = MemoryCache()


def cache_result(key_prefix: str = "", ttl_seconds: int = 300):
    """
    Декоратор для кэширования результатов функций

    Args:
        key_prefix: Префикс для ключа кэша
        ttl_seconds: Время жизни кэша в секундах
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Генерируем ключ кэша на основе имени функции и аргументов
            cache_key = _generate_cache_key(key_prefix or func.__name__, args, kwargs)

            # Проверяем кэш
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # Выполняем функцию и кэшируем результат
            result = await func(*args, **kwargs)
            _cache.set(cache_key, result, ttl_seconds)
            logger.debug(f"Cache miss, stored: {cache_key}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = _generate_cache_key(key_prefix or func.__name__, args, kwargs)

            # Проверяем кэш
            cached_result = _cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # Выполняем функцию и кэшируем результат
            result = func(*args, **kwargs)
            _cache.set(cache_key, result, ttl_seconds)
            logger.debug(f"Cache miss, stored: {cache_key}")

            return result

        # Возвращаем правильную обертку в зависимости от типа функции
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _generate_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Генерация ключа кэша на основе аргументов функции"""
    try:
        # Создаем строку из аргументов для ключа кэша
        key_parts = [prefix]

        # Добавляем позиционные аргументы
        for arg in args:
            if hasattr(arg, "__dict__"):  # Объекты с атрибутами
                key_parts.append(str(type(arg).__name__))
            else:
                key_parts.append(str(arg))

        # Добавляем именованные аргументы
        for key, value in sorted(kwargs.items()):
            if hasattr(value, "__dict__"):
                key_parts.append(f"{key}={type(value).__name__}")
            else:
                key_parts.append(f"{key}={value}")

        cache_key = ":".join(key_parts)
        # Ограничиваем длину ключа
        if len(cache_key) > 200:
            cache_key = cache_key[:180] + "..." + str(hash(cache_key))[-10:]

        return cache_key
    except Exception as e:
        logger.warning(f"Failed to generate cache key: {e}")
        return f"{prefix}:fallback:{time.time()}"


# Публичные функции для работы с кэшем
def get_cache_stats() -> Dict[str, Any]:
    """Получение статистики кэша"""
    return _cache.stats()


def clear_cache(pattern: Optional[str] = None) -> int:
    """
    Очистка кэша

    Args:
        pattern: Паттерн для частичной очистки (если None - очищается весь кэш)

    Returns:
        Количество удаленных ключей
    """
    if pattern is None:
        count = len(_cache._cache)
        _cache.clear()
        return count

    # Частичная очистка по паттерну
    keys_to_delete = [key for key in _cache._cache.keys() if pattern in key]
    for key in keys_to_delete:
        _cache.delete(key)

    logger.info(f"Cache cleared for pattern '{pattern}': {len(keys_to_delete)} keys")
    return len(keys_to_delete)


def invalidate_cache_key(key: str) -> bool:
    """Инвалидация конкретного ключа кэша"""
    return _cache.delete(key)


# Предустановленные кэширующие декораторы для часто используемых данных
def cache_tariffs(ttl_seconds: int = 600):  # 10 минут
    """Кэширование тарифов"""
    return cache_result("tariffs", ttl_seconds)


def cache_promocodes(ttl_seconds: int = 300):  # 5 минут
    """Кэширование промокодов"""
    return cache_result("promocodes", ttl_seconds)


def cache_user_data(ttl_seconds: int = 180):  # 3 минуты
    """Кэширование данных пользователей"""
    return cache_result("users", ttl_seconds)


def cache_dashboard_stats(ttl_seconds: int = 120):  # 2 минуты
    """Кэширование статистики dashboard"""
    return cache_result("dashboard", ttl_seconds)


def cache_booking_data(ttl_seconds: int = 60):  # 1 минута
    """Кэширование данных бронирований"""
    return cache_result("bookings", ttl_seconds)
