from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    UserProfilePhotos,
    File,
)

from config import ADMIN_URL, RULES_URL
from utils.logger import get_logger

logger = get_logger(__name__)


def create_user_keyboard() -> InlineKeyboardMarkup:
    """Создание основной клавиатуры пользователя"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Забронировать", callback_data="book")],
            [InlineKeyboardButton(text="🎫 Поддержка", callback_data="support")],
            [
                InlineKeyboardButton(
                    text="👥 Пригласить друзей", callback_data="invite_friends"
                )
            ],
            [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")],
            [
                InlineKeyboardButton(
                    text="📱 Связаться с администратором", url=ADMIN_URL
                )
            ],
            [InlineKeyboardButton(text="📋 Правила коворкинга", url=RULES_URL)],
        ]
    )
    return keyboard


def create_back_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры с кнопкой 'Назад'"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")]
        ]
    )


async def save_user_avatar(bot: Bot, user_id: int) -> Optional[str]:
    """
    Сохранение аватара пользователя.

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя в Telegram

    Returns:
        Путь к сохраненному файлу или None
    """
    try:
        # Получаем фото профиля
        profile_photos: UserProfilePhotos = await bot.get_user_profile_photos(
            user_id=user_id, limit=1
        )

        if not profile_photos.photos:
            logger.info(f"У пользователя {user_id} нет фото профиля")
            return None

        # Берем самое большое фото (последнее в списке)
        photo = profile_photos.photos[0][-1]
        file: File = await bot.get_file(photo.file_id)

        # Создаем директорию для аватаров если её нет
        avatars_dir = Path("avatars")
        avatars_dir.mkdir(exist_ok=True)

        # Формируем путь к файлу
        file_path = avatars_dir / f"{user_id}.jpg"

        # Скачиваем файл
        file_content = await bot.download_file(file.file_path)

        # Преобразуем в байты если нужно
        if hasattr(file_content, "read"):
            content_bytes = file_content.read()
        else:
            content_bytes = (
                file_content.getvalue()
                if hasattr(file_content, "getvalue")
                else bytes(file_content)
            )

        # Сохраняем файл
        with open(file_path, "wb") as f:
            f.write(content_bytes)

        logger.info(f"Аватар пользователя {user_id} сохранен: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Ошибка при сохранении аватара пользователя {user_id}: {e}")
        return None
