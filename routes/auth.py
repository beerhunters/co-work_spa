from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt
from werkzeug.security import check_password_hash

from models.models import Admin
from config import SECRET_KEY_JWT, ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
from dependencies import get_db
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
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


@router.post("/login", response_model=TokenResponse)
async def login(credentials: AdminCredentials, db: Session = Depends(get_db)):
    """Аутентификация администратора."""
    admin = db.query(Admin).filter(Admin.login == credentials.login).first()
    if not admin or not check_password_hash(admin.password, credentials.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": admin.login})
    logger.info(f"Успешная аутентификация пользователя: {admin.login}")
    return {"access_token": access_token}


@router.get("/verify")
async def verify_token_endpoint(username: str = Depends(verify_token)):
    """Проверка действительности токена."""
    return {"username": username, "valid": True}


@router.post("/logout")
async def logout():
    """Выход из системы."""
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(
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
        "permissions": ["admin"],  # Расширяемо для будущих ролей
    }
