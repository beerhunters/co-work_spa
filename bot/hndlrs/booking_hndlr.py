import os
import re
import pytz
import asyncio
from datetime import datetime, timedelta, date, time
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import create_user_keyboard
from utils.api_client import get_api_client
from utils.logger import get_logger
from bot.utils.localization import get_text, get_button_text, pluralize_hours

logger = get_logger(__name__)
router = Router()

MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")


class Booking(StatesGroup):
    SELECT_TARIFF = State()
    ENTER_DATE = State()
    ENTER_TIME = State()
    ENTER_DURATION = State()
    ENTER_PROMOCODE = State()
    PAYMENT = State()
    STATUS_PAYMENT = State()


def format_payment_notification(user, booking_data, status="SUCCESS", lang="ru") -> str:
    """Форматирует уведомление о платеже для администратора."""
    status_emojis = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "PENDING": "⏳",
        "CANCELLED": "🚫",
    }

    status_emoji = status_emojis.get(status, "❓")

    status_texts = {
        "SUCCESS": get_text(lang, "booking.payment_success"),
        "FAILED": get_text(lang, "booking.payment_failed"),
        "PENDING": get_text(lang, "booking.payment_pending"),
        "CANCELLED": get_text(lang, "booking.payment_cancelled"),
    }

    status_text = status_texts.get(status, get_text(lang, "booking.payment_unknown"))

    # Правильное форматирование даты
    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    if visit_date:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            try:
                if isinstance(visit_date, str):
                    date_obj = datetime.strptime(visit_date, "%Y-%m-%d").date()
                    date_str = date_obj.strftime("%d.%m.%Y")
                else:
                    date_str = str(visit_date)
            except:
                date_str = get_text(lang, "booking.date_unknown")
    else:
        date_str = get_text(lang, "booking.date_unknown")

    # Добавляем время если есть
    if visit_time:
        if hasattr(visit_time, "strftime"):
            time_str = f" в {visit_time.strftime('%H:%M')}"
        else:
            try:
                if isinstance(visit_time, str):
                    time_obj = datetime.strptime(visit_time, "%H:%M:%S").time()
                    time_str = f" в {time_obj.strftime('%H:%M')}"
                else:
                    time_str = ""
            except:
                time_str = ""
    else:
        time_str = ""

    full_date_str = date_str + time_str

    # Добавляем информацию о длительности
    duration = booking_data.get("duration")
    duration_str = f" ({duration}ч)" if duration else ""

    message = f"""💳 <b>{status_text}</b> {status_emoji}

👤 <b>{get_text(lang, 'booking.admin_notification.client')}</b> {user.get('full_name') or get_text(lang, 'booking.admin_notification.not_specified')}
📞 <b>{get_text(lang, 'booking.admin_notification.phone')}</b> {user.get('phone') or get_text(lang, 'booking.admin_notification.not_specified')}

💰 <b>{get_text(lang, 'booking.admin_notification.payment_details')}</b>
├ <b>{get_text(lang, 'booking.amount_label')}</b> {booking_data.get('amount', 0):.2f} ₽
├ <b>{get_text(lang, 'booking.tariff_label')}</b> {booking_data.get('tariff_name', get_text(lang, 'booking.admin_notification.unknown'))}
├ <b>{get_text(lang, 'booking.admin_notification.booking_date')}</b> {full_date_str}{duration_str}
└ <b>{get_text(lang, 'booking.admin_notification.payment_id')}</b> <code>{booking_data.get('payment_id', get_text(lang, 'booking.admin_notification.unknown'))}</code>

⏰ <i>{get_text(lang, 'booking.admin_notification.time')} {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def format_user_booking_notification(user, booking_data, confirmed: bool, lang="ru") -> str:
    """Форматирует уведомление о бронировании для пользователя."""
    tariff_emojis = {
        "опенспейс": "🏢",
        "переговорная": "🏛",
        "meeting": "🏛",
        "openspace": "🏢",
        "coworking": "🏢",
    }

    purpose = booking_data.get("tariff_purpose", "").lower()
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    if isinstance(visit_date, str):
        visit_date = datetime.fromisoformat(visit_date).date()

    if visit_time and isinstance(visit_time, str):
        visit_time = datetime.strptime(visit_time, "%H:%M:%S").time()

    if visit_time:
        datetime_str = (
            f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
        )
    else:
        datetime_str = f"{visit_date.strftime('%d.%m.%Y')} {get_text(lang, 'booking.all_day')}"

    discount_info = ""
    if booking_data.get("promocode_name"):
        promocode_name = booking_data.get("promocode_name", get_text(lang, "booking.unknown_promocode"))
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>{get_text(lang, 'booking.promocode_label')}</b> {promocode_name} (-{discount}%)"

    duration_info = ""
    if booking_data.get("duration"):
        duration = booking_data['duration']
        duration_info = f"\n⏱ <b>{get_text(lang, 'booking.duration_label')}</b> {duration} {pluralize_hours(duration, lang)}"

    status_text = get_text(lang, "booking.booking_confirmed") if confirmed else get_text(lang, "booking.booking_pending")
    status_instruction = (
        get_text(lang, "booking.next_steps_confirmed")
        if confirmed
        else get_text(lang, "booking.next_steps_pending")
    )

    message = f"""{get_text(lang, 'booking.your_booking_created')} {tariff_emoji}

{get_text(lang, 'booking.booking_details')}
├ <b>{get_text(lang, 'booking.tariff_label')}</b> {booking_data.get('tariff_name', get_text(lang, 'booking.admin_notification.unknown'))}
├ <b>{get_text(lang, 'booking.admin_new_booking.date_time')}</b> {datetime_str}{duration_info}
└ <b>{get_text(lang, 'booking.amount_label')}</b> {booking_data.get('amount', 0):.2f} ₽{discount_info}

📌 <b>{get_text(lang, 'booking.status_label')}</b> {status_text}{status_instruction}

⏰ <i>{get_text(lang, 'booking.creation_time')} {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def format_booking_notification(user, tariff, booking_data, lang="ru") -> str:
    """
    Форматирует уведомление о новом бронировании для админа (версия для бота)

    Args:
        user: словарь с данными пользователя
        tariff: словарь с данными тарифа
        booking_data: словарь с данными бронирования
        lang: язык уведомления (по умолчанию "ru")
    """
    tariff_emojis = {
        "coworking": "🏢",
        "meeting": "🤝",
        "переговорная": "🤝",
        "коворкинг": "🏢",
    }

    # Безопасное получение данных пользователя
    user_name = user.get("full_name") or get_text(lang, "booking.admin_notification.not_specified")
    user_phone = user.get("phone") or get_text(lang, "booking.admin_notification.not_specified")
    user_username = f"@{user.get('username')}" if user.get("username") else get_text(lang, "booking.admin_notification.not_specified")
    telegram_id = user.get("telegram_id", get_text(lang, "booking.admin_notification.unknown"))

    # Безопасное получение данных тарифа
    tariff_name = tariff.get("name", get_text(lang, "booking.admin_notification.unknown"))
    tariff_purpose = tariff.get("purpose", "")

    purpose = tariff_purpose.lower() if tariff_purpose else ""
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    # Форматирование даты и времени
    if visit_time:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            # Если visit_date - строка
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)

        if hasattr(visit_time, "strftime"):
            time_str = visit_time.strftime("%H:%M")
        else:
            # Если visit_time - строка
            try:
                time_obj = datetime.strptime(str(visit_time), "%H:%M:%S").time()
                time_str = time_obj.strftime("%H:%M")
            except:
                time_str = str(visit_time)

        datetime_str = f"{date_str} в {time_str}"
    else:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)
        datetime_str = f"{date_str} {get_text(lang, 'booking.all_day')}"

    # Информация о промокоде
    discount_info = ""
    promocode_name = booking_data.get("promocode_name")
    if promocode_name:
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>{get_text(lang, 'booking.promocode_label')}</b> {promocode_name} (-{discount}%)"

    # Информация о длительности
    duration_info = ""
    duration = booking_data.get("duration")
    if duration:
        duration_info = f"\n⏱ <b>{get_text(lang, 'booking.duration_label')}</b> {duration} {pluralize_hours(duration, lang)}"

    # Сумма
    amount = booking_data.get("amount", 0)

    message = f"""{get_text(lang, 'booking.admin_new_booking.title')} {tariff_emoji}

👤 <b>{get_text(lang, 'booking.admin_new_booking.client')}</b> {user_name}
📱 <b>{get_text(lang, 'booking.admin_new_booking.phone')}</b> {user_phone}
💬 <b>{get_text(lang, 'booking.admin_new_booking.telegram')}</b> {user_username}
🆔 <b>{get_text(lang, 'booking.admin_new_booking.telegram_id')}</b> {telegram_id}

📋 <b>{get_text(lang, 'booking.tariff_label')}</b> {tariff_name}
📅 <b>{get_text(lang, 'booking.admin_new_booking.date_time')}</b> {datetime_str}{duration_info}{discount_info}

💰 <b>{get_text(lang, 'booking.amount_label')}</b> {amount:.0f} ₽
✅ <b>{get_text(lang, 'booking.admin_new_booking.status_paid')}</b>"""

    return message


async def create_tariff_keyboard(telegram_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Создаёт инлайн-клавиатуру с активными тарифами, исключая 'Тестовый день' для пользователей с успешными бронированиями."""
    api_client = await get_api_client()

    # ИСПРАВЛЕНО: добавляем обработку ошибки получения пользователя
    try:
        user = await api_client.get_user_by_telegram_id(telegram_id)
        successful_bookings = user.get("successful_bookings", 0) if user else 0
    except Exception as e:
        logger.warning(f"Не удалось получить данные пользователя {telegram_id}: {e}")
        successful_bookings = 0

    tariffs = await api_client.get_active_tariffs()

    keyboard = InlineKeyboardBuilder()

    for tariff in tariffs:
        tariff_id = tariff.get("id")
        tariff_name = tariff.get("name")
        tariff_price = tariff.get("price")
        service_id = tariff.get("service_id")

        # Скрываем "Тестовый день" (service_id 47890) если есть успешные бронирования
        if service_id == 47890 and successful_bookings > 0:
            continue

        button_text = f"{tariff_name} - {tariff_price}₽"
        keyboard.row(
            InlineKeyboardButton(text=button_text, callback_data=f"tariff_{tariff_id}")
        )

    keyboard.row(InlineKeyboardButton(text=get_button_text(lang, "booking.cancel"), callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_date_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Создаёт инлайн-клавиатуру с датами (сегодня + 7 дней)."""
    today = datetime.now(MOSCOW_TZ).date()
    keyboard = InlineKeyboardBuilder()

    # Группируем кнопки по 2 в ряд
    buttons = []
    for i in range(8):  # Сегодня + 7 дней
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m")
        callback_data = f"date_{date.strftime('%Y-%m-%d')}"

        if i == 0:
            date_str = f"{get_text(lang, 'booking.today')} ({date_str})"
        elif i == 1:
            date_str = f"{get_text(lang, 'booking.tomorrow')} ({date_str})"

        buttons.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.row(buttons[i])

    keyboard.row(
        InlineKeyboardButton(text=get_button_text(lang, "booking.back_to_tariffs"), callback_data="back_to_tariffs")
    )
    keyboard.row(InlineKeyboardButton(text=get_button_text(lang, "booking.cancel"), callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_duration_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Создаёт клавиатуру выбора длительности от 1 до 8 часов."""
    keyboard = InlineKeyboardBuilder()

    # Группируем кнопки по 2 в ряд
    buttons = []
    for i in range(1, 9):  # От 1 до 8 часов
        discount_text = f" {get_text(lang, 'booking.discount_10_percent')}" if i > 2 else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{i} {pluralize_hours(i, lang)}{discount_text}",
                callback_data=f"duration_{i}",
            )
        )

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.row(buttons[i])

    keyboard.row(InlineKeyboardButton(text=get_button_text(lang, "booking.back"), callback_data="back_to_time"))
    keyboard.row(InlineKeyboardButton(text=get_button_text(lang, "booking.cancel"), callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_payment_keyboard(
    confirmation_url: str, amount: float, lang: str = "ru"
) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопкой оплаты и отмены."""
    keyboard = InlineKeyboardBuilder()
    pay_text_template = get_button_text(lang, "booking.pay")
    pay_text = pay_text_template.format(amount=f"{amount:.0f}")
    # keyboard.add(
    #     InlineKeyboardButton(text=get_button_text(lang, "booking.pay", amount=f"{amount:.0f}"), url=confirmation_url)
    # )
    keyboard.add(
        InlineKeyboardButton(text=pay_text, url=confirmation_url)
    )
    keyboard.row(
        InlineKeyboardButton(text=get_button_text(lang, "booking.cancel_payment"), callback_data="cancel_payment")
    )

    return keyboard.as_markup()


def create_promocode_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Создает клавиатуру для ввода промокода."""
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text=get_button_text(lang, "booking.skip_promocode"), callback_data="skip_promocode"
        )
    )
    keyboard.row(InlineKeyboardButton(text=get_button_text(lang, "booking.cancel"), callback_data="cancel_booking"))

    return keyboard.as_markup()


@router.callback_query(F.data == "book")
async def start_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработчик нажатия кнопки 'Забронировать'. Показывает активные тарифы."""
    await callback_query.answer()

    lang = "ru"  # Default language
    try:
        keyboard = await create_tariff_keyboard(callback_query.from_user.id)

        await callback_query.message.edit_text(
            f"{get_text(lang, 'booking.select_tariff_title')}\n\n"
            f"{get_text(lang, 'booking.select_tariff_description')}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.SELECT_TARIFF)

    except Exception as e:
        logger.error(f"Ошибка при показе тарифов: {e}")
        await callback_query.message.edit_text(
            get_text(lang, "booking.tariffs_load_error"),
            reply_markup=None,
        )


@router.callback_query(Booking.SELECT_TARIFF, F.data.startswith("tariff_"))
async def select_tariff(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора тарифа. Показывает клавиатуру с датами."""
    await callback_query.answer()

    lang = callback_query.from_user.language_code or "ru"

    try:
        tariff_id = int(callback_query.data.split("_")[1])

        api_client = await get_api_client()
        tariff = await api_client.get_tariff(tariff_id)

        if not tariff:
            await callback_query.message.edit_text(
                get_text(lang, "booking.tariff_not_found"), reply_markup=None
            )
            return

        # Сохраняем данные тарифа в состоянии
        await state.update_data(
            tariff_id=tariff_id,
            tariff_name=tariff["name"],
            tariff_price=tariff["price"],
            tariff_purpose=tariff["purpose"],
            tariff_service_id=tariff.get("service_id"),
            lang=lang,
        )

        # Показываем календарь для выбора даты
        keyboard = create_date_keyboard()

        await callback_query.message.edit_text(
            get_text(lang, "booking.select_date_title", tariff_name=tariff['name']) + "\n\n" +
            get_text(lang, "booking.select_date_description"),
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_DATE)

    except Exception as e:
        logger.error(f"Ошибка при выборе тарифа: {e}")
        await callback_query.message.edit_text(
            get_text(lang, "booking.general_error"), reply_markup=None
        )


@router.callback_query(Booking.ENTER_DATE, F.data.startswith("date_"))
async def select_date(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора даты через инлайн-клавиатуру."""
    await callback_query.answer()

    try:
        date_str = callback_query.data.split("_")[1]
        visit_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        await state.update_data(visit_date=visit_date)

        data = await state.get_data()
        tariff_purpose = data.get("tariff_purpose", "").lower()
        tariff_name = data["tariff_name"]
        lang = data.get("lang", "ru")

        # ИСПРАВЛЕНО: правильная логика определения типа тарифа
        if tariff_purpose in ["переговорная", "meeting_room", "meeting"]:
            # Для переговорной комнаты запрашиваем время
            await callback_query.message.edit_text(
                get_text(lang, "booking.enter_time_title", tariff_name=tariff_name) + "\n\n" +
                get_text(lang, "booking.enter_time_date", date=visit_date.strftime('%d.%m.%Y')) + "\n\n" +
                get_text(lang, "booking.enter_time_format"),
                parse_mode="HTML",
            )
            await state.set_state(Booking.ENTER_TIME)
        else:
            # Для опенспейса сразу переходим к промокоду
            keyboard = create_promocode_keyboard(lang)
            await callback_query.message.edit_text(
                get_text(lang, "booking.promocode_question") + "\n\n" +
                f"📋 {get_text(lang, 'booking.tariff_label')} {tariff_name}\n" +
                f"📅 {get_text(lang, 'booking.date_label')} {visit_date.strftime('%d.%m.%Y')} {get_text(lang, 'booking.all_day')}\n\n" +
                get_text(lang, "booking.enter_promocode_or_skip"),
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await state.set_state(Booking.ENTER_PROMOCODE)

    except Exception as e:
        logger.error(f"Ошибка при выборе даты: {e}")
        data = await state.get_data()
        lang = data.get("lang", "ru")
        await callback_query.message.edit_text(
            get_text(lang, "booking.general_error"), reply_markup=None
        )


@router.message(Booking.ENTER_TIME)
async def process_time(message: Message, state: FSMContext) -> None:
    """Обработка введённого времени для 'Переговорной'. Запрашивает продолжительность."""
    data = await state.get_data()
    lang = data.get("lang", "ru")

    try:
        visit_time = datetime.strptime(message.text, "%H:%M").time()

        await state.update_data(visit_time=visit_time)

        tariff_name = data["tariff_name"]
        visit_date = data["visit_date"]

        # ИСПРАВЛЕНО: для переговорной ВСЕГДА показываем клавиатуру выбора длительности
        keyboard = create_duration_keyboard(lang)

        await message.answer(
            get_text(lang, "booking.select_duration_title", tariff_name=tariff_name) + "\n\n" +
            f"📅 {get_text(lang, 'booking.date_label')} {visit_date.strftime('%d.%m.%Y')}\n" +
            f"⏰ {get_text(lang, 'booking.time_label')} {visit_time.strftime('%H:%M')}\n\n" +
            get_text(lang, "booking.discount_info"),
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_DURATION)

    except ValueError:
        await message.answer(
            get_text(lang, "booking.time_invalid_format") + "\n\n" +
            get_text(lang, "booking.enter_time_format")
        )


@router.callback_query(Booking.ENTER_DURATION, F.data.startswith("duration_"))
async def select_duration(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора длительности."""
    await callback_query.answer()

    try:
        duration = int(callback_query.data.split("_")[1])

        await state.update_data(duration=duration)

        data = await state.get_data()
        tariff_name = data["tariff_name"]
        visit_date = data["visit_date"]
        visit_time = data["visit_time"]
        lang = data.get("lang", "ru")

        # Показываем ввод промокода
        keyboard = create_promocode_keyboard(lang)

        await callback_query.message.edit_text(
            get_text(lang, "booking.promocode_question") + "\n\n" +
            f"📋 {get_text(lang, 'booking.tariff_label')} {tariff_name}\n" +
            f"📅 {get_text(lang, 'booking.date_label')} {visit_date.strftime('%d.%m.%Y')}\n" +
            f"⏰ {get_text(lang, 'booking.time_label')} {visit_time.strftime('%H:%M')}\n" +
            f"⏱ {get_text(lang, 'booking.duration_label')} {duration} {pluralize_hours(duration, lang)}\n\n" +
            get_text(lang, "booking.enter_promocode_or_skip"),
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_PROMOCODE)

    except Exception as e:
        logger.error(f"Ошибка при выборе длительности: {e}")
        data = await state.get_data()
        lang = data.get("lang", "ru")
        await callback_query.message.edit_text(
            get_text(lang, "booking.general_error"), reply_markup=None
        )


@router.callback_query(Booking.ENTER_PROMOCODE, F.data == "skip_promocode")
async def skip_promocode(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка пропуска промокода."""
    await callback_query.answer()

    # Создаем объект-обертку для совместимости с process_promocode_final
    class MessageWrapper:
        def __init__(self, callback_query):
            self.from_user = callback_query.from_user
            self.chat = callback_query.message.chat
            self.bot = callback_query.bot

        def answer(self, *args, **kwargs):
            return callback_query.message.answer(*args, **kwargs)

    message_wrapper = MessageWrapper(callback_query)
    await process_promocode_final(message_wrapper, state, None)


@router.message(Booking.ENTER_PROMOCODE)
async def process_promocode(message: Message, state: FSMContext) -> None:
    """Обработка введённого промокода или его пропуска. Создаёт платёж или бронь в зависимости от тарифа."""
    promocode_name = message.text.strip()
    await process_promocode_final(message, state, promocode_name)


async def process_promocode_final(
    message: Message, state: FSMContext, promocode_name: Optional[str]
) -> None:
    """Финальная обработка промокода и создание брони/платежа."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        # Получение пользователя
        try:
            user = await api_client.get_user_by_telegram_id(message.from_user.id)
            if not user:
                logger.error(f"Пользователь {message.from_user.id} не найден в БД")
                await message.answer(
                    get_text(lang, "booking.user_not_found_admin")
                )
                return
        except Exception as e:
            logger.error(f"Ошибка получения пользователя {message.from_user.id}: {e}")
            await message.answer(
                get_text(lang, "booking.user_data_error")
            )
            return

        tariff_price = data["tariff_price"]
        tariff_purpose = data.get("tariff_purpose", "").lower()

        # Обработка промокода
        promocode_id: Optional[int] = None
        promocode_name_final: Optional[str] = None
        promocode_discount: float = 0

        if promocode_name:
            try:
                promocode = await api_client.get_promocode_by_name(promocode_name)
                if promocode:
                    promocode_discount = promocode.get("discount", 0)
                    promocode_id = promocode.get("id")
                    promocode_name_final = promocode.get("name")
                else:
                    await message.answer(get_text(lang, "booking.promocode_not_found"))
                    return
            except Exception as e:
                logger.error(f"Ошибка проверки промокода: {e}")
                await message.answer(get_text(lang, "booking.promocode_error"))
                return

        # ИСПРАВЛЕННАЯ ЛОГИКА расчета стоимости
        duration = data.get("duration")

        # Базовая стоимость
        if duration:
            base_amount = tariff_price * duration
        else:
            base_amount = tariff_price

        logger.info(
            f"Базовая стоимость: {base_amount}, тариф: {tariff_price}, длительность: {duration}"
        )

        # Собираем все скидки
        total_discount = 0
        discount_details = []

        # Скидка по промокоду
        if promocode_discount > 0:
            total_discount += promocode_discount
            discount_details.append(
                f"промокод {promocode_name_final}: -{promocode_discount}%"
            )

        # Скидка за длительность для переговорных более 2 часов
        if duration and duration > 2:
            duration_discount = 10
            total_discount += duration_discount
            discount_details.append(
                f"длительность более 2 часов: -{duration_discount}%"
            )

        # # Скидка для постоянных пользователей (исключая тестовый день)
        # successful_bookings = user.get("successful_bookings", 0)
        # if successful_bookings > 0 and data.get("tariff_service_id") != 47890:
        #     loyal_discount = 10
        #     total_discount += loyal_discount
        #     discount_details.append(f"постоянный клиент: -{loyal_discount}%")

        # Ограничиваем максимальную скидку до 100%
        total_discount = min(100, total_discount)

        # Рассчитываем финальную стоимость
        final_amount = base_amount * (1 - total_discount / 100)

        logger.info(f"Применённые скидки: {discount_details}")
        logger.info(
            f"Общая скидка: {total_discount}%, финальная стоимость: {final_amount}"
        )

        # Сохраняем данные для дальнейшего использования
        await state.update_data(
            amount=final_amount,
            promocode_id=promocode_id,
            promocode_name=promocode_name_final,
            discount=total_discount,
        )

        # Логика по типам тарифов
        if tariff_purpose in ["переговорная", "meeting_room", "meeting"]:
            # Для переговорной - создаем бронь без оплаты, ожидает подтверждения админа
            await create_booking_without_payment(message, state, user)
        elif final_amount <= 0:
            # Бесплатная бронь (100% скидка) - создаем и подтверждаем
            await create_booking_with_confirmation(message, state, user)
        else:
            # Платная бронь для опенспейса - создаем платеж
            await create_payment_for_booking(message, state, user)

    except Exception as e:
        logger.error(f"Ошибка при обработке промокода: {e}")
        await message.answer(
            get_text(lang, "booking.promocode_processing_error")
        )


async def create_payment_for_booking(
    message: Message, state: FSMContext, user: dict
) -> None:
    """Создание платежа для опенспейса."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()
        amount = data["amount"]
        tariff_name = data["tariff_name"]

        logger.info(
            f"Создание платежа для пользователя {message.from_user.id}, сумма: {amount}"
        )

        # Проверяем, что сумма больше 0
        if amount <= 0:
            logger.warning(f"Попытка создать платеж с суммой {amount}")
            await create_booking_with_confirmation(message, state, user)
            return

        # Формируем описание платежа
        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")

        if visit_time and duration:
            description = get_text(
                lang,
                "booking.payment_description_with_time",
                tariff_name=tariff_name,
                date=visit_date.strftime('%d.%m.%Y'),
                time=visit_time.strftime('%H:%M'),
                duration=duration
            )
        else:
            description = get_text(
                lang,
                "booking.payment_description_all_day",
                tariff_name=tariff_name,
                date=visit_date.strftime('%d.%m.%Y')
            )

        # Создаем платеж через API
        payment_data = {
            "user_id": message.from_user.id,
            "tariff_id": data["tariff_id"],
            "amount": amount,
            "description": description,
        }

        payment_result = await api_client.create_payment(payment_data)

        if not payment_result or not payment_result.get("payment_id"):
            await message.answer(get_text(lang, "booking.payment_create_error"))
            return

        payment_id = payment_result["payment_id"]
        confirmation_url = payment_result["confirmation_url"]

        # Сохраняем данные платежа
        await state.update_data(payment_id=payment_id)

        # Отправляем сообщение с кнопкой оплаты
        payment_keyboard = create_payment_keyboard(confirmation_url, amount, lang)
        payment_message = await message.answer(
            get_text(lang, "booking.payment_title") + "\n\n" +
            f"📋 {description}\n" +
            f"{get_text(lang, 'booking.amount_to_pay')} <b>{amount:.2f} ₽</b>\n\n" +
            get_text(lang, "booking.click_to_pay"),
            reply_markup=payment_keyboard,
            parse_mode="HTML",
        )

        # Сохраняем ID сообщения для последующего редактирования
        await state.update_data(payment_message_id=payment_message.message_id)
        await state.set_state(Booking.STATUS_PAYMENT)

        # Запускаем отслеживание статуса платежа
        task = asyncio.create_task(poll_payment_status(message, state, bot=message.bot))
        await state.update_data(payment_task=task)

        logger.info(f"Платеж создан: {payment_id}, сумма: {amount}")

    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {e}")
        await message.answer(
            get_text(lang, "booking.payment_create_error")
        )


async def poll_payment_status(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверка статуса платежа с ограничением по времени."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        payment_id = data["payment_id"]
        payment_message_id = data["payment_message_id"]

        max_attempts = 60  # 5 минут (60 * 5 секунд)
        delay = 5
        user = None

        for attempt in range(max_attempts):
            try:
                # Проверяем статус платежа через API
                payment_status_result = await api_client.check_payment_status(
                    payment_id
                )
                status = payment_status_result.get("status", "pending")

                logger.info(
                    f"Проверка платежа {payment_id}, попытка {attempt + 1}, статус: {status}"
                )

                if status == "succeeded":
                    # Платеж успешен - создаем бронь
                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    # ВАЖНО: Получаем данные состояния ДО создания брони (до очистки состояния)
                    booking_data = await state.get_data()

                    # Логирование для отладки
                    logger.info(f"Данные состояния ДО создания брони: {booking_data}")

                    # Дополняем данные для уведомления о платеже
                    payment_data = {
                        "amount": booking_data.get("amount", 0),
                        "tariff_name": booking_data.get("tariff_name", get_text(lang, "booking.admin_notification.unknown")),
                        "visit_date": booking_data.get("visit_date"),
                        "visit_time": booking_data.get("visit_time"),
                        "duration": booking_data.get("duration"),
                        "promocode_name": booking_data.get("promocode_name"),
                        "discount": booking_data.get("discount", 0),
                        "payment_id": payment_id,
                    }

                    logger.info(f"Данные для payment_notification: {payment_data}")

                    # Создаем подтвержденную бронь после успешной оплаты
                    await create_booking_after_payment(message, state, user)

                    # Отправка уведомления администратору об успешном платеже (ПОСЛЕ создания брони)
                    payment_notification = format_payment_notification(
                        user, payment_data, "SUCCESS"
                    )

                    if ADMIN_TELEGRAM_ID:
                        await bot.send_message(
                            chat_id=ADMIN_TELEGRAM_ID,
                            text=payment_notification,
                            parse_mode="HTML",
                        )

                    # Удаляем сообщение с кнопкой оплаты
                    try:
                        await bot.delete_message(
                            chat_id=message.chat.id, message_id=payment_message_id
                        )
                    except Exception:
                        pass

                    return

                elif status in ["canceled", "cancelled"]:
                    # Получаем данные состояния ДО очистки
                    booking_data = await state.get_data()

                    # Платеж отменен
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=payment_message_id,
                        text=get_text(lang, 'booking.payment_cancelled_text') + get_text(lang, 'booking.try_again_payment'),
                        parse_mode="HTML",
                    )

                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    payment_data = {
                        "amount": booking_data.get("amount", 0),
                        "tariff_name": booking_data.get("tariff_name", get_text(lang, "booking.admin_notification.unknown")),
                        "visit_date": booking_data.get("visit_date"),
                        "visit_time": booking_data.get("visit_time"),
                        "duration": booking_data.get("duration"),
                        "promocode_name": booking_data.get("promocode_name"),
                        "discount": booking_data.get("discount", 0),
                        "payment_id": payment_id,
                    }
                    payment_notification = format_payment_notification(
                        user, payment_data, "CANCELLED"
                    )

                    if ADMIN_TELEGRAM_ID:
                        await bot.send_message(
                            chat_id=ADMIN_TELEGRAM_ID,
                            text=payment_notification,
                            parse_mode="HTML",
                        )

                    await state.clear()
                    return

                elif status == "failed":
                    # Получаем данные состояния ДО очистки
                    booking_data = await state.get_data()

                    # Платеж не прошел
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=payment_message_id,
                        text=get_text(lang, 'booking.payment_failed_text') + get_text(lang, 'booking.try_other_card'),
                        parse_mode="HTML",
                    )

                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    payment_data = {
                        "amount": booking_data.get("amount", 0),
                        "tariff_name": booking_data.get("tariff_name", get_text(lang, "booking.admin_notification.unknown")),
                        "visit_date": booking_data.get("visit_date"),
                        "visit_time": booking_data.get("visit_time"),
                        "duration": booking_data.get("duration"),
                        "promocode_name": booking_data.get("promocode_name"),
                        "discount": booking_data.get("discount", 0),
                        "payment_id": payment_id,
                    }
                    payment_notification = format_payment_notification(
                        user, payment_data, "FAILED"
                    )

                    if ADMIN_TELEGRAM_ID:
                        await bot.send_message(
                            chat_id=ADMIN_TELEGRAM_ID,
                            text=payment_notification,
                            parse_mode="HTML",
                        )

                    await state.clear()
                    return

                # Платеж еще в процессе - ждем
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Ошибка проверки статуса платежа: {e}")
                await asyncio.sleep(delay)

        # Время вышло - уведомляем об этом
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=payment_message_id,
                text=get_text(lang, 'booking.payment_timeout') + get_text(lang, 'booking.contact_support_payment'),
                parse_mode="HTML",
            )
        except Exception:
            pass

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в процессе проверки платежа: {e}")
        await state.clear()


async def create_booking_after_payment(
    message: Message, state: FSMContext, user: dict
) -> None:
    """Создание бронирования после успешной оплаты."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        logger.info(f"Создание брони после оплаты для пользователя: {user}")

        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")
        tariff_service_id = data.get("tariff_service_id")

        # Создаем запись в Rubitime
        rubitime_id = None

        if tariff_service_id:
            try:
                user_phone = user.get("phone", "")
                formatted_phone = format_phone_for_rubitime(user_phone)

                if formatted_phone and len(formatted_phone) >= 10:
                    if visit_time and duration:
                        rubitime_date = datetime.combine(
                            visit_date, visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = duration * 60
                    else:
                        rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        rubitime_duration = None

                    comment_parts = [
                        f"Оплаченная бронь через Telegram бота - {data['tariff_name']}"
                    ]

                    promocode_name = data.get("promocode_name")
                    if promocode_name:
                        discount = data.get("discount", 0)
                        comment_parts.append(
                            f"Промокод: {promocode_name} (-{discount}%)"
                        )

                    if duration and duration > 2:
                        comment_parts.append("Скидка за длительность: -10%")

                    final_comment = " | ".join(comment_parts)

                    rubitime_params = {
                        "service_id": tariff_service_id,
                        "date": rubitime_date,
                        "phone": formatted_phone,
                        "name": user.get("full_name", "Клиент"),
                        "comment": final_comment,
                        "source": "Telegram Bot",
                    }

                    if rubitime_duration is not None:
                        rubitime_params["duration"] = rubitime_duration

                    user_email = user.get("email")
                    if user_email and user_email.strip():
                        rubitime_params["email"] = user_email.strip()

                    rubitime_id = await api_client.create_rubitime_record(
                        rubitime_params
                    )
                    logger.info(f"Результат создания записи Rubitime: {rubitime_id}")

            except Exception as e:
                logger.error(f"Ошибка создания записи Rubitime: {e}")

        # Создаем бронирование
        booking_data = {
            "user_id": message.from_user.id,
            "tariff_id": data["tariff_id"],
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "visit_time": visit_time.strftime("%H:%M:%S") if visit_time else None,
            "duration": duration,
            "promocode_id": data.get("promocode_id"),
            "amount": data["amount"],
            "payment_id": data.get("payment_id"),
            "paid": True,
            "confirmed": True,  # Автоподтверждение для оплаченных броней
            "rubitime_id": rubitime_id,
        }

        booking_result = await api_client.create_booking(booking_data)
        logger.info(f"Создано бронирование: {booking_result}")

        # Обновляем данные для уведомления
        updated_booking_data = {
            **data,
            "rubitime_id": rubitime_id,
            "booking_id": booking_result.get("id"),
        }

        # Получаем тариф для уведомления
        tariff = await api_client.get_tariff(data["tariff_id"])

        # Отправляем уведомление админу
        try:
            admin_message = format_booking_notification(
                user, tariff, updated_booking_data
            )
            await message.bot.send_message(
                chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
            )
            logger.info("Уведомление админу отправлено успешно")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")

        # Отправляем подтверждение пользователю
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=True
        )
        await message.answer(response_text, parse_mode="HTML")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при создании бронирования после оплаты: {e}")
        await message.answer(
            get_text(lang, "booking.booking_create_error")
        )


async def create_booking_without_payment(
    message: Message, state: FSMContext, user: dict
) -> None:
    """Создание бронирования переговорной без оплаты - ожидает подтверждения админа."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")
        tariff_service_id = data.get("tariff_service_id")

        # Для переговорной НЕ создаем запись в Rubitime до подтверждения админом
        rubitime_id = None

        # Создание брони в базе данных
        booking_data = {
            "user_id": message.from_user.id,
            "tariff_id": data["tariff_id"],
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "visit_time": visit_time.strftime("%H:%M:%S") if visit_time else None,
            "duration": duration,
            "promocode_id": data.get("promocode_id"),
            "amount": data.get("amount", 0),
            "paid": False,
            "confirmed": False,  # Ожидает подтверждения админа
            "rubitime_id": rubitime_id,
        }

        booking_result = await api_client.create_booking(booking_data)

        if not booking_result:
            await message.answer(get_text(lang, "booking.booking_create_error"))
            return

        # Подготовка данных для уведомлений
        updated_booking_data = {
            "tariff_name": data["tariff_name"],
            "tariff_purpose": data["tariff_purpose"],
            "visit_date": visit_date,
            "visit_time": visit_time,
            "duration": duration,
            "amount": data.get("amount", 0),
            "promocode_name": data.get("promocode_name"),
            "discount": data.get("discount", 0),
        }

        # Отправка уведомления администратору
        try:
            tariff = await api_client.get_tariff(data["tariff_id"])
            admin_message = format_booking_notification(
                user, tariff, updated_booking_data
            )

            if ADMIN_TELEGRAM_ID:
                await message.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
                )
                logger.info("Уведомление админу отправлено успешно")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")

        # Отправка уведомления пользователю - ожидает подтверждения
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=False
        )

        await message.answer(response_text, parse_mode="HTML")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при создании брони переговорной: {e}")
        await message.answer(
            get_text(lang, "booking.booking_create_error")
        )


async def create_booking_with_confirmation(
    message: Message, state: FSMContext, user: dict
) -> None:
    """Создание бесплатного бронирования с автоподтверждением."""
    lang = message.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")
        tariff_service_id = data.get("tariff_service_id")

        # Создаем запись в Rubitime для бесплатных броней
        rubitime_id = None

        if tariff_service_id:
            try:
                user_phone = user.get("phone", "")
                formatted_phone = format_phone_for_rubitime(user_phone)

                if formatted_phone and len(formatted_phone) >= 10:
                    if visit_time and duration:
                        rubitime_date = datetime.combine(
                            visit_date, visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = duration * 60
                    else:
                        rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        rubitime_duration = None

                    comment_parts = [
                        f"Бесплатная бронь через Telegram бота - {data['tariff_name']}"
                    ]

                    promocode_name = data.get("promocode_name")
                    if promocode_name:
                        discount = data.get("discount", 0)
                        comment_parts.append(
                            f"Промокод: {promocode_name} (-{discount}%)"
                        )

                    final_comment = " | ".join(comment_parts)

                    rubitime_params = {
                        "service_id": tariff_service_id,
                        "date": rubitime_date,
                        "phone": formatted_phone,
                        "name": user.get("full_name", "Клиент"),
                        "comment": final_comment,
                        "source": "Telegram Bot",
                    }

                    if rubitime_duration is not None:
                        rubitime_params["duration"] = rubitime_duration

                    user_email = user.get("email")
                    if user_email and user_email.strip():
                        rubitime_params["email"] = user_email.strip()

                    rubitime_id = await api_client.create_rubitime_record(
                        rubitime_params
                    )
                    logger.info(f"Результат создания записи Rubitime: {rubitime_id}")

            except Exception as e:
                logger.error(f"Ошибка создания записи в Rubitime: {e}")

        # Создание брони в базе данных
        booking_data = {
            "user_id": message.from_user.id,
            "tariff_id": data["tariff_id"],
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "visit_time": visit_time.strftime("%H:%M:%S") if visit_time else None,
            "duration": duration,
            "promocode_id": data.get("promocode_id"),
            "amount": 0,  # Бесплатно
            "paid": True,  # Считается оплаченным (бесплатно)
            "confirmed": True,  # Автоподтверждение
            "rubitime_id": rubitime_id,
        }

        booking_result = await api_client.create_booking(booking_data)

        if not booking_result:
            await message.answer(get_text(lang, "booking.booking_create_error"))
            return

        # Подготовка данных для уведомлений
        updated_booking_data = {
            "tariff_name": data["tariff_name"],
            "tariff_purpose": data["tariff_purpose"],
            "visit_date": visit_date,
            "visit_time": visit_time,
            "duration": duration,
            "amount": 0,
            "promocode_name": data.get("promocode_name"),
            "discount": data.get("discount", 0),
        }

        # Отправка уведомления администратору
        try:
            tariff = await api_client.get_tariff(data["tariff_id"])
            admin_message = format_booking_notification(
                user, tariff, updated_booking_data
            )

            if ADMIN_TELEGRAM_ID:
                await message.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode="HTML"
                )
                logger.info("Уведомление админу отправлено успешно")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу: {e}")

        # Отправка уведомления пользователю - подтверждено
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=True
        )

        await message.answer(response_text, parse_mode="HTML")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при создании бесплатной брони: {e}")
        await message.answer(
            get_text(lang, "booking.booking_create_error")
        )


def format_phone_for_rubitime(phone: str) -> str:
    """Форматирует номер телефона для Rubitime в формате +7**********."""
    if not phone:
        return "Не указано"

    # Извлекаем только цифры
    digits = re.sub(r"[^0-9]", "", phone)

    if len(digits) == 11 and digits.startswith("8"):
        # Заменяем 8 на 7
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        # Добавляем 7 в начало
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("7"):
        # Уже правильный формат
        pass
    else:
        return "Не указано"

    if len(digits) == 11:
        return "+" + digits
    else:
        return "Не указано"


@router.callback_query(Booking.STATUS_PAYMENT, F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка отмены платежа."""
    lang = callback_query.from_user.language_code or "ru"
    await callback_query.answer()

    try:
        data = await state.get_data()
        payment_id = data.get("payment_id")
        payment_message_id = data.get("payment_message_id")
        payment_task = data.get("payment_task")

        # Отменяем задачу проверки платежа
        if payment_task and not payment_task.done():
            payment_task.cancel()

        # Отменяем платеж через API
        if payment_id:
            try:
                api_client = await get_api_client()
                await api_client.cancel_payment(payment_id)
            except Exception as e:
                logger.error(f"Ошибка отмены платежа: {e}")

        await callback_query.message.edit_text(
            get_text(lang, "booking.payment_cancelled_full"),
            parse_mode="HTML",
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при отмене платежа: {e}")
        await callback_query.message.edit_text(
            get_text(lang, "booking.payment_create_error"), parse_mode="HTML"
        )


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка отмены бронирования."""
    await callback_query.answer()
    user_language = callback_query.from_user.language_code or "ru"
    await callback_query.message.edit_text(
        get_text(user_language, "booking.booking_cancelled"),
        reply_markup=create_user_keyboard(user_language),
        parse_mode="HTML",
    )

    await state.clear()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору тарифов."""
    lang = callback_query.from_user.language_code or "ru"
    await callback_query.answer()

    try:
        keyboard = await create_tariff_keyboard(callback_query.from_user.id)

        await callback_query.message.edit_text(
            f"{get_text(lang, 'booking.select_tariff_title')}\n\n{get_text(lang, 'booking.select_tariff_description')}",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.SELECT_TARIFF)

    except Exception as e:
        logger.error(f"Ошибка при возврате к тарифам: {e}")
        await callback_query.message.edit_text(
            get_text(lang, "booking.general_error"), reply_markup=None
        )


@router.callback_query(F.data == "back_to_time")
async def back_to_time(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к вводу времени."""
    lang = callback_query.from_user.language_code or "ru"
    await callback_query.answer()

    data = await state.get_data()
    tariff_name = data.get("tariff_name", "")
    visit_date = data.get("visit_date")

    if visit_date:
        await callback_query.message.edit_text(
            f"{get_text(lang, 'booking.enter_time_title', tariff_name=tariff_name)}\n\n"
            f"{get_text(lang, 'booking.enter_time_date', date=visit_date.strftime('%d.%m.%Y'))}\n\n"
            f"{get_text(lang, 'booking.enter_time_format')}",
            parse_mode="HTML",
        )
        await state.set_state(Booking.ENTER_TIME)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка нажатия кнопки 'Главное меню' в состояниях бронирования."""
    lang = callback_query.from_user.language_code or "ru"
    await callback_query.answer()

    await callback_query.message.edit_text(
        get_text(lang, "booking.returning_main_menu"), reply_markup=None
    )

    await state.clear()


def register_book_handlers(dp) -> None:
    """Регистрация обработчиков бронирования."""
    dp.include_router(router)
