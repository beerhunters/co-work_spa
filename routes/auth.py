from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt
from werkzeug.security import check_password_hash

from models.models import Admin
from config import SECRET_KEY_JWT, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
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
    token_type: str = "bearer"


def create_access_token(data: dict):
    """Создание JWT токена."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_JWT, algorithm=ALGORITHM)
    return encoded_jwt


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

    access_token = create_access_token(data={"sub": admin.login})
    logger.info(f"Успешная аутентификация пользователя: {admin.login}")
    return {"access_token": access_token}


@router.get("/auth/verify")
async def verify_token_endpoint(username: str = Depends(verify_token)):
    """Проверка действительности токена."""
    return {"username": username, "valid": True}


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
