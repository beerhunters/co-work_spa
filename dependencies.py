from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from aiogram import Bot
from typing import Optional

from models.models import Session as DBSession
from config import SECRET_KEY_JWT, ALGORITHM, BOT_TOKEN
from utils.logger import get_logger

logger = get_logger(__name__)
security = HTTPBearer()

# Глобальный экземпляр бота
_bot: Optional[Bot] = None


def get_db():
    """Получение сессии БД с улучшенной обработкой ошибок."""
    session = DBSession()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка сессии БД: {e}")
        raise
    finally:
        try:
            session.close()
        except Exception as e:
            logger.error(f"Ошибка закрытия сессии БД: {e}")


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


def get_bot() -> Optional[Bot]:
    """Получение экземпляра бота."""
    global _bot
    if _bot is None and BOT_TOKEN:
        _bot = Bot(token=BOT_TOKEN)
    return _bot


def init_bot():
    """Инициализация бота."""
    global _bot
    if BOT_TOKEN and _bot is None:
        _bot = Bot(token=BOT_TOKEN)
        logger.info("Бот инициализирован")
    return _bot


async def close_bot():
    """Закрытие бота."""
    global _bot
    if _bot:
        await _bot.session.close()
        _bot = None
        logger.info("Бот закрыт")
