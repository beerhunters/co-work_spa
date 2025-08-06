from typing import Optional, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import aiohttp
from utils.logger import get_logger
from yookassa import Payment
import pytz

logger = get_logger(__name__)
RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
RUBITIME_BASE_URL = "https://rubitime.ru/api2/"
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_URL = "https://t.me/partacoworking"
RULES = "https://parta-works.ru/main_rules"


def create_user_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для пользователя.

    Returns:
        InlineKeyboardMarkup с кнопками.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Забронировать", callback_data="book")],
            [InlineKeyboardButton(text="Техподдержка", callback_data="ticket")],
            [InlineKeyboardButton(text="Информация", callback_data="info")],
        ]
    )
    return keyboard


def create_back_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой "Назад".

    Returns:
        InlineKeyboardMarkup с кнопкой.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
        ]
    )
    return keyboard


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    """Отправляет запрос к Rubitime API.

    Args:
        method: Метод API.
        extra_params: Дополнительные параметры.

    Returns:
        ID записи или None при ошибке.

    Сложность: O(1) для сетевого запроса.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{RUBITIME_BASE_URL}{method.replace('_', '-')}"
            params = {"api_key": RUBITIME_API_KEY, **extra_params}
            async with session.post(url, json=params) as response:
                if response.status != 200:
                    logger.error(f"Ошибка Rubitime API: {response.status}")
                    return None
                data = await response.json()
                return data.get("data", {}).get("id")
    except Exception as e:
        logger.error(f"Ошибка при запросе к Rubitime: {str(e)}")
        return None


async def check_payment_status(payment_id: str) -> Optional[str]:
    """Проверяет статус платежа через Yookassa.

    Args:
        payment_id: ID платежа.

    Returns:
        Статус платежа или None при ошибке.

    Сложность: O(1).
    """
    try:
        payment = await Payment.find_one(payment_id)
        return payment.status if payment else None
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса платежа {payment_id}: {str(e)}")
        return None
