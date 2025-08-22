"""
Система кэширования для приложения
Поддерживает Redis и in-memory fallback
"""
import json
import asyncio
import time
from typing import Optional, Any, Dict, Union
from datetime import datetime, timedelta
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from utils.logger import get_logger
from config import REDIS_URL, DEBUG

logger = get_logger(__name__)


class MemoryCache:
    """In-memory кэш как fallback для Redis"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Проверяем TTL
            if entry.get('expires_at') and time.time() > entry['expires_at']:
                del self._cache[key]
                return None
            
            return entry['value']
    
    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Установить значение в кэш"""
        async with self._lock:
            expires_at = time.time() + ttl if ttl > 0 else None
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            return True
    
    async def delete(self, key: str) -> bool:
        """Удалить ключ из кэша"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> bool:
        """Очистить весь кэш"""
        async with self._lock:
            self._cache.clear()
            return True
    
    async def keys(self, pattern: str = "*") -> list:
        """Получить список ключей по паттерну"""
        async with self._lock:
            if pattern == "*":
                return list(self._cache.keys())
            
            # Простая реализация паттерна
            import fnmatch
            return [key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)]


class CacheManager:
    """Менеджер кэширования с поддержкой Redis и in-memory fallback"""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._memory_cache = MemoryCache()
        self._use_redis = False
        self._connection_attempts = 0
        self._max_connection_attempts = 3
        
        # Настройки кэширования
        self.default_ttl = 300  # 5 минут
        self.dashboard_ttl = 60  # 1 минута для дашборда
        self.user_data_ttl = 600  # 10 минут для данных пользователей
        self.static_data_ttl = 1800  # 30 минут для статичных данных (тарифы и т.д.)
    
    async def initialize(self) -> bool:
        """Инициализация подключения к Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis не доступен, используется in-memory кэш")
            return False
        
        try:
            if hasattr(self, '_redis') and self._redis:
                await self._redis.close()
            
            self._redis = redis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Проверяем подключение
            await self._redis.ping()
            self._use_redis = True
            self._connection_attempts = 0
            
            logger.info("Redis подключен успешно")
            return True
            
        except Exception as e:
            self._connection_attempts += 1
            logger.warning(f"Не удалось подключиться к Redis (попытка {self._connection_attempts}): {e}")
            
            if self._connection_attempts >= self._max_connection_attempts:
                logger.warning("Превышено количество попыток подключения к Redis, переходим на in-memory кэш")
                self._use_redis = False
            
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        try:
            if self._use_redis and self._redis:
                value = await self._redis.get(key)
                if value is not None:
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value
                return None
            else:
                return await self._memory_cache.get(key)
                
        except Exception as e:
            logger.error(f"Ошибка получения из кэша {key}: {e}")
            if self._use_redis:
                # Fallback на memory cache
                return await self._memory_cache.get(key)
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Установить значение в кэш"""
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            if self._use_redis and self._redis:
                # Сериализуем значение
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value, ensure_ascii=False)
                else:
                    serialized_value = str(value)
                
                await self._redis.setex(key, ttl, serialized_value)
                
                # Дублируем в memory cache как backup
                await self._memory_cache.set(key, value, ttl)
                return True
            else:
                return await self._memory_cache.set(key, value, ttl)
                
        except Exception as e:
            logger.error(f"Ошибка записи в кэш {key}: {e}")
            # Fallback на memory cache
            return await self._memory_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Удалить ключ из кэша"""
        success = False
        
        try:
            if self._use_redis and self._redis:
                result = await self._redis.delete(key)
                success = bool(result)
            
            # Всегда удаляем из memory cache
            memory_success = await self._memory_cache.delete(key)
            
            return success or memory_success
            
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша {key}: {e}")
            return await self._memory_cache.delete(key)
    
    async def clear_pattern(self, pattern: str) -> int:
        """Удалить все ключи по паттерну"""
        deleted_count = 0
        
        try:
            if self._use_redis and self._redis:
                keys = await self._redis.keys(pattern)
                if keys:
                    deleted_count = await self._redis.delete(*keys)
            
            # Также чистим memory cache
            memory_keys = await self._memory_cache.keys(pattern)
            for key in memory_keys:
                await self._memory_cache.delete(key)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки кэша по паттерну {pattern}: {e}")
            return 0
    
    async def clear_all(self) -> bool:
        """Очистить весь кэш"""
        try:
            success = True
            
            if self._use_redis and self._redis:
                await self._redis.flushdb()
            
            await self._memory_cache.clear()
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка полной очистки кэша: {e}")
            return False
    
    def get_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Генерация ключа кэша"""
        # Создаем уникальный ключ на основе префикса и параметров
        key_parts = [prefix]
        
        # Добавляем позиционные аргументы
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[:8])
            else:
                key_parts.append(str(arg))
        
        # Добавляем именованные аргументы
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            kwargs_str = json.dumps(sorted_kwargs, sort_keys=True)
            key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
        
        return ":".join(key_parts)
    
    async def get_or_set(self, key: str, factory_func, ttl: Optional[int] = None) -> Any:
        """Получить из кэша или выполнить функцию и закэшировать результат"""
        # Пытаемся получить из кэша
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        try:
            # Выполняем функцию
            if asyncio.iscoroutinefunction(factory_func):
                value = await factory_func()
            else:
                value = factory_func()
            
            # Кэшируем результат
            await self.set(key, value, ttl)
            return value
            
        except Exception as e:
            logger.error(f"Ошибка выполнения factory_func для ключа {key}: {e}")
            raise
    
    async def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        stats = {
            "backend": "redis" if self._use_redis else "memory",
            "redis_available": REDIS_AVAILABLE,
            "redis_connected": self._use_redis,
            "connection_attempts": self._connection_attempts,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            if self._use_redis and self._redis:
                redis_info = await self._redis.info("memory")
                stats.update({
                    "redis_memory_used": redis_info.get("used_memory_human"),
                    "redis_keys": await self._redis.dbsize()
                })
            
            # Статистика memory cache
            memory_keys = await self._memory_cache.keys()
            stats["memory_cache_keys"] = len(memory_keys)
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики кэша: {e}")
            stats["error"] = str(e)
        
        return stats
    
    async def close(self):
        """Закрыть соединения"""
        try:
            if self._redis:
                await self._redis.close()
                logger.info("Redis соединение закрыто")
        except Exception as e:
            logger.error(f"Ошибка закрытия Redis соединения: {e}")


# Глобальный экземпляр менеджера кэша
cache_manager = CacheManager()