"""
API для управления API ключами
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dependencies import verify_token
from utils.api_keys import (
    APIKeyScope, generate_api_key, revoke_api_key, 
    list_api_keys, verify_api_key_admin
)
from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class APIKeyCreateRequest(BaseModel):
    """Запрос на создание API ключа"""
    name: str = Field(..., min_length=1, max_length=100, description="Название ключа")
    scopes: List[str] = Field(..., min_items=1, description="Области доступа")
    expires_in_days: Optional[int] = Field(None, gt=0, le=3650, description="Срок действия в днях")
    allowed_ips: Optional[List[str]] = Field(None, description="Разрешенные IP адреса")
    max_requests_per_hour: int = Field(1000, gt=0, le=10000, description="Лимит запросов в час")


class APIKeyResponse(BaseModel):
    """Информация о созданном API ключе"""
    key_id: str
    key: str  # Показывается только при создании!
    name: str
    scopes: List[str]
    expires_at: Optional[str]
    max_requests_per_hour: int


class APIKeyInfo(BaseModel):
    """Информация об API ключе без самого ключа"""
    id: int
    name: str
    scopes: List[str]
    is_active: bool
    created_by: str
    created_at: str
    last_used: Optional[str]
    usage_count: int
    expires_at: Optional[str]


@router.post("/", response_model=APIKeyResponse)
async def create_api_key(
    request: APIKeyCreateRequest,
    current_admin: str = Depends(verify_token)
):
    """
    Создание нового API ключа
    
    **Важно:** Ключ показывается только один раз при создании!
    """
    try:
        # Валидируем области доступа
        valid_scopes = set(scope.value for scope in APIKeyScope)
        invalid_scopes = [scope for scope in request.scopes if scope not in valid_scopes]
        
        if invalid_scopes:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid scopes: {invalid_scopes}. Valid scopes: {list(valid_scopes)}"
            )
        
        # Преобразуем строки в enum
        scopes = [APIKeyScope(scope) for scope in request.scopes]
        
        # Генерируем ключ
        result = generate_api_key(
            name=request.name,
            scopes=scopes,
            created_by=current_admin.login,
            expires_in_days=request.expires_in_days,
            allowed_ips=request.allowed_ips,
            max_requests_per_hour=request.max_requests_per_hour
        )
        
        expires_at = None
        if request.expires_in_days:
            from datetime import timedelta
            expires_at = (datetime.utcnow() + timedelta(days=request.expires_in_days)).isoformat()
        
        logger.info(
            f"API key created: {request.name}",
            extra={
                "key_id": result["key_id"],
                "scopes": request.scopes,
                "created_by": current_admin.login
            }
        )
        
        return APIKeyResponse(
            key_id=result["key_id"],
            key=result["key"],
            name=request.name,
            scopes=request.scopes,
            expires_at=expires_at,
            max_requests_per_hour=request.max_requests_per_hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create API key")


@router.get("/", response_model=List[APIKeyInfo])
async def list_api_keys_endpoint(
    include_inactive: bool = Query(False, description="Включить неактивные ключи"),
    _: str = Depends(verify_token)
):
    """Получение списка всех API ключей"""
    try:
        keys = list_api_keys(include_inactive=include_inactive)
        return [APIKeyInfo(**key) for key in keys]
    except Exception as e:
        logger.error(f"Error listing API keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list API keys")


@router.delete("/{key_id}")
async def revoke_api_key_endpoint(
    key_id: int,
    current_admin: str = Depends(verify_token)
):
    """Отзыв API ключа"""
    try:
        success = revoke_api_key(key_id, current_admin.login)
        
        if not success:
            raise HTTPException(status_code=404, detail="API key not found")
        
        logger.info(
            f"API key revoked: {key_id}",
            extra={
                "key_id": key_id,
                "revoked_by": current_admin.login
            }
        )
        
        return {"message": "API key revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key {key_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to revoke API key")


@router.get("/scopes")
async def get_available_scopes(_: str = Depends(verify_token)):
    """Получение доступных областей доступа для API ключей"""
    return {
        "scopes": [
            {
                "value": scope.value,
                "description": _get_scope_description(scope)
            }
            for scope in APIKeyScope
        ]
    }


def _get_scope_description(scope: APIKeyScope) -> str:
    """Получение описания области доступа"""
    descriptions = {
        APIKeyScope.READ_ONLY: "Только чтение данных (пользователи, тарифы, статистика)",
        APIKeyScope.BOOKINGS: "Управление бронированиями (создание, изменение, отмена)",
        APIKeyScope.USERS: "Управление пользователями (просмотр, редактирование)",
        APIKeyScope.NOTIFICATIONS: "Отправка уведомлений пользователям",
        APIKeyScope.MONITORING: "Доступ к метрикам и мониторингу",
        APIKeyScope.ADMIN: "Полный административный доступ ко всем функциям"
    }
    return descriptions.get(scope, "Неизвестная область доступа")


# Пример защищенного эндпоинта для тестирования API ключей
@router.get("/test/read-only")
async def test_read_only_access(
    key_info: dict = Depends(verify_api_key_admin)
):
    """
    Тестовый эндпоинт для проверки API ключей с областью READ_ONLY
    """
    return {
        "message": "API key authentication successful",
        "key_info": key_info,
        "timestamp": datetime.utcnow().isoformat()
    }