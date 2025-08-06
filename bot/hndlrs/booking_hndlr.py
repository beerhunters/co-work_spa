from typing import Optional
from aiogram import Router, F, Dispatcher
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from datetime import datetime, timedelta, date, time
from models.models import (
    get_user_by_telegram_id,
    get_active_tariffs,
    get_promocode_by_name,
    create_booking,
    Session,
    format_booking_notification,
    User,
    Promocode,
)
from bot.config import rubitime, check_payment_status
import os
import re
import asyncio
from yookassa import Payment, Refund
from utils.logger import get_logger
import pytz

router = Router()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
logger = get_logger(__name__)


class Booking(StatesGroup):
    SELECT_TARIFF = State()
    ENTER_DATE = State()
    ENTER_TIME = State()
    ENTER_DURATION = State()
    ENTER_PROMOCODE = State()
    PAYMENT = State()
    STATUS_PAYMENT = State()


def format_payment_notification(user, booking_data, status="SUCCESS") -> str:
    """Форматирует уведомление о статусе платежа.

    Args:
        user: Объект пользователя.
        booking_data: Данные бронирования.
        status: Статус платежа.

    Returns:
        Форматированное сообщение для уведомления.
    """
    status_emojis = {
        "SUCCESS": "✅",
        "PENDING": "⏳",
        "FAILED": "❌",
        "CANCELLED": "🚫",
    }
    status_texts = {
        "SUCCESS": "Платёж успешно проведён",
        "PENDING": "Платёж в обработке",
        "FAILED": "Платёж не удался",
        "CANCELLED": "Платёж отменён",
    }
    status_emoji = status_emojis.get(status, "❓")
    status_text = status_texts.get(status, "НЕИЗВЕСТНЫЙ СТАТУС")
    message = f"""💳 <b>{status_text}</b> {status_emoji}
👤 <b>Клиент:</b> {user.full_name or 'Не указано'} (@{user.username or 'не указан'})
📋 <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
💰 <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽
🔗 <b>Payment ID:</b> <code>{booking_data.get('payment_id', 'Неизвестно')}</code>"""
    return message.strip()


def format_user_booking_notification(user, booking_data, confirmed: bool) -> str:
    """Форматирует уведомление для пользователя о брони.

    Args:
        user: Объект пользователя.
        booking_data: Данные бронирования.
        confirmed: Флаг подтверждения брони.

    Returns:
        Форматированное сообщение для пользователя.
    """
    tariff_emojis = {
        "meeting": "🤝",
        "workspace": "💼",
        "event": "🎉",
        "office": "🏢",
        "coworking": "💻",
    }
    purpose = booking_data.get("tariff_purpose", "").lower()
    tariff_emoji = tariff_emojis.get(purpose, "📋")
    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")
    datetime_str = (
        f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
        if visit_time
        else f"{visit_date.strftime('%d.%m.%Y')} (весь день)"
    )
    discount_info = ""
    promocode_name = booking_data.get("promocode_name", "Неизвестный")
    discount = booking_data.get("discount", 0)
    if discount > 0:
        discount_info = (
            f"\n💰 <b>Скидка:</b> {discount}% (промокод: <code>{promocode_name}</code>)"
        )
    duration_info = ""
    if booking_data.get("duration"):
        duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"
    status_text = "Бронь подтверждена ✅" if confirmed else "Ожидайте подтверждения ⏳"
    status_instruction = (
        "\n\nℹ️ <b>Следующий шаг:</b> Дождитесь подтверждения администратором."
        if not confirmed
        else ""
    )
    message = f"""🎉 <b>Ваша бронь создана!</b> {tariff_emoji}
📋 <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}
💰 <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽{discount_info}
📌 <b>Статус:</b> {status_text}{status_instruction}"""
    return message.strip()


def create_tariff_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с доступными тарифами.

    Args:
        telegram_id: Telegram ID пользователя.

    Returns:
        InlineKeyboardMarkup с кнопками тарифов.

    Сложность: O(n), где n — количество активных тарифов.
    """
    user = get_user_by_telegram_id(telegram_id)
    successful_bookings = user.successful_bookings if user else 0
    tariffs = get_active_tariffs()
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{tariff.name} ({tariff.price} ₽)",
                callback_data=f"tariff_{tariff.id}",
            )
        ]
        for tariff in tariffs
    ]
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def create_date_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с датами для бронирования.

    Returns:
        InlineKeyboardMarkup с кнопками дат.

    Сложность: O(1), так как создается фиксированное количество кнопок (7 дней).
    """
    today = datetime.now(MOSCOW_TZ).date()
    buttons = []
    for i in range(7):
        date = today + timedelta(days=i)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=date.strftime("%d.%m.%Y"),
                    callback_data=f"date_{date.strftime('%Y-%m-%d')}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Обрабатывает выбор тарифа.

    Args:
        callback_query: Объект callback-запроса.
        state: Контекст FSM.

    Сложность: O(n), где n — количество активных тарифов (поиск тарифа).
    """
    tariff_id = int(callback_query.data.split("_")[1])
    tariffs = get_active_tariffs()
    tariff = next((t for t in tariffs if t.id == tariff_id), None)
    if not tariff:
        await callback_query.message.answer("Тариф не найден.")
        return
    await state.update_data(
        tariff_id=tariff.id,
        tariff_name=tariff.name,
        tariff_price=tariff.price,
        tariff_purpose=tariff.purpose,
        tariff_service_id=tariff.service_id,
    )
    await callback_query.message.answer("Введите дату визита (ГГГГ-ММ-ДД):")
    await state.set_state(Booking.ENTER_DATE)


@router.message(Booking.ENTER_DATE)
async def process_date(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод даты визита.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    try:
        visit_date = datetime.strptime(message.text, "%Y-%m-%d").date()
        await state.update_data(visit_date=visit_date)
        data = await state.get_data()
        tariff_purpose = data["tariff_purpose"]
        if tariff_purpose.lower() == "переговорная":
            await message.answer("Введите время визита (ЧЧ:ММ):")
            await state.set_state(Booking.ENTER_TIME)
        else:
            await message.answer("Введите промокод (или нажмите /skip):")
            await state.set_state(Booking.ENTER_PROMOCODE)
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ГГГГ-ММ-ДД.")


@router.message(Booking.ENTER_TIME)
async def process_time(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод времени визита.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    try:
        visit_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(visit_time=visit_time)
        await message.answer("Введите длительность в часах:")
        await state.set_state(Booking.ENTER_DURATION)
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ.")


@router.message(Booking.ENTER_DURATION)
async def process_duration(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод длительности.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    try:
        duration = int(message.text)
        if duration <= 0:
            raise ValueError("Длительность должна быть положительным числом.")
        await state.update_data(duration=duration)
        await message.answer("Введите промокод (или нажмите /skip):")
        await state.set_state(Booking.ENTER_PROMOCODE)
    except ValueError:
        await message.answer("Введите положительное число для длительности.")


@router.message(Booking.ENTER_PROMOCODE)
async def process_promocode(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод промокода.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1) для получения промокода и вычислений.
    """
    data = await state.get_data()
    tariff_price = data["tariff_price"]
    promocode_id: Optional[int] = None
    promocode_name: Optional[str] = None
    discount: float = 0
    if message.text != "/skip":
        promocode_name = message.text.strip()
        promocode = get_promocode_by_name(promocode_name)
        if promocode and promocode.is_active:
            discount = promocode.discount
            promocode_id = promocode.id
        else:
            await message.answer(
                "Промокод недействителен. Продолжить без промокода? Нажмите /skip."
            )
            return
    duration = data.get("duration")
    amount = tariff_price * duration if duration else tariff_price
    if discount > 0:
        amount = amount * (1 - discount / 100)
    additional_discount = 10 if data.get("successful_bookings", 0) >= 5 else 0
    total_discount = min(100, discount + additional_discount)
    amount = amount * (1 - total_discount / 100)
    await state.update_data(
        amount=amount,
        promocode_id=promocode_id,
        promocode_name=promocode_name,
        discount=total_discount,
    )
    description = f"Бронь: {data['tariff_name']}, дата: {data['visit_date']}"
    try:
        payment = await Payment.create(
            {
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": "https://example.com/return",
                },
                "description": description,
            }
        )
        await state.update_data(
            payment_id=payment.id, payment_url=payment.confirmation.confirmation_url
        )
        payment_message = await message.answer(
            f"Оплатите бронь: {amount:.2f} ₽\nСсылка: {payment.confirmation.confirmation_url}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Отмена", callback_data="cancel_payment"
                        )
                    ]
                ]
            ),
        )
        await state.update_data(payment_message_id=payment_message.message_id)
        task = asyncio.create_task(poll_payment_status(message, state, bot=message.bot))
        await state.update_data(payment_task=task)
        await state.set_state(Booking.STATUS_PAYMENT)
    except Exception as e:
        logger.error(f"Ошибка при создании платежа: {str(e)}")
        await message.answer("Ошибка при создании платежа. Попробуйте снова.")
        await state.clear()


def format_phone_for_rubitime(phone: str) -> str:
    """Форматирует номер телефона для Rubitime.

    Args:
        phone: Номер телефона.

    Returns:
        Отформатированный номер телефона.

    Сложность: O(n), где n — длина строки телефона.
    """
    digits = re.sub(r"[^0-9]", "", phone)
    return f"+{digits}"


@router.message(Booking.PAYMENT)
async def process_payment(message: Message, state: FSMContext) -> None:
    """Обрабатывает создание брони после оплаты.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1) для операций с базой данных и API.
    """
    data = await state.get_data()
    tariff_id = data["tariff_id"]
    tariff_service_id = data["tariff_service_id"]
    visit_date = data["visit_date"]
    visit_time = data.get("visit_time")
    duration = data.get("duration")
    amount = data["amount"]
    promocode_id = data.get("promocode_id")
    promocode_name = data.get("promocode_name", "-")
    discount = data.get("discount", 0)
    payment_id = data["payment_id"]
    session = Session()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("Пользователь не найден.")
            return
        promocode = (
            session.query(Promocode).filter_by(id=promocode_id).first()
            if promocode_id
            else None
        )
        rubitime_date = (
            datetime.combine(visit_date, visit_time).strftime("%Y-%m-%d %H:%M:%S")
            if visit_time
            else visit_date.strftime("%Y-%m-%d") + " 09:00:00"
        )
        rubitime_duration = duration * 60 if duration else None
        formatted_phone = format_phone_for_rubitime(user.phone or "Не указано")
        rubitime_params = {
            "service_id": tariff_service_id,
            "date": rubitime_date,
            "phone": formatted_phone,
            "duration": rubitime_duration,
        }
        rubitime_id = await rubitime("create_record", rubitime_params)
        booking, admin_message, session = create_booking(
            telegram_id=message.from_user.id,
            tariff_id=tariff_id,
            visit_date=visit_date,
            visit_time=visit_time,
            duration=duration,
            promocode_id=promocode_id,
            amount=amount,
            payment_id=payment_id,
            paid=False,
            confirmed=False,
        )
        if not booking:
            await message.answer(admin_message)
            return
        updated_booking_data = {
            "tariff_name": data["tariff_name"],
            "tariff_purpose": data["tariff_purpose"],
            "visit_date": visit_date,
            "visit_time": visit_time,
            "duration": duration,
            "amount": amount,
            "promocode_name": promocode_name,
            "discount": discount,
            "rubitime_id": rubitime_id,
            "payment_id": payment_id,
        }
        admin_message = format_booking_notification(
            user, booking.tariff, updated_booking_data
        )
        await message.bot.send_message(
            ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
        )
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=False
        )
        await message.answer(response_text, parse_mode="HTML")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при создании брони: {str(e)}")
        await message.answer("Ошибка при создании брони. Попробуйте снова.")
    finally:
        if session:
            session.close()


async def poll_payment_status(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверяет статус платежа через Yookassa.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        bot: Экземпляр бота.

    Сложность: O(k), где k — количество попыток проверки статуса (max_attempts).
    """
    data = await state.get_data()
    payment_id = data["payment_id"]
    payment_message_id = data["payment_message_id"]
    max_attempts = 60
    delay = 5
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        if not user:
            await bot.send_message(message.chat.id, "Пользователь не найден.")
            return
        for attempt in range(max_attempts):
            status = await check_payment_status(payment_id)
            if status == "succeeded":
                session = Session()
                try:
                    booking = (
                        session.query(Booking).filter_by(payment_id=payment_id).first()
                    )
                    if booking:
                        booking.paid = True
                        booking.confirmed = True
                        user.successful_bookings += 1
                        session.commit()
                        payment_notification = format_payment_notification(
                            user, data, status="SUCCESS"
                        )
                        await bot.send_message(
                            ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
                        )
                        await bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=payment_message_id,
                            text=format_user_booking_notification(
                                user, data, confirmed=True
                            ),
                            parse_mode="HTML",
                        )
                        await state.clear()
                    break
                finally:
                    session.close()
            elif status == "canceled" or status == "failed":
                payment_notification = format_payment_notification(
                    user, data, status="FAILED"
                )
                await bot.send_message(
                    ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
                )
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=payment_message_id,
                    text="Платёж не удался. Попробуйте снова.",
                    parse_mode="HTML",
                )
                await state.clear()
                break
            await asyncio.sleep(delay)
        else:
            payment_notification = format_payment_notification(
                user, data, status="FAILED"
            )
            await bot.send_message(
                ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
            )
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=payment_message_id,
                text="Время ожидания платежа истекло.",
                parse_mode="HTML",
            )
            await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при проверке статуса платежа {payment_id}: {str(e)}")
        await bot.send_message(message.chat.id, "Ошибка при проверке платежа.")
        await state.clear()


@router.callback_query(Booking.STATUS_PAYMENT, F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает отмену платежа.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    data = await state.get_data()
    payment_id = data.get("payment_id")
    payment_message_id = data.get("payment_message_id")
    payment_task = data.get("payment_task")
    user = get_user_by_telegram_id(callback_query.from_user.id)
    if not user:
        await callback_query.message.answer("Пользователь не найден.")
        return
    try:
        if payment_task:
            payment_task.cancel()
        if payment_id:
            refund = Refund.create(
                {
                    "payment_id": payment_id,
                    "amount": {"value": f"{data['amount']:.2f}", "currency": "RUB"},
                    "description": "Отмена брони",
                }
            )
        payment_notification = format_payment_notification(
            user, data, status="CANCELLED"
        )
        await callback_query.message.bot.send_message(
            ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
        )
        await callback_query.message.bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=payment_message_id,
            text="Платёж отменён.",
            parse_mode="HTML",
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отмене платежа {payment_id}: {str(e)}")
        await callback_query.message.answer("Ошибка при отмене платежа.")


@router.callback_query(F.data == "cancel")
async def cancel_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Отменяет процесс бронирования.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await state.clear()
    await callback_query.message.answer("Бронирование отменено.")


def register_book_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики бронирования.

    Args:
        dp: Dispatcher бота.

    Сложность: O(1).
    """
    dp.include_router(router)
