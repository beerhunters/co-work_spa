import os
from typing import Optional
from aiogram import Bot
from dotenv import load_dotenv
from utils.logger import get_logger

# Тихая настройка логгера для модуля
logger = get_logger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")

_bot: Optional[Bot] = None


def init_bot() -> Bot:
    """
    Инициализирует и возвращает экземпляр бота.

    Returns:
        Bot: Инициализированный экземпляр aiogram.Bot.

    Raises:
        ValueError: Если BOT_TOKEN не указан в конфигурации.
    """
    global _bot
    if _bot is None:
        bot_token = BOT_TOKEN
        if not bot_token:
            logger.error("BOT_TOKEN не указан в конфигурации")
            raise ValueError("BOT_TOKEN не указан")
        _bot = Bot(token=bot_token)
        logger.info("Экземпляр бота успешно инициализирован")
    return _bot


def get_bot() -> Bot:
    """
    Возвращает существующий экземпляр бота или инициализирует новый.

    Returns:
        Bot: Экземпляр aiogram.Bot.

    Raises:
        ValueError: Если бот не был инициализирован.
    """
    if _bot is None:
        return init_bot()
    return _bot


async def close_bot():
    """
    Корректно закрывает экземпляр бота и его сессию.
    """
    global _bot
    if _bot is not None:
        try:
            await _bot.session.close()
            logger.info("Bot session закрыта корректно")
        except Exception as e:
            logger.error(f"Ошибка при закрытии bot session: {e}")
        finally:
            _bot = None


async def send_admin_notification(message: str):
    """
    Отправляет уведомление администратору в Telegram.

    Args:
        message: Текст сообщения для отправки

    Raises:
        ValueError: Если ADMIN_TELEGRAM_ID не настроен
    """
    if not ADMIN_TELEGRAM_ID:
        logger.warning("ADMIN_TELEGRAM_ID не настроен, уведомление не отправлено")
        return

    try:
        bot = get_bot()
        await bot.send_message(ADMIN_TELEGRAM_ID, message)
        logger.info(f"Уведомление отправлено администратору: {message[:50]}...")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления администратору: {e}", exc_info=True)
