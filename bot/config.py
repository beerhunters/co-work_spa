# import asyncio
# import os
# from datetime import datetime
# from io import BytesIO
# from typing import Optional, Tuple
#
# import aiofiles
# import aiohttp
# import pytz
# from aiogram import Bot
# from aiogram.types import (
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
#     UserProfilePhotos,
#     File,
# )
# from dotenv import load_dotenv
# from yookassa import Payment, Configuration
#
# from utils.logger import get_logger
#
# # Тихая настройка логгера для модуля
# logger = get_logger(__name__)
#
# load_dotenv()
#
# # Конфигурация YooKassa
# Configuration.account_id = os.getenv("YOKASSA_ACCOUNT_ID")
# Configuration.secret_key = os.getenv("YOKASSA_SECRET_KEY")
#
#
# # Конфигурация Rubitime
# RUBITIME_API_KEY = os.getenv("RUBITIME_API_KEY")
# RUBITIME_BASE_URL = "https://rubitime.ru/api2/"
# MOSCOW_TZ = pytz.timezone("Europe/Moscow")
# ADMIN_URL = "https://t.me/partacoworking"
#
# RULES = "https://parta-works.ru/main_rules"
#
# # btn_back = ⬅️ Назад
# # rules_button = 📄 Общие правила
# # contact_admin_button = 📞 Связаться с Администратором
#
#
# def create_user_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создаёт инлайн-клавиатуру для начала регистрации.
#     """
#     logger.debug("Создание инлайн-клавиатуры для пользователя")
#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="📍 Забронировать", callback_data="booking")],
#             [InlineKeyboardButton(text="🛠️ Helpdesk", callback_data="helpdesk")],
#             [InlineKeyboardButton(text="❔ Информация", callback_data="info")],
#             [
#                 InlineKeyboardButton(
#                     text="👥 Пригласить друга", callback_data="invite_friend"
#                 )
#             ],
#             [
#                 InlineKeyboardButton(
#                     text="📞 Связаться с Администратором", url=ADMIN_URL
#                 )
#             ],
#         ]
#     )
#     return keyboard
#
#
# def create_back_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создаёт инлайн-клавиатуру для начала регистрации.
#     """
#     logger.debug("Создание инлайн-клавиатуры для возврата")
#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
#         ]
#     )
#     return keyboard
#
#
# async def save_user_avatar(bot: Bot, user_id: int) -> Optional[str]:
#     """
#     Получает и сохраняет первую аватарку пользователя в папку avatars.
#
#     Args:
#         bot: Экземпляр бота.
#         user_id: Telegram ID пользователя.
#
#     Returns:
#         Optional[str]: Путь к сохранённому файлу или None в случае ошибки.
#
#     Асимптотика: O(1) для запроса к Telegram API, O(n) для записи файла, где n — размер файла.
#     """
#     logger.debug(f"Попытка сохранить аватарку для пользователя {user_id}")
#     try:
#         # Получаем фотографии профиля
#         profile_photos: UserProfilePhotos = await bot.get_user_profile_photos(
#             user_id, limit=1
#         )
#         if not profile_photos.photos or not profile_photos.photos[0]:
#             logger.info(f"У пользователя {user_id} нет аватарки")
#             return None
#
#         # Берем первую фотографию (наименьший размер для экономии)
#         photo = profile_photos.photos[0][-1]  # Последний размер — самый большой
#         file: File = await bot.get_file(photo.file_id)
#
#         # Создаём папку avatars, если она не существует
#         avatars_dir = "avatars"
#         if not os.path.exists(avatars_dir):
#             os.makedirs(avatars_dir)
#             logger.debug(f"Создана папка {avatars_dir}")
#
#         # Формируем путь для сохранения
#         file_path = os.path.join(avatars_dir, f"{user_id}.jpg")
#
#         # Скачиваем файл
#         file_content = await bot.download_file(file.file_path)
#         if file_content is None:
#             logger.error(
#                 f"Не удалось скачать аватарку для пользователя {user_id}: file_content is None"
#             )
#             return None
#
#         # Проверяем тип file_content
#         if isinstance(file_content, bytes):
#             content_bytes = file_content
#         elif isinstance(file_content, BytesIO):
#             content_bytes = (
#                 file_content.read()
#             )  # Синхронное чтение, так как BytesIO не требует await
#         else:
#             logger.error(
#                 f"Неожиданный тип file_content для пользователя {user_id}: {type(file_content)}"
#             )
#             return None
#
#         # Сохраняем файл
#         async with aiofiles.open(file_path, "wb") as f:
#             await f.write(content_bytes)
#
#         logger.info(f"Аватарка пользователя {user_id} сохранена в {file_path}")
#         return file_path
#
#     except Exception as e:
#         logger.error(f"Ошибка при сохранении аватарки для {user_id}: {str(e)}")
#         return None
#
#
# async def rubitime(method: str, extra_params: dict) -> Optional[str]:
#     """
#     Выполнение запроса к Rubitime API.
#
#     Args:
#         method: Метод API ('create_record', 'update_record', 'get_record', 'remove_record').
#         extra_params: Дополнительные параметры для запроса.
#
#     Returns:
#         Optional[str]: ID записи (для create_record) или None.
#     """
#     if method == "create_record":
#         url = f"{RUBITIME_BASE_URL}create-record"
#         params = {
#             "branch_id": 12595,
#             "cooperator_id": 25786,
#             "created_at": datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S"),
#             "status": 0,
#             "source": "Telegram",
#             **extra_params,
#         }
#     else:
#         logger.error(f"Неизвестный метод Rubitime: {method}")
#         return None
#
#     params["rk"] = RUBITIME_API_KEY
#
#     async with aiohttp.ClientSession() as session:
#         try:
#             async with session.post(url, json=params) as response:
#                 if response.status == 200:
#                     data = await response.json()
#                     if data.get("status") == "ok":
#                         if method == "create_record":
#                             record_id = data.get("data", {}).get("id")
#                             logger.debug(f"Создано в Rubitime: ID {record_id}")
#                             return record_id
#                         logger.debug(f"Запрос Rubitime успешен: {method}")
#                         return None
#                     else:
#                         logger.warning(
#                             f"Ошибка Rubitime: {data.get('message', 'Неизвестная ошибка')}"
#                         )
#                         return None
#                 else:
#                     logger.error(
#                         f"Ошибка HTTP {response.status}: {await response.text()}"
#                     )
#                     return None
#         except Exception as e:
#             logger.error(f"Исключение при запросе к Rubitime: {str(e)}")
#             return None
#
#
# async def create_payment(
#     description: str, amount: float
# ) -> Tuple[Optional[str], Optional[str]]:
#     """
#     Создание платежа через YooKassa.
#
#     Args:
#         description: Описание платежа.
#         amount: Сумма платежа.
#
#     Returns:
#         Tuple[Optional[str], Optional[str]]: ID платежа и URL для оплаты или (None, None) при ошибке.
#     """
#     try:
#         payment = Payment.create(
#             {
#                 "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
#                 "confirmation": {
#                     "type": "redirect",
#                     "return_url": os.getenv("BOT_LINK"),
#                 },
#                 "capture": True,
#                 "description": description,
#             }
#         )
#         logger.debug(
#             f"Платёж создан: id={payment.id}, url={payment.confirmation.confirmation_url}"
#         )
#         return payment.id, payment.confirmation.confirmation_url
#     except Exception as e:
#         logger.error(f"Ошибка создания платежа: {str(e)}")
#         return None, None
#
#
# async def check_payment_status(payment_id: str) -> Optional[str]:
#     """
#     Проверка статуса платежа через YooKassa.
#
#     Args:
#         payment_id: ID платежа.
#
#     Returns:
#         Optional[str]: Статус платежа ('succeeded', 'canceled', etc.) или None при ошибке.
#     """
#     try:
#         payment = await asyncio.get_event_loop().run_in_executor(
#             None, Payment.find_one, payment_id
#         )
#         return payment.status
#     except Exception as e:
#         logger.error(f"Ошибка проверки статуса платежа {payment_id}: {str(e)}")
#         return None
"""
Конфигурация и вспомогательные функции для бота
"""
import os
import pytz
from pathlib import Path
from typing import Optional
from datetime import datetime

from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    UserProfilePhotos,
    File,
)

from utils.logger import get_logger

logger = get_logger(__name__)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_URL = "https://t.me/partacoworking"
RULES = "https://parta-works.ru/main_rules"


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
            [InlineKeyboardButton(text="📋 Правила коворкинга", url=RULES)],
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
        avatars_dir = "avatars"
        Path(avatars_dir).mkdir(exist_ok=True)

        # Формируем путь к файлу
        file_path = os.path.join(avatars_dir, f"{user_id}.jpg")

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
