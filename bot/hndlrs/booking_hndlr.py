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

from utils.api_client import get_api_client
from utils.logger import get_logger

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


def format_payment_notification(user, booking_data, status="SUCCESS") -> str:
    """Форматирует уведомление о платеже для администратора."""
    status_emojis = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "PENDING": "⏳",
        "CANCELLED": "🚫",
    }

    status_emoji = status_emojis.get(status, "❓")

    status_texts = {
        "SUCCESS": "ПЛАТЕЖ УСПЕШЕН",
        "FAILED": "ПЛАТЕЖ ОТКЛОНЕН",
        "PENDING": "ПЛАТЕЖ В ОЖИДАНИИ",
        "CANCELLED": "ПЛАТЕЖ ОТМЕНЕН",
    }

    status_text = status_texts.get(status, "НЕИЗВЕСТНЫЙ СТАТУС")

    message = f"""💳 <b>{status_text}</b> {status_emoji}

👤 <b>Клиент:</b> {user.full_name or 'Не указано'}
📞 <b>Телефон:</b> {user.phone or 'Не указано'}

💰 <b>Детали платежа:</b>
├ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽
├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
├ <b>Дата брони:</b> {booking_data.get('visit_date', '').strftime('%d.%m.%Y') if booking_data.get('visit_date') else 'Неизвестно'}
└ <b>Payment ID:</b> <code>{booking_data.get('payment_id', 'Неизвестно')}</code>

⏰ <i>Время: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def format_user_booking_notification(user, booking_data, confirmed: bool) -> str:
    """Форматирует уведомление о бронировании для пользователя."""
    tariff_emojis = {
        "опенспейс": "🏢",
        "переговорная": "🏛",
        "meeting": "🏛",
        "openspace": "🏢",
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
        datetime_str = f"{visit_date.strftime('%d.%m.%Y')} (весь день)"

    discount_info = ""
    if booking_data.get("promocode_name"):
        promocode_name = booking_data.get("promocode_name", "Неизвестный")
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    duration_info = ""
    if booking_data.get("duration"):
        duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"

    status_text = "Бронь подтверждена ✅" if confirmed else "Ожидайте подтверждения ⏳"
    status_instruction = (
        "\n\n💡 <b>Что дальше:</b> Ждем вас в назначенное время!"
        if confirmed
        else "\n\n💡 <b>Что дальше:</b> Администратор рассмотрит заявку и свяжется с вами."
    )

    message = f"""🎉 <b>Ваша бронь создана!</b> {tariff_emoji}

📋 <b>Детали брони:</b>
├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
├ <b>Дата и время:</b> {datetime_str}{duration_info}
└ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽{discount_info}

📌 <b>Статус:</b> {status_text}{status_instruction}

⏰ <i>Время создания: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def format_booking_notification(user, tariff, booking_data) -> str:
    """
    Форматирует уведомление о новом бронировании для админа (версия для бота)

    Args:
        user: словарь с данными пользователя
        tariff: словарь с данными тарифа
        booking_data: словарь с данными бронирования
    """
    tariff_emojis = {
        "coworking": "🏢",
        "meeting": "🤝",
        "переговорная": "🤝",
        "коворкинг": "🏢",
    }

    # Безопасное получение данных пользователя
    user_name = user.get("full_name") or "Не указано"
    user_phone = user.get("phone") or "Не указано"
    user_username = f"@{user.get('username')}" if user.get("username") else "Не указано"
    telegram_id = user.get("telegram_id", "Неизвестно")

    # Безопасное получение данных тарифа
    tariff_name = tariff.get("name", "Неизвестно")
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
        datetime_str = f"{date_str} (весь день)"

    # Информация о промокоде
    discount_info = ""
    promocode_name = booking_data.get("promocode_name")
    if promocode_name:
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    # Информация о длительности
    duration_info = ""
    duration = booking_data.get("duration")
    if duration:
        duration_info = f"\n⏱ <b>Длительность:</b> {duration} час(ов)"

    # Сумма
    amount = booking_data.get("amount", 0)

    message = f"""🎯 <b>НОВАЯ БРОНЬ!</b> {tariff_emoji}

👤 <b>Клиент:</b> {user_name}
📱 <b>Телефон:</b> {user_phone}
💬 <b>Telegram:</b> {user_username}
🆔 <b>ID:</b> {telegram_id}

📋 <b>Тариф:</b> {tariff_name}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}{discount_info}

💰 <b>Сумма:</b> {amount:.0f} ₽
✅ <b>Статус:</b> Оплачено, ожидает подтверждения"""

    return message


async def create_tariff_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Создаёт инлайн-клавиатуру с активными тарифами, исключая 'Тестовый день' для пользователей с успешными бронированиями."""
    api_client = await get_api_client()
    user = await api_client.get_user_by_telegram_id(telegram_id)
    tariffs = await api_client.get_active_tariffs()

    successful_bookings = user.get("successful_bookings", 0)

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

    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_date_keyboard() -> InlineKeyboardMarkup:
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
            date_str = f"Сегодня ({date_str})"
        elif i == 1:
            date_str = f"Завтра ({date_str})"

        buttons.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.row(buttons[i])

    keyboard.row(
        InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="back_to_tariffs")
    )
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_duration_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру выбора длительности от 1 до 8 часов."""
    keyboard = InlineKeyboardBuilder()

    # Группируем кнопки по 2 в ряд
    buttons = []
    for i in range(1, 9):  # От 1 до 8 часов
        discount_text = " (скидка 10%)" if i > 2 else ""
        buttons.append(
            InlineKeyboardButton(
                text=f"{i} час{'а' if i in [2, 3, 4] else 'ов' if i > 4 else ''}{discount_text}",
                callback_data=f"duration_{i}",
            )
        )

    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            keyboard.row(buttons[i], buttons[i + 1])
        else:
            keyboard.row(buttons[i])

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_time"))
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"))

    return keyboard.as_markup()


def create_payment_keyboard(
    confirmation_url: str, amount: float
) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопкой оплаты и отмены."""
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(text=f"💳 Оплатить {amount:.2f} ₽", url=confirmation_url)
    )
    keyboard.row(
        InlineKeyboardButton(text="❌ Отменить платеж", callback_data="cancel_payment")
    )

    return keyboard.as_markup()


def create_promocode_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для ввода промокода."""
    keyboard = InlineKeyboardBuilder()

    keyboard.add(
        InlineKeyboardButton(
            text="⏭ Пропустить промокод", callback_data="skip_promocode"
        )
    )
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking"))

    return keyboard.as_markup()


@router.callback_query(F.data == "book")
async def start_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработчик нажатия кнопки 'Забронировать'. Показывает активные тарифы."""
    await callback_query.answer()

    try:
        keyboard = await create_tariff_keyboard(callback_query.from_user.id)

        await callback_query.message.edit_text(
            "🎯 <b>Выберите тариф:</b>\n\n"
            "📌 Выберите подходящий тариф из списка ниже:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.SELECT_TARIFF)

    except Exception as e:
        logger.error(f"Ошибка при показе тарифов: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при загрузке тарифов. Попробуйте позже.",
            reply_markup=None,
        )


@router.callback_query(Booking.SELECT_TARIFF, F.data.startswith("tariff_"))
async def select_tariff(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка выбора тарифа. Показывает клавиатуру с датами."""
    await callback_query.answer()

    try:
        tariff_id = int(callback_query.data.split("_")[1])

        api_client = await get_api_client()
        tariff = await api_client.get_tariff(tariff_id)

        if not tariff:
            await callback_query.message.edit_text(
                "❌ Тариф не найден. Попробуйте снова.", reply_markup=None
            )
            return

        # Сохраняем данные тарифа в состоянии
        await state.update_data(
            tariff_id=tariff_id,
            tariff_name=tariff["name"],
            tariff_price=tariff["price"],
            tariff_purpose=tariff["purpose"],
            tariff_service_id=tariff.get("service_id"),
        )

        # Показываем календарь для выбора даты
        keyboard = create_date_keyboard()

        await callback_query.message.edit_text(
            f"📅 <b>Выберите дату для '{tariff['name']}':</b>\n\n"
            "📌 Выберите удобную дату из предложенных:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_DATE)

    except Exception as e:
        logger.error(f"Ошибка при выборе тарифа: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка. Попробуйте позже.", reply_markup=None
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
        tariff_purpose = data["tariff_purpose"]
        tariff_name = data["tariff_name"]

        if tariff_purpose and tariff_purpose.lower() in ["переговорная", "meeting"]:
            # Для переговорной комнаты запрашиваем время
            await callback_query.message.edit_text(
                f"⏰ <b>Введите время начала для '{tariff_name}':</b>\n\n"
                f"📅 Дата: {visit_date.strftime('%d.%m.%Y')}\n\n"
                "📌 Введите время в формате ЧЧ:ММ (например, 14:30):",
                parse_mode="HTML",
            )
            await state.set_state(Booking.ENTER_TIME)
        else:
            # Для опенспейса сразу переходим к промокоду
            keyboard = create_promocode_keyboard()
            await callback_query.message.edit_text(
                f"🎁 <b>Есть ли у вас промокод?</b>\n\n"
                f"📋 Тариф: {tariff_name}\n"
                f"📅 Дата: {visit_date.strftime('%d.%m.%Y')} (весь день)\n\n"
                "📌 Введите промокод или пропустите этот шаг:",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await state.set_state(Booking.ENTER_PROMOCODE)

    except Exception as e:
        logger.error(f"Ошибка при выборе даты: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка. Попробуйте позже.", reply_markup=None
        )


@router.message(Booking.ENTER_TIME)
async def process_time(message: Message, state: FSMContext) -> None:
    """Обработка введённого времени для 'Переговорной'. Запрашивает продолжительность."""
    try:
        visit_time = datetime.strptime(message.text, "%H:%M").time()

        await state.update_data(visit_time=visit_time)

        data = await state.get_data()
        tariff_name = data["tariff_name"]
        visit_date = data["visit_date"]

        # Показываем клавиатуру выбора длительности
        keyboard = create_duration_keyboard()

        await message.answer(
            f"⏱ <b>Выберите длительность для '{tariff_name}':</b>\n\n"
            f"📅 Дата: {visit_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Время: {visit_time.strftime('%H:%M')}\n\n"
            "📌 При аренде более 2 часов действует скидка 10%:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_DURATION)

    except ValueError:
        await message.answer(
            "❌ Неверный формат времени.\n\n"
            "📌 Введите время в формате ЧЧ:ММ (например, 14:30):"
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

        # Показываем ввод промокода
        keyboard = create_promocode_keyboard()

        await callback_query.message.edit_text(
            f"🎁 <b>Есть ли у вас промокод?</b>\n\n"
            f"📋 Тариф: {tariff_name}\n"
            f"📅 Дата: {visit_date.strftime('%d.%m.%Y')}\n"
            f"⏰ Время: {visit_time.strftime('%H:%M')}\n"
            f"⏱ Длительность: {duration} час{'а' if duration in [2, 3, 4] else 'ов' if duration > 4 else ''}\n\n"
            "📌 Введите промокод или пропустите этот шаг:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.ENTER_PROMOCODE)

    except Exception as e:
        logger.error(f"Ошибка при выборе длительности: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка. Попробуйте позже.", reply_markup=None
        )


@router.callback_query(F.data == "skip_promocode")
async def skip_promocode(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка пропуска промокода."""
    await callback_query.answer()
    await process_promocode_final(callback_query.message, state, None)


@router.message(Booking.ENTER_PROMOCODE)
async def process_promocode(message: Message, state: FSMContext) -> None:
    """Обработка введённого промокода или его пропуска. Создаёт платёж или бронь в зависимости от тарифа."""
    promocode_name = message.text.strip()
    await process_promocode_final(message, state, promocode_name)


async def process_promocode_final(
    message: Message, state: FSMContext, promocode_name: Optional[str]
) -> None:
    """Финальная обработка промокода и создание брони/платежа."""
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        user = await api_client.get_user_by_telegram_id(message.from_user.id)
        tariff_price = data["tariff_price"]
        tariff_purpose = data["tariff_purpose"]

        # Обработка промокода
        promocode_id: Optional[int] = None
        promocode_name_final: Optional[str] = None
        discount: float = 0

        if promocode_name:
            try:
                promocode = await api_client.get_promocode_by_name(promocode_name)
                if promocode:
                    discount = promocode.get("discount", 0)
                    promocode_id = promocode.get("id")
                    promocode_name_final = promocode.get("name")
                else:
                    await message.answer("❌ Промокод не найден или неактивен.")
                    return
            except Exception:
                await message.answer("❌ Ошибка при проверке промокода.")
                return

        # Расчет стоимости
        duration = data.get("duration")
        if duration:
            amount = tariff_price * duration
        else:
            amount = tariff_price

        # Скидка для пользователей с успешными бронированиями
        successful_bookings = user.get("successful_bookings", 0)
        if successful_bookings > 0 and data.get("tariff_service_id") != 47890:
            additional_discount = 10
            total_discount = min(100, discount + additional_discount)
        else:
            total_discount = discount

        # Скидка 10% для переговорных более 2 часов
        if duration and duration > 2:
            duration_discount = 10
            total_discount = min(100, total_discount + duration_discount)

        amount = amount * (1 - total_discount / 100)

        # Сохраняем данные для дальнейшего использования
        await state.update_data(
            amount=amount,
            promocode_id=promocode_id,
            promocode_name=promocode_name_final,
            discount=total_discount,
        )

        if tariff_purpose and tariff_purpose.lower() in ["переговорная", "meeting"]:
            # Для переговорной - создаем бронь без оплаты
            await create_booking_in_system(message, state, paid=False)
        elif amount <= 0:
            # Бесплатная бронь (100% скидка)
            await create_booking_in_system(message, state, paid=True)
        else:
            # Платная бронь - создаем платеж
            await create_payment_for_booking(message, state)

    except Exception as e:
        logger.error(f"Ошибка при обработке промокода: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке промокода. Попробуйте позже."
        )


async def create_payment_for_booking(message: Message, state: FSMContext) -> None:
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        # Получаем данные пользователя
        user = await api_client.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            return

        logger.info(f"Данные пользователя: {user}")

        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")
        tariff_service_id = data.get("tariff_service_id")

        # Создаем запись в Rubitime только если есть service_id и корректный телефон
        rubitime_id = None
        tariff_purpose = data.get("tariff_purpose", "").lower()

        if tariff_service_id:
            try:
                # Проверяем наличие и корректность телефона
                user_phone = user.get("phone", "")
                logger.info(f"Исходный телефон пользователя: '{user_phone}'")

                formatted_phone = format_phone_for_rubitime(user_phone)
                logger.info(f"Отформатированный телефон: '{formatted_phone}'")

                if (
                    not formatted_phone
                    or formatted_phone == "+7"
                    or len(formatted_phone) < 10
                ):
                    logger.warning(
                        f"Некорректный телефон для пользователя {user.get('id')}: '{user_phone}' -> '{formatted_phone}', пропускаем Rubitime"
                    )
                else:
                    if visit_time and duration:
                        # Для переговорной с конкретным временем
                        rubitime_date = datetime.combine(
                            visit_date, visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = duration * 60
                    else:
                        # Для коворкинга на весь день
                        rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        rubitime_duration = None

                    # УЛУЧШЕННЫЕ ПАРАМЕТРЫ с email и источником
                    # Формируем комментарий с информацией о промокоде
                    comment_parts = [
                        f"Бронь через Telegram бота - {data['tariff_name']}"
                    ]

                    # Добавляем информацию о промокоде если использован
                    promocode_name = data.get("promocode_name")
                    if promocode_name:
                        discount = data.get("discount", 0)
                        comment_parts.append(
                            f"Промокод: {promocode_name} (-{discount}%)"
                        )

                    # Добавляем информацию о скидке за длительность если есть
                    if duration and duration > 2:
                        comment_parts.append("Скидка за длительность: -10%")

                    final_comment = " | ".join(comment_parts)

                    # УЛУЧШЕННЫЕ ПАРАМЕТРЫ с email, источником и информацией о промокоде
                    rubitime_params = {
                        "service_id": tariff_service_id,
                        "date": rubitime_date,
                        "phone": formatted_phone,
                        "name": user.get("full_name", "Клиент"),
                        "comment": final_comment,  # Улучшенный комментарий
                        "source": "Telegram Bot",
                    }

                    # Добавляем duration только если он есть
                    if rubitime_duration is not None:
                        rubitime_params["duration"] = rubitime_duration

                    # Добавляем email если есть
                    user_email = user.get("email")
                    if user_email and user_email.strip():
                        rubitime_params["email"] = user_email.strip()
                        logger.info(
                            f"Добавлен email в параметры Rubitime: {user_email}"
                        )
                    else:
                        logger.info(
                            f"Email пользователя пустой или отсутствует: '{user_email}'"
                        )

                    logger.info(
                        f"Финальные параметры для Rubitime с промокодом: {rubitime_params}"
                    )
                    rubitime_id = await api_client.create_rubitime_record(
                        rubitime_params
                    )
                    logger.info(f"Результат создания записи Rubitime: {rubitime_id}")

            except Exception as e:
                logger.error(f"Ошибка создания записи Rubitime: {e}")
                # Продолжаем без rubitime_id
        else:
            logger.warning(
                f"Тариф без service_id ({tariff_service_id}), пропускаем создание записи Rubitime"
            )

        # Создаем бронирование
        booking_data = {
            "user_id": message.from_user.id,
            "tariff_id": data["tariff_id"],
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "visit_time": visit_time.strftime("%H:%M:%S") if visit_time else None,
            "duration": duration,
            "promocode_id": data.get("promocode_id"),
            "amount": data["amount"],
            "payment_id": data["payment_id"],
            "paid": True,
            "confirmed": False,
            "rubitime_id": rubitime_id,  # Передаем ID созданной записи
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
            user, updated_booking_data, confirmed=False
        )
        await message.answer(response_text, parse_mode="HTML")

        # Обновляем счетчик успешных бронирований
        try:
            current_bookings = user.get("successful_bookings", 0)
            await api_client.update_user(
                user["id"],  # Используем id вместо telegram_id
                {"successful_bookings": current_bookings + 1},
            )
            logger.info(f"Обновлен счетчик бронирований для пользователя {user['id']}")
        except Exception as e:
            logger.error(f"Ошибка обновления счетчика бронирований: {e}")

    except Exception as e:
        logger.error(f"Ошибка при создании бронирования: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке бронирования. Попробуйте позже."
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


async def create_booking_in_system(
    message: Message, state: FSMContext, paid: bool = False
) -> None:
    """Обработка бронирования без оплаты (для "Переговорной" или если сумма после скидки = 0)."""
    try:
        api_client = await get_api_client()
        data = await state.get_data()

        user = await api_client.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Ошибка: пользователь не найден")
            return

        tariff_service_id = data.get("tariff_service_id")
        visit_date = data["visit_date"]
        visit_time = data.get("visit_time")
        duration = data.get("duration")

        # Подготовка данных для Rubitime (только для опенспейса и оплаченных броней)
        rubitime_id = None
        tariff_purpose = data.get("tariff_purpose", "").lower()

        if paid or tariff_purpose in [
            "опенспейс",
            "openspace",
            "коворкинг",
            "coworking",
        ]:
            if tariff_service_id:  # Проверяем наличие service_id
                try:
                    if visit_time and duration:
                        # Для переговорной с указанным временем
                        rubitime_date = datetime.combine(
                            visit_date, visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = duration * 60  # В минутах
                    else:
                        # Для опенспейса (весь день)
                        rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        rubitime_duration = None

                    formatted_phone = format_phone_for_rubitime(user.get("phone", ""))

                    # Проверяем корректность телефона
                    if (
                        not formatted_phone
                        or formatted_phone == "+7"
                        or len(formatted_phone) < 10
                    ):
                        logger.warning(
                            f"Некорректный телефон для пользователя {user.get('id')}: '{user.get('phone')}' -> '{formatted_phone}', пропускаем Rubitime"
                        )
                    else:
                        # УЛУЧШЕННЫЕ ПАРАМЕТРЫ с email и источником
                        # Формируем комментарий с информацией о промокоде
                        comment_parts = [
                            f"Бронь через Telegram бота - {data['tariff_name']}"
                        ]

                        # Добавляем информацию о промокоде если использован
                        promocode_name = data.get("promocode_name")
                        if promocode_name:
                            discount = data.get("discount", 0)
                            comment_parts.append(
                                f"Промокод: {promocode_name} (-{discount}%)"
                            )

                        # Добавляем информацию о скидке за длительность если есть
                        if duration and duration > 2:
                            comment_parts.append("Скидка за длительность: -10%")

                        final_comment = " | ".join(comment_parts)

                        # УЛУЧШЕННЫЕ ПАРАМЕТРЫ с email, источником и информацией о промокоде
                        rubitime_params = {
                            "service_id": tariff_service_id,
                            "date": rubitime_date,
                            "phone": formatted_phone,
                            "name": user.get("full_name", "Клиент"),
                            "comment": final_comment,  # Улучшенный комментарий
                            "source": "Telegram Bot",
                        }

                        # Добавляем duration только если он есть
                        if rubitime_duration is not None:
                            rubitime_params["duration"] = rubitime_duration

                        # Добавляем email если есть
                        user_email = user.get("email")
                        if user_email and user_email.strip():
                            rubitime_params["email"] = user_email.strip()
                            logger.info(
                                f"Добавлен email в параметры Rubitime: {user_email}"
                            )
                        else:
                            logger.info(
                                f"Email пользователя пустой или отсутствует: '{user_email}'"
                            )

                        logger.info(
                            f"Финальные параметры для Rubitime с промокодом: {rubitime_params}"
                        )
                        rubitime_id = await api_client.create_rubitime_record(
                            rubitime_params
                        )
                        logger.info(
                            f"Результат создания записи Rubitime: {rubitime_id}"
                        )

                except Exception as e:
                    logger.error(f"Ошибка создания записи в Rubitime: {e}")
            else:
                logger.warning(
                    f"Тариф без service_id, пропускаем создание записи Rubitime"
                )

        # Создание брони в базе данных
        booking_data = {
            "user_id": message.from_user.id,  # Используем telegram_id
            "tariff_id": data["tariff_id"],
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "visit_time": visit_time.strftime("%H:%M:%S") if visit_time else None,
            "duration": duration,
            "promocode_id": data.get("promocode_id"),
            "amount": data.get("amount", 0),
            "paid": paid,
            "confirmed": paid,  # Автоподтверждение для оплаченных броней
            "rubitime_id": rubitime_id,
        }

        booking_result = await api_client.create_booking(booking_data)

        if not booking_result:
            await message.answer("❌ Ошибка при создании брони. Попробуйте позже.")
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

        # Отправка уведомления пользователю
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=paid
        )

        await message.answer(response_text, parse_mode="HTML")

        # Обновляем счетчик успешных бронирований для оплаченных броней
        if paid:
            try:
                current_bookings = user.get("successful_bookings", 0)
                await api_client.update_user(
                    user["id"],  # ИСПРАВЛЕНО: используем user["id"] вместо telegram_id
                    {"successful_bookings": current_bookings + 1},
                )
                logger.info(
                    f"Обновлен счетчик бронирований для пользователя {user['id']}"
                )
            except Exception as e:
                logger.error(f"Ошибка обновления счетчика бронирований: {e}")

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при создании брони: {e}")
        await message.answer(
            "❌ Произошла ошибка при создании брони. Попробуйте позже."
        )


async def poll_payment_status(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверка статуса платежа с ограничением по времени."""
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
                payment_status = await api_client.check_payment_status(payment_id)
                status = payment_status.get("status")

                if status == "succeeded":
                    # Платеж успешен - создаем бронь
                    await create_booking_in_system(message, state, paid=True)

                    # Получаем данные пользователя для уведомления
                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    # Отправка уведомления администратору об успешном платеже
                    booking_data = await state.get_data()
                    payment_notification = format_payment_notification(
                        user, booking_data, "SUCCESS"
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
                    # Платеж отменен
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=payment_message_id,
                        text="❌ <b>Платеж отменен</b>\n\n"
                        "Вы можете попробовать забронировать снова.",
                        parse_mode="HTML",
                    )

                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    booking_data = await state.get_data()
                    payment_notification = format_payment_notification(
                        user, booking_data, "CANCELLED"
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
                    # Платеж не прошел
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=payment_message_id,
                        text="❌ <b>Платеж не прошел</b>\n\n"
                        "Попробуйте использовать другую карту или способ оплаты.",
                        parse_mode="HTML",
                    )

                    if not user:
                        user = await api_client.get_user_by_telegram_id(
                            message.from_user.id
                        )

                    booking_data = await state.get_data()
                    payment_notification = format_payment_notification(
                        user, booking_data, "FAILED"
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
                text="⏰ <b>Время ожидания платежа истекло</b>\n\n"
                "Если оплата прошла, свяжитесь с поддержкой.",
                parse_mode="HTML",
            )
        except Exception:
            pass

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка в процессе проверки платежа: {e}")
        await state.clear()


@router.callback_query(Booking.STATUS_PAYMENT, F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка отмены платежа."""
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
            "❌ <b>Платеж отменен</b>\n\n" "Вы можете попробовать забронировать снова.",
            parse_mode="HTML",
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при отмене платежа: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при отмене платежа.", parse_mode="HTML"
        )


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка отмены бронирования."""
    await callback_query.answer()

    await callback_query.message.edit_text(
        "❌ Бронирование отменено.\n\n"
        "Возвращайтесь, когда будете готовы забронировать!",
        reply_markup=None,
    )

    await state.clear()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору тарифов."""
    await callback_query.answer()

    try:
        keyboard = await create_tariff_keyboard(callback_query.from_user.id)

        await callback_query.message.edit_text(
            "🎯 <b>Выберите тариф:</b>\n\n"
            "📌 Выберите подходящий тариф из списка ниже:",
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        await state.set_state(Booking.SELECT_TARIFF)

    except Exception as e:
        logger.error(f"Ошибка при возврате к тарифам: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка. Попробуйте позже.", reply_markup=None
        )


@router.callback_query(F.data == "back_to_time")
async def back_to_time(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к вводу времени."""
    await callback_query.answer()

    data = await state.get_data()
    tariff_name = data.get("tariff_name", "")
    visit_date = data.get("visit_date")

    if visit_date:
        await callback_query.message.edit_text(
            f"⏰ <b>Введите время начала для '{tariff_name}':</b>\n\n"
            f"📅 Дата: {visit_date.strftime('%d.%m.%Y')}\n\n"
            "📌 Введите время в формате ЧЧ:ММ (например, 14:30):",
            parse_mode="HTML",
        )
        await state.set_state(Booking.ENTER_TIME)


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка нажатия кнопки 'Главное меню' в состояниях бронирования."""
    await callback_query.answer()

    await callback_query.message.edit_text(
        "🏠 Возвращаемся в главное меню...", reply_markup=None
    )

    await state.clear()


def register_book_handlers(dp) -> None:
    """Регистрация обработчиков бронирования."""
    dp.include_router(router)
