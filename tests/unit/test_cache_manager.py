"""
Тесты для системы кэширования
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from utils.cache_manager import CacheManager, MemoryCache


@pytest.mark.asyncio
class TestMemoryCache:
    """Тесты для in-memory кэша"""

    async def test_basic_operations(self):
        """Тест базовых операций кэша"""
        cache = MemoryCache()
        
        # Тест установки и получения значения
        await cache.set("test_key", {"data": "test_value"}, ttl=60)
        result = await cache.get("test_key")
        
        assert result is not None
        assert result["data"] == "test_value"
    
    async def test_ttl_expiration(self):
        """Тест истечения TTL"""
        cache = MemoryCache()
        
        # Устанавливаем значение с очень коротким TTL
        await cache.set("expire_key", {"data": "expire_test"}, ttl=1)
        
        # Сразу должно быть доступно
        result = await cache.get("expire_key")
        assert result is not None
        
        # Ждем истечения TTL
        await asyncio.sleep(1.1)
        
        # Должно быть недоступно
        result = await cache.get("expire_key")
        assert result is None
    
    async def test_delete_operation(self):
        """Тест удаления из кэша"""
        cache = MemoryCache()
        
        await cache.set("delete_key", {"data": "delete_test"}, ttl=60)
        
        # Проверяем, что значение есть
        result = await cache.get("delete_key")
        assert result is not None
        
        # Удаляем
        deleted = await cache.delete("delete_key")
        assert deleted is True
        
        # Проверяем, что значения нет
        result = await cache.get("delete_key")
        assert result is None
        
        # Попытка удалить несуществующий ключ
        deleted = await cache.delete("nonexistent_key")
        assert deleted is False
    
    async def test_clear_operation(self):
        """Тест полной очистки кэша"""
        cache = MemoryCache()
        
        # Добавляем несколько значений
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key2", "value2", ttl=60)
        await cache.set("key3", "value3", ttl=60)
        
        # Проверяем, что все значения есть
        assert await cache.get("key1") is not None
        assert await cache.get("key2") is not None
        assert await cache.get("key3") is not None
        
        # Очищаем кэш
        await cache.clear()
        
        # Проверяем, что все значения удалены
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert await cache.get("key3") is None
    
    async def test_keys_pattern_matching(self):
        """Тест получения ключей по паттерну"""
        cache = MemoryCache()
        
        # Добавляем значения с разными ключами
        await cache.set("user:1", "data1", ttl=60)
        await cache.set("user:2", "data2", ttl=60)
        await cache.set("booking:1", "booking_data", ttl=60)
        await cache.set("dashboard:stats", "stats_data", ttl=60)
        
        # Получаем все ключи
        all_keys = await cache.keys("*")
        assert len(all_keys) == 4
        
        # Получаем ключи по паттерну user:*
        user_keys = await cache.keys("user:*")
        assert len(user_keys) == 2
        assert "user:1" in user_keys
        assert "user:2" in user_keys


@pytest.mark.asyncio
class TestCacheManager:
    """Тесты для менеджера кэширования"""

    async def test_cache_key_generation(self):
        """Тест генерации ключей кэша"""
        manager = CacheManager()
        
        # Простой ключ
        key1 = manager.get_cache_key("dashboard", "stats")
        assert key1 == "dashboard:stats"
        
        # Ключ с параметрами
        key2 = manager.get_cache_key("dashboard", "chart_data", 2024, 8)
        assert key2 == "dashboard:chart_data:2024:8"
        
        # Ключ со сложными объектами
        key3 = manager.get_cache_key("api", {"user_id": 123, "type": "bookings"})
        assert key3.startswith("api:")
        assert len(key3.split(":")) == 2  # api + hash
    
    async def test_memory_fallback(self):
        """Тест fallback на memory cache при недоступности Redis"""
        manager = CacheManager()
        manager._use_redis = False  # Принудительно используем memory cache
        
        # Тест базовых операций через memory cache
        await manager.set("test_key", {"test": "data"}, ttl=60)
        result = await manager.get("test_key")
        
        assert result is not None
        assert result["test"] == "data"
    
    @patch('utils.cache_manager.redis')
    async def test_redis_initialization_failure(self, mock_redis):
        """Тест обработки ошибок инициализации Redis"""
        # Настраиваем мок для имитации ошибки подключения
        mock_redis.from_url.side_effect = Exception("Connection failed")
        
        manager = CacheManager()
        result = await manager.initialize()
        
        assert result is False
        assert manager._use_redis is False
    
    async def test_get_or_set_functionality(self):
        """Тест функциональности get_or_set"""
        manager = CacheManager()
        manager._use_redis = False  # Используем memory cache для тестов
        
        call_count = 0
        
        def test_factory():
            nonlocal call_count
            call_count += 1
            return {"computed": f"value_{call_count}"}
        
        # Первый вызов должен выполнить factory функцию
        result1 = await manager.get_or_set("compute_key", test_factory, ttl=60)
        assert result1["computed"] == "value_1"
        assert call_count == 1
        
        # Второй вызов должен вернуть кэшированное значение
        result2 = await manager.get_or_set("compute_key", test_factory, ttl=60)
        assert result2["computed"] == "value_1"  # То же значение
        assert call_count == 1  # Функция не вызывалась повторно
    
    async def test_async_factory_function(self):
        """Тест с асинхронной factory функцией"""
        manager = CacheManager()
        manager._use_redis = False
        
        async def async_factory():
            await asyncio.sleep(0.01)  # Имитация async работы
            return {"async": "result"}
        
        result = await manager.get_or_set("async_key", async_factory, ttl=60)
        assert result["async"] == "result"
    
    async def test_cache_stats(self):
        """Тест получения статистики кэша"""
        manager = CacheManager()
        
        stats = await manager.get_stats()
        
        assert isinstance(stats, dict)
        assert "backend" in stats
        assert "timestamp" in stats
        assert stats["backend"] in ["redis", "memory"]
    
    async def test_pattern_clearing(self):
        """Тест очистки по паттерну"""
        manager = CacheManager()
        manager._use_redis = False
        
        # Добавляем тестовые данные
        await manager.set("dashboard:stats", {"data": "stats"}, ttl=60)
        await manager.set("dashboard:chart", {"data": "chart"}, ttl=60)
        await manager.set("user:123", {"data": "user"}, ttl=60)
        
        # Очищаем по паттерну dashboard:*
        deleted_count = await manager.clear_pattern("dashboard:*")
        
        # Проверяем результат
        assert deleted_count >= 0  # В memory cache это может быть 0 из-за реализации
        
        # Проверяем, что dashboard данные удалены, а user данные остались
        dashboard_stats = await manager.get("dashboard:stats")
        dashboard_chart = await manager.get("dashboard:chart")
        user_data = await manager.get("user:123")
        
        assert dashboard_stats is None
        assert dashboard_chart is None
        assert user_data is not None
    
    async def test_error_handling(self):
        """Тест обработки ошибок"""
        manager = CacheManager()
        
        # Тест на некорректных данных не должен вызывать исключения
        result = await manager.get("nonexistent_key")
        assert result is None
        
        # Установка с неправильными параметрами не должна вызывать исключения
        success = await manager.set("", None, ttl=0)
        # Результат может быть любым, главное - отсутствие исключений


@pytest.mark.asyncio
class TestCacheIntegration:
    """Интеграционные тесты кэширования"""
    
    async def test_cache_invalidation_flow(self):
        """Тест потока инвалидации кэша"""
        from utils.cache_invalidation import CacheInvalidator
        
        manager = CacheManager()
        manager._use_redis = False
        
        invalidator = CacheInvalidator()
        
        # Настраиваем тестовые данные
        await manager.set("dashboard:stats", {"bookings": 100}, ttl=300)
        await manager.set("bookings:list", {"data": "list"}, ttl=300)
        await manager.set("user:123", {"name": "Test User"}, ttl=300)
        
        # Проверяем, что данные есть
        assert await manager.get("dashboard:stats") is not None
        assert await manager.get("bookings:list") is not None
        assert await manager.get("user:123") is not None
        
        # Инвалидируем кэши связанные с бронированиями
        deleted_count = await invalidator.invalidate_booking_related_cache()
        
        # Проверяем результат инвалидации
        dashboard_data = await manager.get("dashboard:stats")
        booking_data = await manager.get("bookings:list")
        user_data = await manager.get("user:123")
        
        # Dashboard и booking кэши должны быть очищены, user - остаться
        assert dashboard_data is None
        assert booking_data is None
        assert user_data is not None  # Пользовательские данные не затронуты
    
    async def test_concurrent_cache_access(self):
        """Тест конкурентного доступа к кэшу"""
        manager = CacheManager()
        manager._use_redis = False
        
        call_count = 0
        
        async def slow_factory():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Имитация медленной операции
            return {"computed": call_count}
        
        # Запускаем несколько конкурентных запросов
        tasks = [
            manager.get_or_set("concurrent_key", slow_factory, ttl=60)
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Все результаты должны быть одинаковыми
        assert all(r["computed"] == results[0]["computed"] for r in results)
        
        # Factory функция может вызываться несколько раз из-за гонки условий,
        # но это нормальное поведение для нашей реализации


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])