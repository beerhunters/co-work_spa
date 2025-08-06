from typing import Optional
from aiogram import Bot
import os
from utils.logger import get_logger

logger = get_logger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
_bot: Optional[Bot] = None


def init_bot() -> Bot:
    """Инициализирует экземпляр бота.

    Returns:
        Экземпляр Bot.

    Сложность: O(1).
    """
    global _bot
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не указан в переменных окружения")
        raise ValueError("BOT_TOKEN не указан")
    try:
        _bot = Bot(token=BOT_TOKEN)
        logger.info("Бот успешно инициализирован")
        return _bot
    except Exception as e:
        logger.error(f"Ошибка при инициализации бота: {str(e)}")
        raise


def get_bot() -> Bot:
    """Возвращает экземпляр бота (синглтон).

    Returns:
        Экземпляр Bot.

    Сложность: O(1).
    """
    global _bot
    if _bot is None:
        _bot = init_bot()
    return _bot
