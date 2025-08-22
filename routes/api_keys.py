"""
API маршруты для управления API ключами
"""
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Optional, List, Dict, Any
import secrets
import string
from datetime import datetime, timedelta
import random

from dependencies import verify_token
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api_keys"])

# Демонстрационное хранилище API ключей (в реальном приложении это будет БД)
api_keys_storage = []
audit_logs_storage = []

def generate_api_key() -> str:
    """Генерация безопасного API ключа"""
    alphabet = string.ascii_letters + string.digits
    return 'ak_' + ''.join(secrets.choice(alphabet) for _ in range(40))

def log_audit_event(action: str, api_key_name: str = None, user: str = "admin", success: bool = True, ip_address: str = "127.0.0.1"):
    """Логирование событий аудита"""
    audit_logs_storage.append({
        "timestamp": datetime.now().isoformat(),
        "user": user,
        "action": action,
        "api_key_name": api_key_name,
        "ip_address": ip_address,
        "success": success
    })

@router.get("")
async def get_api_keys(_: str = Depends(verify_token)):
    """
    Получение списка всех API ключей
    
    Требует аутентификации администратора.
    """
    try:
        # Если нет демонстрационных данных, создаем их
        if not api_keys_storage:
            sample_keys = [
                {
                    "id": 1,
                    "name": "Mobile App API",
                    "description": "API ключ для мобильного приложения",
                    "key": generate_api_key(),
                    "scopes": ["users:read", "bookings:read", "bookings:write"],
                    "is_active": True,
                    "expires_at": (datetime.now() + timedelta(days=365)).isoformat(),
                    "created_at": datetime.now().isoformat(),
                    "ip_whitelist": ["192.168.1.100", "10.0.0.50"],
                    "rate_limit": 1000,
                    "request_count": random.randint(100, 5000),
                    "last_used_at": (datetime.now() - timedelta(hours=2)).isoformat()
                },
                {
                    "id": 2,
                    "name": "Dashboard Analytics",
                    "description": "Ключ для получения аналитических данных",
                    "key": generate_api_key(),
                    "scopes": ["analytics:read", "users:read"],
                    "is_active": True,
                    "expires_at": (datetime.now() + timedelta(days=180)).isoformat(),
                    "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
                    "ip_whitelist": [],
                    "rate_limit": 500,
                    "request_count": random.randint(50, 1000),
                    "last_used_at": (datetime.now() - timedelta(hours=1)).isoformat()
                },
                {
                    "id": 3,
                    "name": "Webhook Integration",
                    "description": "Ключ для интеграции через webhooks",
                    "key": generate_api_key(),
                    "scopes": ["tickets:read", "tickets:write", "users:read"],
                    "is_active": False,
                    "expires_at": (datetime.now() + timedelta(days=90)).isoformat(),
                    "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
                    "ip_whitelist": ["203.0.113.0"],
                    "rate_limit": 2000,
                    "request_count": random.randint(0, 100),
                    "last_used_at": (datetime.now() - timedelta(days=5)).isoformat()
                }
            ]
            api_keys_storage.extend(sample_keys)
            
            # Логируем создание демо-ключей
            for key in sample_keys:
                log_audit_event("create_api_key", key["name"], success=True)
        
        return {
            "status": "success",
            "api_keys": api_keys_storage
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения API ключей: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить API ключи: {str(e)}"
        )

@router.post("")
async def create_api_key(
    key_data: Dict[str, Any] = Body(...),
    _: str = Depends(verify_token)
):
    """
    Создание нового API ключа
    
    Требует аутентификации администратора.
    """
    try:
        new_key = {
            "id": len(api_keys_storage) + 1,
            "name": key_data.get("name"),
            "description": key_data.get("description", ""),
            "key": generate_api_key(),
            "scopes": key_data.get("scopes", []),
            "is_active": True,
            "expires_at": key_data.get("expires_at"),
            "created_at": datetime.now().isoformat(),
            "ip_whitelist": key_data.get("ip_whitelist", []),
            "rate_limit": key_data.get("rate_limit", 1000),
            "request_count": 0,
            "last_used_at": None
        }
        
        api_keys_storage.append(new_key)
        log_audit_event("create_api_key", new_key["name"], success=True)
        
        logger.info(f"API ключ '{new_key['name']}' создан успешно")
        
        return {
            "status": "success",
            "message": "API ключ создан успешно",
            "api_key": new_key
        }
        
    except Exception as e:
        log_audit_event("create_api_key", key_data.get("name"), success=False)
        logger.error(f"Ошибка создания API ключа: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать API ключ: {str(e)}"
        )

@router.put("/{key_id}")
async def update_api_key(
    key_id: int,
    key_data: Dict[str, Any] = Body(...),
    _: str = Depends(verify_token)
):
    """
    Обновление API ключа
    
    Требует аутентификации администратора.
    """
    try:
        # Находим ключ для обновления
        key_to_update = None
        for key in api_keys_storage:
            if key["id"] == key_id:
                key_to_update = key
                break
        
        if not key_to_update:
            raise HTTPException(status_code=404, detail="API ключ не найден")
        
        # Обновляем данные
        key_to_update.update({
            "name": key_data.get("name", key_to_update["name"]),
            "description": key_data.get("description", key_to_update["description"]),
            "scopes": key_data.get("scopes", key_to_update["scopes"]),
            "expires_at": key_data.get("expires_at", key_to_update["expires_at"]),
            "ip_whitelist": key_data.get("ip_whitelist", key_to_update["ip_whitelist"]),
            "rate_limit": key_data.get("rate_limit", key_to_update["rate_limit"]),
        })
        
        log_audit_event("update_api_key", key_to_update["name"], success=True)
        
        logger.info(f"API ключ '{key_to_update['name']}' обновлен успешно")
        
        return {
            "status": "success",
            "message": "API ключ обновлен успешно",
            "api_key": key_to_update
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_audit_event("update_api_key", f"key_id_{key_id}", success=False)
        logger.error(f"Ошибка обновления API ключа {key_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось обновить API ключ: {str(e)}"
        )

@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    _: str = Depends(verify_token)
):
    """
    Удаление API ключа
    
    Требует аутентификации администратора.
    """
    try:
        # Находим и удаляем ключ
        key_to_delete = None
        for i, key in enumerate(api_keys_storage):
            if key["id"] == key_id:
                key_to_delete = api_keys_storage.pop(i)
                break
        
        if not key_to_delete:
            raise HTTPException(status_code=404, detail="API ключ не найден")
        
        log_audit_event("delete_api_key", key_to_delete["name"], success=True)
        
        logger.info(f"API ключ '{key_to_delete['name']}' удален успешно")
        
        return {
            "status": "success",
            "message": "API ключ удален успешно"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_audit_event("delete_api_key", f"key_id_{key_id}", success=False)
        logger.error(f"Ошибка удаления API ключа {key_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось удалить API ключ: {str(e)}"
        )

@router.patch("/{key_id}/toggle")
async def toggle_api_key_status(
    key_id: int,
    _: str = Depends(verify_token)
):
    """
    Переключение статуса активности API ключа
    
    Требует аутентификации администратора.
    """
    try:
        # Находим ключ для переключения статуса
        key_to_toggle = None
        for key in api_keys_storage:
            if key["id"] == key_id:
                key_to_toggle = key
                break
        
        if not key_to_toggle:
            raise HTTPException(status_code=404, detail="API ключ не найден")
        
        # Переключаем статус
        key_to_toggle["is_active"] = not key_to_toggle["is_active"]
        
        action = "activate_api_key" if key_to_toggle["is_active"] else "deactivate_api_key"
        log_audit_event(action, key_to_toggle["name"], success=True)
        
        status = "активирован" if key_to_toggle["is_active"] else "деактивирован"
        logger.info(f"API ключ '{key_to_toggle['name']}' {status}")
        
        return {
            "status": "success",
            "message": f"API ключ {status}",
            "api_key": key_to_toggle
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_audit_event("toggle_api_key", f"key_id_{key_id}", success=False)
        logger.error(f"Ошибка переключения статуса API ключа {key_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось изменить статус API ключа: {str(e)}"
        )

@router.get("/usage-stats")
async def get_usage_stats(_: str = Depends(verify_token)):
    """
    Получение статистики использования API ключей
    
    Требует аутентификации администратора.
    """
    try:
        # Генерируем демонстрационную статистику
        total_requests = sum(key.get("request_count", 0) for key in api_keys_storage)
        active_keys = [key for key in api_keys_storage if key["is_active"]]
        
        usage_stats = {
            "total_requests": total_requests,
            "total_requests_today": random.randint(100, 1000),
            "requests_trend": random.uniform(-15.0, 25.0),
            "successful_requests": int(total_requests * 0.95),
            "client_errors": int(total_requests * 0.03),
            "server_errors": int(total_requests * 0.02),
            "daily_usage": [
                {"date": f"2025-08-{16+i:02d}", "requests": random.randint(50, 300)}
                for i in range(7)
            ],
            "top_keys": [
                {
                    "name": key["name"],
                    "requests": key.get("request_count", 0),
                    "success_rate": random.randint(92, 99)
                }
                for key in sorted(api_keys_storage, key=lambda k: k.get("request_count", 0), reverse=True)[:5]
            ]
        }
        
        return {
            "status": "success",
            "usage_stats": usage_stats
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики использования: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статистику использования: {str(e)}"
        )

@router.get("/audit-logs")
async def get_audit_logs(_: str = Depends(verify_token)):
    """
    Получение журнала аудита действий с API ключами
    
    Требует аутентификации администратора.
    """
    try:
        # Если нет логов аудита, создаем демонстрационные
        if not audit_logs_storage:
            demo_logs = [
                {
                    "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                    "user": "admin",
                    "action": "create_api_key",
                    "api_key_name": "Mobile App API",
                    "ip_address": "192.168.1.100",
                    "success": True
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                    "user": "admin",
                    "action": "update_api_key",
                    "api_key_name": "Dashboard Analytics",
                    "ip_address": "192.168.1.100",
                    "success": True
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                    "user": "admin",
                    "action": "deactivate_api_key",
                    "api_key_name": "Webhook Integration",
                    "ip_address": "192.168.1.100",
                    "success": True
                },
                {
                    "timestamp": (datetime.now() - timedelta(hours=6)).isoformat(),
                    "user": "admin",
                    "action": "delete_api_key",
                    "api_key_name": "Old Test Key",
                    "ip_address": "192.168.1.100",
                    "success": False
                }
            ]
            audit_logs_storage.extend(demo_logs)
        
        # Сортируем логи по времени (новые сначала)
        sorted_logs = sorted(audit_logs_storage, 
                           key=lambda x: x["timestamp"], 
                           reverse=True)
        
        return {
            "status": "success",
            "audit_logs": sorted_logs
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения журнала аудита: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить журнал аудита: {str(e)}"
        )
