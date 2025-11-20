from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt
import secrets
from werkzeug.security import check_password_hash

from models.models import Admin, RefreshToken, DatabaseManager
from config import (
    SECRET_KEY_JWT,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    MOSCOW_TZ
)
from dependencies import get_db
from utils.logger import get_logger
from utils.rate_limiter import get_rate_limiter

logger = get_logger(__name__)

router = APIRouter(tags=["authentication"])
security = HTTPBearer()


class AdminCredentials(BaseModel):
    """Модель данных админа для аутентификации."""

    login: str
    password: str


class TokenResponse(BaseModel):
    """Модель ответа с токеном."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Модель запроса для обновления токена."""

    refresh_token: str


def create_access_token(data: dict):
    """Создание JWT токена."""
    to_encode = data.copy()

    # Поддержка тестового режима с минутами или обычного режима с часами
    if ACCESS_TOKEN_EXPIRE_MINUTES is not None:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.info(f"Creating access token with {ACCESS_TOKEN_EXPIRE_MINUTES} minutes expiration")
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        logger.debug(f"Creating access token with {ACCESS_TOKEN_EXPIRE_HOURS} hours expiration")

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(admin_id: int, db: Session) -> str:
    """Создание refresh токена для администратора."""
    # Генерируем уникальный токен
    token = secrets.token_urlsafe(64)

    # Устанавливаем срок действия
    expires_at = datetime.now(MOSCOW_TZ) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Сохраняем в базе данных
    refresh_token = RefreshToken(
        admin_id=admin_id,
        token=token,
        expires_at=expires_at
    )
    db.add(refresh_token)
    db.commit()

    logger.info(f"Created refresh token for admin_id={admin_id}, expires at {expires_at}")
    return token


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка JWT токена."""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY_JWT, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Основные эндпоинты аутентификации с префиксом /auth
@router.post("/auth/login", response_model=TokenResponse)
async def login_auth(credentials: AdminCredentials, request: Request, db: Session = Depends(get_db)):
    """Аутентификация администратора через /auth/login с защитой от брутфорса."""
    
    # Применяем строгий rate limiting для логина
    rate_limiter = get_rate_limiter()
    await rate_limiter.check_limit(request, "auth:login")
    
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        # Логируем неудачную попытку входа для мониторинга
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        logger.warning(
            f"Неудачная попытка входа",
            extra={
                "login": credentials.login,
                "client_ip": client_ip,
                "user_agent": request.headers.get("User-Agent", ""),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Создаем access и refresh токены
    access_token = create_access_token(data={"sub": admin.login})
    refresh_token = create_refresh_token(admin.id, db)

    logger.info(f"Успешная аутентификация пользователя: {admin.login}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


@router.get("/auth/verify")
async def verify_token_endpoint(username: str = Depends(verify_token)):
    """Проверка действительности токена."""
    return {"username": username, "valid": True}


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_access_token(request_data: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Обновление access токена с помощью refresh токена."""
    try:
        # Ищем refresh токен в базе данных
        refresh_token_db = db.query(RefreshToken).filter(
            RefreshToken.token == request_data.refresh_token,
            RefreshToken.revoked == False
        ).first()

        if not refresh_token_db:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Проверяем, не истек ли токен
        if refresh_token_db.expires_at < datetime.now(MOSCOW_TZ):
            raise HTTPException(status_code=401, detail="Refresh token expired")

        # Получаем администратора
        admin = db.query(Admin).filter(Admin.id == refresh_token_db.admin_id).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")

        # Создаем новый access токен
        new_access_token = create_access_token(data={"sub": admin.login})

        # Создаем новый refresh токен (ротация токенов)
        new_refresh_token = create_refresh_token(admin.id, db)

        # Отзываем старый refresh токен
        refresh_token_db.revoked = True
        db.commit()

        logger.info(f"Refreshed tokens for admin: {admin.login}")
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/auth/logout")
async def logout():
    """Выход из системы."""
    return {"message": "Logged out successfully"}


@router.get("/auth/me")
async def get_current_user_auth(
    username: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """Получение информации о текущем пользователе."""
    admin = db.query(Admin).filter(Admin.login == username).first()
    if not admin:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": admin.id,
        "login": admin.login,
        "is_active": admin.is_active,
        "permissions": ["admin"],
    }


# Дублирующие эндпоинты для совместимости с фронтендом (без префикса)
@router.post("/login", response_model=TokenResponse, include_in_schema=False)
async def login_root(credentials: AdminCredentials, request: Request, db: Session = Depends(get_db)):
    """Аутентификация администратора (корневой эндпоинт для совместимости)."""
    return await login_auth(credentials, request, db)


@router.get("/verify_token", include_in_schema=False)
async def verify_token_root(username: str = Depends(verify_token)):
    """Проверка токена (корневой эндпоинт для совместимости)."""
    return await verify_token_endpoint(username)


@router.get("/me", include_in_schema=False)
async def get_current_user_root(
    username: str = Depends(verify_token), db: Session = Depends(get_db)
):
    """Получение текущего пользователя (корневой эндпоинт для совместимости)."""
    return await get_current_user_auth(username, db)


@router.get("/logout", include_in_schema=False)
async def logout_root():
    """Выход из системы (корневой эндпоинт для совместимости)."""
    return {"message": "Logged out successfully"}
