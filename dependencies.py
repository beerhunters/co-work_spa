from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
import jwt
from jwt.exceptions import (
    InvalidTokenError,
    ExpiredSignatureError,
)  # ← Правильный импорт

from config import SECRET_KEY_JWT, ALGORITHM, BOT_TOKEN
from models.models import DatabaseManager, Admin, Permission, AdminRole
from utils.logger import get_logger
from aiogram import Bot

logger = get_logger(__name__)
security = HTTPBearer()
_bot: Optional[Bot] = None


def get_db():
    """Генератор сессий для FastAPI dependency injection"""
    session = DatabaseManager.get_session()
    try:
        yield session
    finally:
        session.close()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:
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
    except InvalidTokenError:  # ← Правильное исключение
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Unexpected error in token validation: {e}")
        raise credentials_exception

    # Безопасный поиск администратора
    try:
        admin = (
            db.query(Admin)
            .filter(Admin.login == username, Admin.is_active == True)
            .first()
        )

        if admin is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin not found or inactive",
            )

        # Принудительно загружаем связанные данные в текущей сессии
        # для предотвращения DetachedInstanceError
        try:
            # Загружаем permissions - используем len() для инициализации коллекции
            _ = len(admin.permissions)

            # Загружаем creator если есть
            if admin.created_by:
                _ = admin.creator.login if admin.creator else None

        except Exception as e:
            logger.warning(f"Could not preload admin relations for {username}: {e}")
            # Продолжаем работу, даже если не удалось загрузить связанные данные

        return admin

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
        current_admin: Admin = Depends(verify_token), db: Session = Depends(get_db)
    ) -> Admin:

        # Супер админ имеет все права
        if current_admin.role == AdminRole.SUPER_ADMIN:
            return current_admin

        # Проверяем каждое требуемое разрешение
        for permission in required_permissions:
            try:
                has_perm = current_admin.has_permission(permission)
                if not has_perm:
                    logger.warning(
                        f"Admin {current_admin.login} tried to access {permission.value} without permission"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required: {permission.value}",
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Error checking permission {permission.value} for admin {current_admin.login}: {e}"
                )
                # В случае ошибки загрузки разрешений, запрещаем доступ
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Could not verify permissions. Required: {permission.value}",
                )

        return current_admin

    return permission_checker


def require_super_admin(
    current_admin: Admin = Depends(verify_token), db: Session = Depends(get_db)
) -> Admin:
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
