"""
Модуль для управления API ключами и аутентификацией внешних сервисов
"""
import secrets
import hashlib
import time
from typing import Dict, Optional, List
from enum import Enum
from datetime import datetime, timedelta

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base

from utils.logger import get_logger
from models.models import Base, DatabaseManager

logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


class APIKeyScope(Enum):
    """Области доступа для API ключей"""
    READ_ONLY = "read_only"           # Только чтение данных
    BOOKINGS = "bookings"             # Управление бронированиями  
    USERS = "users"                   # Управление пользователями
    NOTIFICATIONS = "notifications"   # Отправка уведомлений
    MONITORING = "monitoring"         # Доступ к метрикам
    ADMIN = "admin"                   # Полный административный доступ


class APIKey(Base):
    """Модель API ключа"""
    
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # Человекочитаемое имя
    key_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA-256 хэш ключа
    key_prefix = Column(String(16), nullable=False, index=True)  # Префикс для быстрого поиска
    scopes = Column(Text, nullable=False)  # JSON список областей доступа
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Metadata
    created_by = Column(String(100), nullable=False)  # Кто создал ключ
    created_at = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Безопасность
    allowed_ips = Column(Text, nullable=True)  # JSON список разрешенных IP
    expires_at = Column(DateTime, nullable=True)  # Срок действия ключа
    max_requests_per_hour = Column(Integer, default=1000)  # Rate limiting


class APIKeyManager:
    """Менеджер для работы с API ключами"""
    
    def __init__(self):
        self._rate_limit_cache: Dict[str, Dict] = {}
    
    def generate_api_key(
        self,
        name: str,
        scopes: List[APIKeyScope],
        created_by: str,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        max_requests_per_hour: int = 1000
    ) -> Dict[str, str]:
        """
        Генерация нового API ключа
        
        Returns:
            dict: {"key": "raw_key", "key_id": "key_id"}
        """
        # Генерируем случайный ключ
        raw_key = self._generate_raw_key()
        key_prefix = raw_key[:16]
        key_hash = self._hash_key(raw_key)
        
        # Подготавливаем данные
        scopes_json = ",".join([scope.value for scope in scopes])
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        allowed_ips_json = None
        if allowed_ips:
            allowed_ips_json = ",".join(allowed_ips)
        
        # Сохраняем в БД
        def _create_key(session):
            api_key = APIKey(
                name=name,
                key_hash=key_hash,
                key_prefix=key_prefix,
                scopes=scopes_json,
                created_by=created_by,
                allowed_ips=allowed_ips_json,
                expires_at=expires_at,
                max_requests_per_hour=max_requests_per_hour
            )
            session.add(api_key)
            session.commit()
            
            logger.info(f"API key created: {name}", extra={
                "key_id": api_key.id,
                "scopes": scopes_json,
                "created_by": created_by,
                "event_type": "security"
            })
            
            return {"key": raw_key, "key_id": str(api_key.id)}
        
        return DatabaseManager.safe_execute(_create_key)
    
    def validate_api_key(
        self, 
        raw_key: str, 
        required_scope: Optional[APIKeyScope] = None,
        client_ip: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Валидация API ключа
        
        Returns:
            Dict с информацией о ключе или None если невалидный
        """
        if not raw_key or len(raw_key) < 32:
            return None
        
        key_prefix = raw_key[:16]
        key_hash = self._hash_key(raw_key)
        
        def _validate(session):
            # Находим ключ по префиксу и хэшу
            api_key = session.query(APIKey).filter(
                APIKey.key_prefix == key_prefix,
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            ).first()
            
            if not api_key:
                return None
            
            # Проверяем срок действия
            if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
                logger.warning(f"Expired API key used: {api_key.name}")
                return None
            
            # Проверяем IP ограничения
            if api_key.allowed_ips and client_ip:
                allowed_ips = api_key.allowed_ips.split(",")
                if client_ip not in allowed_ips:
                    logger.warning(f"API key used from unauthorized IP: {client_ip}")
                    return None
            
            # Проверяем области доступа
            scopes = api_key.scopes.split(",") if api_key.scopes else []
            if required_scope and required_scope.value not in scopes:
                logger.warning(f"API key missing required scope: {required_scope.value}")
                return None
            
            # Проверяем rate limiting
            if not self._check_rate_limit(api_key):
                logger.warning(f"API key rate limit exceeded: {api_key.name}")
                return None
            
            # Обновляем статистику использования
            api_key.last_used = datetime.utcnow()
            api_key.usage_count += 1
            session.commit()
            
            return {
                "id": api_key.id,
                "name": api_key.name,
                "scopes": scopes,
                "created_by": api_key.created_by
            }
        
        return DatabaseManager.safe_execute(_validate)
    
    def revoke_api_key(self, key_id: int, revoked_by: str) -> bool:
        """Отзыв API ключа"""
        def _revoke(session):
            api_key = session.query(APIKey).filter(APIKey.id == key_id).first()
            if not api_key:
                return False
            
            api_key.is_active = False
            session.commit()
            
            logger.info(f"API key revoked: {api_key.name}", extra={
                "key_id": key_id,
                "revoked_by": revoked_by,
                "event_type": "security"
            })
            return True
        
        return DatabaseManager.safe_execute(_revoke)
    
    def list_api_keys(self, include_inactive: bool = False) -> List[Dict]:
        """Получение списка API ключей"""
        def _list_keys(session):
            query = session.query(APIKey)
            if not include_inactive:
                query = query.filter(APIKey.is_active == True)
            
            keys = query.order_by(APIKey.created_at.desc()).all()
            
            return [
                {
                    "id": key.id,
                    "name": key.name,
                    "scopes": key.scopes.split(",") if key.scopes else [],
                    "is_active": key.is_active,
                    "created_by": key.created_by,
                    "created_at": key.created_at.isoformat() if key.created_at else None,
                    "last_used": key.last_used.isoformat() if key.last_used else None,
                    "usage_count": key.usage_count,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None
                }
                for key in keys
            ]
        
        return DatabaseManager.safe_execute(_list_keys)
    
    def _generate_raw_key(self) -> str:
        """Генерация сырого API ключа"""
        # Префикс для идентификации наших ключей
        prefix = "cws"  # coworking-spa
        # Случайная часть (32 байта = 64 hex символа)
        random_part = secrets.token_hex(32)
        return f"{prefix}_{random_part}"
    
    def _hash_key(self, raw_key: str) -> str:
        """Хэширование API ключа"""
        return hashlib.sha256(raw_key.encode()).hexdigest()
    
    def _check_rate_limit(self, api_key: APIKey) -> bool:
        """Проверка rate limiting для API ключа"""
        current_time = time.time()
        current_hour = int(current_time // 3600)
        cache_key = f"{api_key.id}:{current_hour}"
        
        # Проверяем кэш rate limiting
        if cache_key in self._rate_limit_cache:
            request_count = self._rate_limit_cache[cache_key]["count"]
            if request_count >= api_key.max_requests_per_hour:
                return False
            # Увеличиваем счетчик
            self._rate_limit_cache[cache_key]["count"] += 1
        else:
            # Создаем новую запись
            self._rate_limit_cache[cache_key] = {
                "count": 1,
                "hour": current_hour
            }
        
        # Очищаем старые записи
        self._cleanup_rate_limit_cache(current_hour)
        
        return True
    
    def _cleanup_rate_limit_cache(self, current_hour: int):
        """Очистка старых записей из кэша rate limiting"""
        keys_to_remove = []
        for key, data in self._rate_limit_cache.items():
            if data["hour"] < current_hour - 1:  # Старше часа
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._rate_limit_cache[key]


# Глобальный экземпляр менеджера
_api_key_manager = APIKeyManager()


# Зависимости для FastAPI
async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    required_scope: Optional[APIKeyScope] = None
) -> Dict:
    """
    Dependency для проверки API ключа
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Валидируем ключ
    key_info = _api_key_manager.validate_api_key(
        credentials.credentials,
        required_scope=required_scope
    )
    
    if not key_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return key_info


# Convenience dependencies для разных областей доступа
async def verify_api_key_read_only(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict:
    return await verify_api_key(credentials, APIKeyScope.READ_ONLY)


async def verify_api_key_bookings(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict:
    return await verify_api_key(credentials, APIKeyScope.BOOKINGS)


async def verify_api_key_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict:
    return await verify_api_key(credentials, APIKeyScope.ADMIN)


# Публичные функции
def generate_api_key(
    name: str,
    scopes: List[APIKeyScope],
    created_by: str,
    **kwargs
) -> Dict[str, str]:
    """Генерация нового API ключа"""
    return _api_key_manager.generate_api_key(name, scopes, created_by, **kwargs)


def revoke_api_key(key_id: int, revoked_by: str) -> bool:
    """Отзыв API ключа"""
    return _api_key_manager.revoke_api_key(key_id, revoked_by)


def list_api_keys(include_inactive: bool = False) -> List[Dict]:
    """Получение списка API ключей"""
    return _api_key_manager.list_api_keys(include_inactive)