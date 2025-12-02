from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import threading
import time
import asyncio

from config import get_secret_key_jwt, get_bot_token, ALGORITHM
from models.models import DatabaseManager, Admin, Permission, AdminRole
from utils.logger import get_logger
from utils.cache_manager import cache_manager
from aiogram import Bot

logger = get_logger(__name__)
security = HTTPBearer()
_bot: Optional[Bot] = None


class ThreadSafeCache:
    """Thread-safe кэш с TTL для администраторов"""

    def __init__(self, default_ttl: int = 60):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()  # Reentrant lock для вложенных вызовов
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша с проверкой TTL"""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            # Проверяем не истек ли TTL
            if current_time > entry["expires_at"]:
                del self._cache[key]
                return None

            # Обновляем время последнего доступа для статистики
            entry["last_accessed"] = current_time
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Сохранение значения в кэш с TTL"""
        with self._lock:
            expires_at = time.time() + (ttl or self.default_ttl)
            self._cache[key] = {
                "value": value,
                "created_at": time.time(),
                "expires_at": expires_at,
                "last_accessed": time.time(),
            }

    def delete(self, key: str) -> bool:
        """Удаление конкретного ключа из кэша"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Полная очистка кэша"""
        with self._lock:
            self._cache.clear()

    def cleanup_expired(self) -> int:
        """Очистка истекших записей, возвращает количество удаленных"""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time > entry["expires_at"]
            ]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Статистика использования кэша"""
        with self._lock:
            current_time = time.time()
            total_entries = len(self._cache)
            active_entries = sum(
                1
                for entry in self._cache.values()
                if current_time <= entry["expires_at"]
            )

            return {
                "total_entries": total_entries,
                "active_entries": active_entries,
                "expired_entries": total_entries - active_entries,
            }


# Глобальный thread-safe кэш для администраторов
_admin_cache = ThreadSafeCache(default_ttl=60)


class CachedAdmin:
    """Класс для кешированных данных администратора"""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def has_permission(self, permission: Permission) -> bool:
        """Проверяет разрешение из кешированных данных"""
        # Проверяем супер админа (учитываем как enum, так и string значения)
        if (self.role == AdminRole.SUPER_ADMIN or 
            (isinstance(self.role, str) and self.role == AdminRole.SUPER_ADMIN.value)):
            return True
        return hasattr(self, "permissions") and permission.value in self.permissions

    def get_permissions_list(self) -> list:
        """Возвращает список разрешений из кеша"""
        if (self.role == AdminRole.SUPER_ADMIN or 
            (isinstance(self.role, str) and self.role == AdminRole.SUPER_ADMIN.value)):
            return [p.value for p in Permission]
        return getattr(self, "permissions", [])

    def safe_get_creator_login(self) -> Optional[str]:
        """Возвращает логин создателя из кеша"""
        return getattr(self, "creator_login", None)


def get_db():
    """Генератор сессий с connection pooling"""
    session = None
    try:
        session = DatabaseManager.get_session()
        yield session
    except Exception as e:
        # Улучшенное логирование с типом исключения и traceback
        import traceback
        logger.error(
            f"Error in get_db: {type(e).__name__}: {e}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
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


class AdminCacheManager:
    """Менеджер thread-safe кэша администраторов"""

    @staticmethod
    def get_cache_key(username: str) -> str:
        """Генерация стандартного ключа кэша"""
        return f"admin:{username}"

    @staticmethod
    def get_admin_from_cache(username: str) -> Optional[Dict[str, Any]]:
        """Безопасное получение администратора из кэша"""
        cache_key = AdminCacheManager.get_cache_key(username)
        cached_data = _admin_cache.get(cache_key)

        if cached_data:
            logger.debug(f"Admin cache HIT: {username}")
            return cached_data

        logger.debug(f"Admin cache MISS: {username}")
        return None

    @staticmethod
    def set_admin_cache(
        username: str, admin_data: Dict[str, Any], ttl: int = 60
    ) -> None:
        """Безопасное сохранение администратора в кэш"""
        cache_key = AdminCacheManager.get_cache_key(username)
        _admin_cache.set(cache_key, admin_data, ttl)
        logger.debug(f"Admin cached: {username}")

    @staticmethod
    def invalidate_admin_cache(username: str) -> bool:
        """Инвалидация кэша конкретного администратора"""
        cache_key = AdminCacheManager.get_cache_key(username)
        result = _admin_cache.delete(cache_key)
        if result:
            logger.debug(f"Admin cache invalidated: {username}")
        return result


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CachedAdmin:
    """Thread-safe проверка токена и получение админа"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, get_secret_key_jwt(), algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")  # JWT ID для revocation

        if username is None:
            raise credentials_exception

        # Проверка jti в blacklist (если токен был отозван)
        if jti:
            # Проверяем Redis blacklist (синхронный вызов)
            blacklist_key = f"blacklist:jti:{jti}"
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                is_blacklisted = loop.run_until_complete(cache_manager.get(blacklist_key))

                if is_blacklisted:
                    logger.warning(
                        f"Attempt to use blacklisted token",
                        extra={"jti": jti, "username": username}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token has been revoked"
                    )
            except RuntimeError:
                # Если event loop не доступен, пропускаем проверку blacklist
                # (может произойти в некоторых edge cases)
                logger.debug("Could not check token blacklist (no event loop)")

        # Проверка глобального отзыва токенов для администратора
        # (все токены выданные до определенного времени)
        iat = payload.get("iat")  # Issued at timestamp
        if iat:
            try:
                import asyncio
                loop = asyncio.get_event_loop()

                # Получаем admin_id из БД для проверки revocation
                def _get_admin_id(session):
                    admin = session.query(Admin).filter(Admin.login == username).first()
                    return admin.id if admin else None

                admin_id = DatabaseManager.safe_execute(_get_admin_id)

                if admin_id:
                    revoke_key = f"admin_revoked:{admin_id}"
                    revoked_timestamp_str = loop.run_until_complete(cache_manager.get(revoke_key))

                    if revoked_timestamp_str:
                        revoked_timestamp = float(revoked_timestamp_str)
                        # Если токен выдан до времени отзыва - отклоняем
                        if iat < revoked_timestamp:
                            logger.warning(
                                f"Attempt to use revoked token (admin-wide revocation)",
                                extra={
                                    "username": username,
                                    "admin_id": admin_id,
                                    "token_iat": iat,
                                    "revoked_at": revoked_timestamp
                                }
                            )
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="All your tokens have been revoked. Please log in again."
                            )
            except RuntimeError:
                # Event loop не доступен
                pass
            except Exception as e:
                # Не блокируем авторизацию при ошибках проверки revocation
                logger.error(f"Error checking admin revocation: {e}")

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

    # Безопасная проверка кэша
    cached_admin_data = AdminCacheManager.get_admin_from_cache(username)
    if cached_admin_data:
        return CachedAdmin(**cached_admin_data)

    # Загрузка из БД с кэшированием
    def _get_admin_data(session):
        admin = (
            session.query(Admin)
            .filter(Admin.login == username, Admin.is_active == True)
            .first()
        )

        if not admin:
            return None

        # Подготовка данных для кэша
        admin_data = {
            "id": admin.id,
            "login": admin.login,
            "role": admin.role,
            "is_active": admin.is_active,
            "created_at": admin.created_at,
            "created_by": admin.created_by,
        }

        # Безопасная загрузка разрешений
        try:
            permissions = []
            for ap in admin.permissions:
                if ap.granted:
                    permissions.append(ap.permission.value)
            admin_data["permissions"] = permissions
        except Exception as e:
            logger.warning(f"Could not load permissions for {username}: {e}")
            admin_data["permissions"] = []

        # Безопасная загрузка создателя
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

        # Кэшируем на 60 секунд
        AdminCacheManager.set_admin_cache(username, admin_data, ttl=60)

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
    """Декоратор для проверки разрешений с thread-safe кэшем"""

    def permission_checker(
        current_admin: CachedAdmin = Depends(verify_token),
    ) -> CachedAdmin:

        # Супер админ имеет все права
        if (current_admin.role == AdminRole.SUPER_ADMIN or 
            (isinstance(current_admin.role, str) and current_admin.role == AdminRole.SUPER_ADMIN.value)):
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
    if not (current_admin.role == AdminRole.SUPER_ADMIN or 
            (isinstance(current_admin.role, str) and current_admin.role == AdminRole.SUPER_ADMIN.value)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required"
        )
    return current_admin


def get_bot() -> Optional[Bot]:
    """Thread-safe получение экземпляра бота"""
    global _bot
    try:
        bot_token = get_bot_token()
        if _bot is None and bot_token:
            _bot = Bot(token=bot_token)
            logger.info("Bot instance created successfully")
    except Exception as e:
        logger.error(f"Failed to create bot instance: {e}")
        return None
    return _bot


def init_bot():
    """Инициализация бота"""
    global _bot
    try:
        bot_token = get_bot_token()
        if bot_token:
            _bot = Bot(token=bot_token)
            logger.info("Bot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize bot: {e}")


async def close_bot():
    """Закрытие сессии бота"""
    try:
        from utils.bot_instance import close_bot as close_bot_instance
        await close_bot_instance()
        logger.info("Bot session closed")
    except Exception as e:
        logger.error(f"Error closing bot session: {e}")


def clear_admin_cache():
    """Thread-safe очистка кэша администраторов"""
    _admin_cache.clear()
    logger.debug("Admin cache cleared")


def invalidate_admin_cache(username: str):
    """Инвалидация кэша конкретного администратора"""
    AdminCacheManager.invalidate_admin_cache(username)


def get_cache_stats() -> Dict[str, Any]:
    """Получение статистики кэша для мониторинга"""
    return _admin_cache.get_stats()


# Фоновая задача для периодической очистки кэша
class CacheCleanupTask:
    """Асинхронная задача для очистки истекшего кэша"""

    def __init__(self, cleanup_interval: int = 300):  # 5 минут
        self.cleanup_interval = cleanup_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Запуск задачи очистки"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cache cleanup task started")

    async def stop(self):
        """Остановка задачи очистки"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Cache cleanup task stopped")

    async def _cleanup_loop(self):
        """Основной цикл очистки истекших записей"""
        while self._running:
            try:
                expired_count = _admin_cache.cleanup_expired()

                if expired_count > 0:
                    logger.debug(f"Cleaned up {expired_count} expired cache entries")

                # Логируем статистику периодически
                stats = _admin_cache.get_stats()
                logger.debug(f"Cache stats: {stats}")

                await asyncio.sleep(self.cleanup_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup task: {e}")
                await asyncio.sleep(30)  # Короткая пауза при ошибке


# Глобальная задача очистки
_cleanup_task = CacheCleanupTask()


async def init_cache_manager():
    """Инициализация глобального менеджера кэша"""
    try:
        await cache_manager.initialize()
        logger.info("Cache manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize cache manager: {e}")


async def close_cache_manager():
    """Закрытие соединений менеджера кэша"""
    try:
        await cache_manager.close()
        logger.info("Cache manager closed")
    except Exception as e:
        logger.error(f"Error closing cache manager: {e}")


async def start_cache_cleanup():
    """Запуск фоновой задачи очистки кэша"""
    await init_cache_manager()
    await _cleanup_task.start()


async def stop_cache_cleanup():
    """Остановка фоновой задачи очистки кэша"""
    await _cleanup_task.stop()
    await close_cache_manager()
