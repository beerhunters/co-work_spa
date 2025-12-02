from datetime import datetime, timedelta
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt
import secrets
from werkzeug.security import check_password_hash
from utils.password_security import verify_password_with_upgrade

from models.models import Admin, RefreshToken, DatabaseManager
from config import (
    get_secret_key_jwt,  # Используем lazy loading функцию
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_HOURS,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    MOSCOW_TZ,
    HCAPTCHA_SECRET_KEY,
    CAPTCHA_ENABLED,
    CAPTCHA_FAILED_ATTEMPTS_THRESHOLD
)
from dependencies import get_db, verify_token
from utils.logger import get_logger
from utils.rate_limiter import get_rate_limiter
from utils.captcha import get_captcha_validator, get_login_tracker
from utils.cache_manager import cache_manager

logger = get_logger(__name__)

router = APIRouter(tags=["authentication"])
security = HTTPBearer()


class AdminCredentials(BaseModel):
    """Модель данных админа для аутентификации."""

    login: str
    password: str
    captcha_token: Optional[str] = None  # hCaptcha token (required after multiple failed attempts)


class TokenResponse(BaseModel):
    """Модель ответа с токеном."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    captcha_required: bool = False  # Flag indicating if CAPTCHA is now required


class RefreshTokenRequest(BaseModel):
    """Модель запроса для обновления токена."""

    refresh_token: str


def create_access_token(data: dict):
    """
    Создание JWT токена с jti для revocation support.

    Включает стандартные JWT claims:
    - sub: subject (username)
    - exp: expiration time
    - iat: issued at time
    - jti: JWT ID (unique identifier для revocation)
    """
    to_encode = data.copy()
    now = datetime.utcnow()

    # Поддержка тестового режима с минутами или обычного режима с часами
    if ACCESS_TOKEN_EXPIRE_MINUTES is not None:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        logger.info(f"Creating access token with {ACCESS_TOKEN_EXPIRE_MINUTES} minutes expiration")
    else:
        expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        logger.debug(f"Creating access token with {ACCESS_TOKEN_EXPIRE_HOURS} hours expiration")

    # Добавляем стандартные JWT claims
    to_encode.update({
        "exp": expire,
        "iat": now,  # Issued at
        "jti": str(uuid.uuid4())  # JWT ID для revocation
    })

    encoded_jwt = jwt.encode(to_encode, get_secret_key_jwt(), algorithm=ALGORITHM)
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
        payload = jwt.decode(token, get_secret_key_jwt(), algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Основные эндпоинты аутентификации с префиксом /auth
@router.post("/auth/login", response_model=TokenResponse)
async def login_auth(credentials: AdminCredentials, request: Request, db: Session = Depends(get_db)):
    """
    Аутентификация администратора через /auth/login с защитой от брутфорса.

    Защита включает:
    - Rate limiting: 5 попыток за 5 минут (IP-based)
    - CAPTCHA: Требуется после 3 неудачных попыток (username-based)
    - Логирование всех неудачных попыток
    """

    # 1. Применяем строгий rate limiting для логина (5/5min)
    rate_limiter = get_rate_limiter()
    await rate_limiter.check_limit(request, "auth:login")

    # 2. Инициализируем CAPTCHA validator и login tracker
    captcha_validator = get_captcha_validator(HCAPTCHA_SECRET_KEY)
    login_tracker = get_login_tracker(CAPTCHA_FAILED_ATTEMPTS_THRESHOLD)

    # 3. Проверяем, требуется ли CAPTCHA для этого логина
    captcha_required = CAPTCHA_ENABLED and login_tracker.requires_captcha(credentials.login)

    if captcha_required:
        # CAPTCHA обязателен - проверяем наличие токена
        if not credentials.captcha_token:
            logger.warning(
                f"CAPTCHA required but not provided",
                extra={
                    "login": credentials.login,
                    "attempts": login_tracker.get_attempt_count(credentials.login)
                }
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "captcha_required",
                    "message": "CAPTCHA verification required after multiple failed attempts"
                }
            )

        # Валидируем CAPTCHA
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        captcha_valid, captcha_data = await captcha_validator.verify(
            token=credentials.captcha_token,
            remote_ip=client_ip
        )

        if not captcha_valid:
            error_codes = captcha_data.get("error-codes", []) if captcha_data else []
            logger.warning(
                f"CAPTCHA validation failed",
                extra={
                    "login": credentials.login,
                    "client_ip": client_ip,
                    "error_codes": error_codes
                }
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "captcha_invalid",
                    "message": "CAPTCHA verification failed",
                    "error_codes": error_codes
                }
            )

    # 4. Проверка учетных данных с автоматическим upgrade хеша
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()

    # Проверяем пароль с возможностью автоматического обновления хеша
    password_valid = False
    needs_upgrade = False
    new_hash = None

    if admin:
        # Используем функцию с поддержкой upgrade
        password_valid, needs_upgrade, new_hash = verify_password_with_upgrade(
            admin.password,
            credentials.password
        )

    if not admin or not password_valid:
        # Неудачная попытка - увеличиваем счетчик
        failed_attempts = login_tracker.record_failed_attempt(credentials.login)

        # Логируем неудачную попытку входа для мониторинга
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        logger.warning(
            f"Неудачная попытка входа",
            extra={
                "login": credentials.login,
                "client_ip": client_ip,
                "user_agent": request.headers.get("User-Agent", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "failed_attempts": failed_attempts,
                "captcha_will_be_required": failed_attempts >= CAPTCHA_FAILED_ATTEMPTS_THRESHOLD
            }
        )

        # Если достигнут порог - возвращаем специальный ответ с флагом captcha_required
        if CAPTCHA_ENABLED and failed_attempts >= CAPTCHA_FAILED_ATTEMPTS_THRESHOLD:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "invalid_credentials",
                    "message": "Invalid credentials",
                    "captcha_required": True
                }
            )

        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 5. Успешный вход - выполняем необходимые действия

    # 5.1. Opportunistic password hash upgrade (pbkdf2 -> bcrypt)
    if needs_upgrade and new_hash:
        admin.password = new_hash
        db.commit()
        logger.info(
            f"Password hash automatically upgraded to bcrypt for admin: {admin.login}"
        )

    # 5.2. Сбрасываем счетчик попыток
    login_tracker.reset_attempts(credentials.login)

    # 6. Создаем access и refresh токены
    access_token = create_access_token(data={"sub": admin.login})
    refresh_token = create_refresh_token(admin.id, db)

    logger.info(f"Успешная аутентификация пользователя: {admin.login}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "captcha_required": False
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
        # Приводим expires_at к timezone-aware, если это naive datetime (из SQLite)
        expires_at_aware = refresh_token_db.expires_at
        if expires_at_aware.tzinfo is None:
            expires_at_aware = MOSCOW_TZ.localize(expires_at_aware)

        if expires_at_aware < datetime.now(MOSCOW_TZ):
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
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Выход из системы с revocation токена.

    Добавляет jti (JWT ID) текущего токена в blacklist,
    делая его недействительным до истечения срока действия.
    """
    try:
        # Декодируем токен чтобы получить jti и exp
        token = credentials.credentials
        payload = jwt.decode(
            token,
            get_secret_key_jwt(),
            algorithms=[ALGORITHM],
            options={"verify_exp": False}  # Разрешаем logout даже для истекших токенов
        )

        jti = payload.get("jti")
        exp = payload.get("exp")
        username = payload.get("sub")

        if not jti:
            # Старые токены без jti - просто возвращаем успех
            logger.warning(f"Logout attempt with token without jti (old token format)")
            return {"message": "Logged out successfully (legacy token)"}

        # Вычисляем TTL для blacklist записи (время до expiration)
        now = datetime.utcnow().timestamp()
        ttl = max(int(exp - now), 60)  # Минимум 60 секунд

        # Добавляем jti в blacklist с TTL
        blacklist_key = f"blacklist:jti:{jti}"
        await cache_manager.set(
            key=blacklist_key,
            value="revoked",
            ttl=ttl
        )

        logger.info(
            f"Token revoked via logout",
            extra={
                "username": username,
                "jti": jti,
                "ttl": ttl
            }
        )

        return {
            "message": "Logged out successfully",
            "token_revoked": True
        }

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token in logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


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
