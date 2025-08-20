from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import threading
import time

from config import SECRET_KEY_JWT, ALGORITHM, BOT_TOKEN
from models.models import DatabaseManager, Admin, Permission, AdminRole
from utils.logger import get_logger
from aiogram import Bot

logger = get_logger(__name__)
security = HTTPBearer()
_bot: Optional[Bot] = None

# Thread-local хранилище для кеширования администраторов
_thread_local = threading.local()


class CachedAdmin:
    """Простой класс для кешированных данных администратора"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def has_permission(self, permission: Permission) -> bool:
        """Проверяет разрешение из кешированных данных"""
        if self.role == AdminRole.SUPER_ADMIN:
            return True
        return hasattr(self, "permissions") and permission.value in self.permissions

    def get_permissions_list(self) -> list:
        """Возвращает список разрешений из кеша"""
        if self.role == AdminRole.SUPER_ADMIN:
            return [p.value for p in Permission]
        return getattr(self, "permissions", [])

    def safe_get_creator_login(self) -> Optional[str]:
        """Возвращает логин создателя из кеша"""
        return getattr(self, "creator_login", None)


def get_db():
    """Генератор сессий для FastAPI dependency injection"""
    session = None
    try:
        session = DatabaseManager.get_session()
        yield session
    except Exception as e:
        logger.error(f"Error in get_db: {e}")
        if session:
            try:
                session.rollback()
            except:
                pass
        raise
    finally:
        if session:
            try:
                session.close()
            except Exception as e:
                logger.warning(f"Error closing session: {e}")


def _get_admin_from_cache(username: str) -> Optional[Admin]:
    """Получение админа из thread-local кеша"""
    if not hasattr(_thread_local, "admin_cache"):
        _thread_local.admin_cache = {}

    cache_key = f"admin_{username}"
    cache_data = _thread_local.admin_cache.get(cache_key)

    if cache_data:
        admin_data, timestamp = cache_data
        # Кеш действителен 60 секунд
        if time.time() - timestamp < 60:
            return admin_data

    return None


def _set_admin_cache(username: str, admin_data: dict):
    """Сохранение админа в thread-local кеш"""
    if not hasattr(_thread_local, "admin_cache"):
        _thread_local.admin_cache = {}

    cache_key = f"admin_{username}"
    _thread_local.admin_cache[cache_key] = (admin_data, time.time())


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CachedAdmin:
    """Базовая проверка токена и получение админа"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
        username: str = payload.get("sub")

        if username is None:
            raise credentials_exception

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Unexpected error in token validation: {e}")
        raise credentials_exception

    # Проверяем кеш сначала
    cached_admin_data = _get_admin_from_cache(username)
    if cached_admin_data:
        # Создаем объект CachedAdmin из кешированных данных
        return CachedAdmin(**cached_admin_data)

    # Если нет в кеше, загружаем из БД
    def _get_admin_data(session):
        admin = (
            session.query(Admin)
            .filter(Admin.login == username, Admin.is_active == True)
            .first()
        )

        if not admin:
            return None

        # Сериализуем данные админа для кеша
        admin_data = {
            "id": admin.id,
            "login": admin.login,
            "role": admin.role,
            "is_active": admin.is_active,
            "created_at": admin.created_at,
            "created_by": admin.created_by,
        }

        # Загружаем разрешения
        try:
            permissions = []
            for ap in admin.permissions:
                if ap.granted:
                    permissions.append(ap.permission.value)
            admin_data["permissions"] = permissions
        except Exception as e:
            logger.warning(f"Could not load permissions for {username}: {e}")
            admin_data["permissions"] = []

        # Загружаем создателя
        try:
            creator_login = None
            if admin.creator:
                creator_login = admin.creator.login
            admin_data["creator_login"] = creator_login
        except Exception as e:
            logger.warning(f"Could not load creator for {username}: {e}")
            admin_data["creator_login"] = None

        return admin_data

    try:
        admin_data = DatabaseManager.safe_execute(_get_admin_data)

        if not admin_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin not found or inactive",
            )

        # Сохраняем в кеш
        _set_admin_cache(username, admin_data)

        # Создаем объект CachedAdmin
        return CachedAdmin(**admin_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error in verify_token for user {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during authentication",
        )


def verify_token_with_permissions(required_permissions: List[Permission]):
    """Декоратор для проверки разрешений"""

    def permission_checker(
        current_admin: CachedAdmin = Depends(verify_token),
    ) -> CachedAdmin:

        # Супер админ имеет все права
        if current_admin.role == AdminRole.SUPER_ADMIN:
            return current_admin

        # Проверяем каждое требуемое разрешение
        admin_permissions = getattr(current_admin, "permissions", [])

        for permission in required_permissions:
            if permission.value not in admin_permissions:
                logger.warning(
                    f"Admin {current_admin.login} tried to access {permission.value} without permission"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}",
                )

        return current_admin

    return permission_checker


def require_super_admin(
    current_admin: CachedAdmin = Depends(verify_token),
) -> CachedAdmin:
    """Проверка, что пользователь - супер админ"""
    if current_admin.role != AdminRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required"
        )
    return current_admin


def get_bot() -> Optional[Bot]:
    """Получение экземпляра бота"""
    global _bot
    if _bot is None and BOT_TOKEN:
        try:
            _bot = Bot(token=BOT_TOKEN)
            logger.info("Bot instance created successfully")
        except Exception as e:
            logger.error(f"Failed to create bot instance: {e}")
            return None
    return _bot


def init_bot():
    """Инициализация бота"""
    global _bot
    if BOT_TOKEN:
        try:
            _bot = Bot(token=BOT_TOKEN)
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")


async def close_bot():
    """Закрытие сессии бота"""
    global _bot
    if _bot:
        try:
            await _bot.session.close()
            logger.info("Bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
        finally:
            _bot = None


def clear_admin_cache():
    """Очистка кеша администраторов (вызывается при изменениях)"""
    if hasattr(_thread_local, "admin_cache"):
        _thread_local.admin_cache.clear()
        logger.debug("Admin cache cleared")
