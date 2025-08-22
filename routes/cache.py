"""
API маршруты для управления кэшем
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from dependencies import verify_token
from utils.cache_manager import cache_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
async def get_cache_stats(_: str = Depends(verify_token)):
    """
    Получение статистики кэша
    
    Требует аутентификации администратора.
    """
    try:
        stats = await cache_manager.get_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики кэша: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статистику кэша: {str(e)}"
        )


@router.post("/clear")
async def clear_cache(
    pattern: Optional[str] = Query(None, description="Паттерн для очистки (например: dashboard:*)"),
    _: str = Depends(verify_token)
):
    """
    Очистка кэша
    
    Args:
        pattern: Паттерн для очистки. Если не указан, очищает весь кэш
        
    Требует аутентификации администратора.
    """
    try:
        if pattern:
            deleted_count = await cache_manager.clear_pattern(pattern)
            message = f"Удалено {deleted_count} ключей по паттерну '{pattern}'"
        else:
            await cache_manager.clear_all()
            message = "Весь кэш очищен"
        
        logger.info(f"Cache cleared: {message}")
        
        return {
            "status": "success",
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось очистить кэш: {str(e)}"
        )


@router.post("/invalidate-dashboard")
async def invalidate_dashboard_cache(_: str = Depends(verify_token)):
    """
    Инвалидация кэша дашборда
    
    Требует аутентификации администратора.
    """
    try:
        # Очищаем все ключи связанные с дашбордом
        deleted_count = await cache_manager.clear_pattern("dashboard:*")
        
        logger.info(f"Dashboard cache invalidated: {deleted_count} keys deleted")
        
        return {
            "status": "success",
            "message": f"Кэш дашборда очищен ({deleted_count} ключей)"
        }
        
    except Exception as e:
        logger.error(f"Ошибка инвалидации кэша дашборда: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось инвалидировать кэш дашборда: {str(e)}"
        )


@router.get("/health")
async def cache_health_check(_: str = Depends(verify_token)):
    """
    Проверка работоспособности системы кэширования
    
    Требует аутентификации администратора.
    """
    try:
        test_key = "health_check_test"
        test_value = {"timestamp": "test", "data": "health_check"}
        
        # Тестируем set/get
        set_result = await cache_manager.set(test_key, test_value, ttl=5)
        get_result = await cache_manager.get(test_key)
        
        # Убираем тестовые данные
        await cache_manager.delete(test_key)
        
        # Проверяем результаты
        is_healthy = (
            set_result and 
            get_result is not None and 
            get_result.get("data") == "health_check"
        )
        
        stats = await cache_manager.get_stats()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "cache_working": is_healthy,
            "backend": stats.get("backend", "unknown"),
            "redis_connected": stats.get("redis_connected", False),
            "test_results": {
                "set_success": set_result,
                "get_match": get_result is not None,
                "data_integrity": get_result.get("data") == "health_check" if get_result else False
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья кэша: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "cache_working": False
        }