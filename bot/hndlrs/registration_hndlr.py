import re
from typing import Optional
from aiogram import Router, F, Dispatcher, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart
from datetime import datetime
import os
from models.models import (
    check_and_add_user,
    get_user_by_telegram_id,
    add_user,
    Session,
    # format_registration_notification,
)
import pytz
from utils.logger import get_logger

router = Router()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/partacoworking")
INVITE_LINK = os.getenv("INVITE_LINK", "https://t.me/partacoworking")
GROUP_ID = os.getenv("GROUP_ID", "-100123456789")
logger = get_logger(__name__)


def format_registration_notification(user, referrer_info=None) -> str:
    """Форматирует уведомление о новом пользователе.

    Args:
        user: Объект пользователя.
        referrer_info: Информация о реферере (если есть).

    Returns:
        Форматированное сообщение.

    Сложность: O(1).
    """
    referrer_text = ""
    if referrer_info:
        referrer_text = f"""
👥 <b>Реферер:</b>
├ <b>Имя:</b> {referrer_info['full_name'] or 'Не указано'}
└ <b>Telegram:</b> @{referrer_info['username'] or 'не указан'} (ID: <code>{referrer_info['telegram_id']}</code>)"""
    message = f"""🎉 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ!</b>
👤 <b>Данные:</b>
├ <b>Имя:</b> {user.full_name or 'Не указано'}
├ <b>Телефон:</b> {user.phone or 'Не указано'}
├ <b>Email:</b> {user.email or 'Не указано'}
└ <b>Telegram:</b> @{user.username or 'не указан'} (ID: <code>{user.telegram_id}</code>){referrer_text}
⏰ <i>Время регистрации: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""
    return message.strip()


def create_register_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для начала регистрации.

    Returns:
        InlineKeyboardMarkup с кнопкой.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Начать регистрацию", callback_data="start_registration"
                )
            ]
        ]
    )
    return keyboard


def create_agreement_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для согласия с правилами.

    Returns:
        InlineKeyboardMarkup с кнопками.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Согласен", callback_data="agree_to_terms")],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
        ]
    )
    return keyboard


def create_invite_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с приглашением в группу.

    Returns:
        InlineKeyboardMarkup с кнопками.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Присоединиться к группе", url="https://t.me/partacowo"
                )
            ],
            [InlineKeyboardButton(text="Информация", callback_data="info")],
            [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")],
        ]
    )
    return keyboard


class Registration(StatesGroup):
    agreement = State()
    full_name = State()
    phone = State()
    email = State()


welcome_message = (
    "Добро пожаловать в коворкинг Parta! ✨\n"
    "Для продолжения, пожалуйста, зарегистрируйтесь."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обрабатывает команду /start.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    user_id = message.from_user.id
    text_parts = message.text.split(maxsplit=1)
    ref_id = None
    if len(text_parts) > 1 and text_parts[1].isdigit():
        ref_id = int(text_parts[1])
    try:
        user, is_complete = check_and_add_user(
            user_id, message.from_user.username, ref_id
        )
        if is_complete:
            await message.answer(
                "Вы уже зарегистрированы!", reply_markup=create_invite_keyboard()
            )
            return
        full_name = user.full_name or "Пользователь"
        welcome_text = welcome_message
        if ref_id:
            referrer = get_user_by_telegram_id(ref_id)
            referrer_username = (
                referrer.username if referrer else "неизвестный пользователь"
            )
            welcome_text += f"\n\nВы были приглашены @{referrer_username}."
        await message.answer(welcome_text, reply_markup=create_register_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при обработке /start для {user_id}: {str(e)}")
        await message.answer("Произошла ошибка. Попробуйте снова.")


@router.callback_query(F.data == "start_registration")
async def start_registration(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс регистрации.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await callback_query.message.answer(
        "Ознакомьтесь с правилами: https://parta-works.ru/main_rules\nСогласны ли вы?",
        reply_markup=create_agreement_keyboard(),
    )
    await state.set_state(Registration.agreement)


@router.callback_query(F.data == "agree_to_terms")
async def agree_to_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает согласие с правилами.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    user_id = callback_query.from_user.id
    try:
        user = get_user_by_telegram_id(user_id)
        if user:
            user.agreed_to_terms = True
            session = Session()
            session.add(user)
            session.commit()
            session.close()
        await callback_query.message.answer("Введите ваше ФИО:")
        await state.set_state(Registration.full_name)
    except Exception as e:
        logger.error(f"Ошибка при согласии с правилами для {user_id}: {str(e)}")
        await callback_query.message.answer("Произошла ошибка. Попробуйте снова.")


@router.message(Registration.agreement)
async def handle_invalid_agreement(message: Message, state: FSMContext) -> None:
    """Обрабатывает неверный ввод на этапе согласия.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await message.answer(
        "Пожалуйста, согласитесь с правилами, нажав кнопку.",
        reply_markup=create_agreement_keyboard(),
    )


@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод ФИО.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    full_name = message.text.strip()
    if not full_name:
        await message.answer("ФИО не может быть пустым.")
        return
    await state.update_data(full_name=full_name)
    await message.answer("Введите ваш номер телефона:")
    await state.set_state(Registration.phone)


@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод номера телефона.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    phone = message.text.strip()
    if not re.match(r"^\+?\d{10,15}$", phone):
        await message.answer("Неверный формат телефона. Используйте +7XXXXXXXXXX.")
        return
    await state.update_data(phone=phone)
    await message.answer("Введите ваш email:")
    await state.set_state(Registration.email)


@router.message(Registration.email)
async def process_email(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает ввод email и завершает регистрацию.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        bot: Экземпляр бота.

    Сложность: O(1).
    """
    email = message.text.strip()
    if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email):
        await message.answer("Неверный формат email.")
        return
    data = await state.get_data()
    full_name = data["full_name"]
    phone = data["phone"]
    try:
        user = get_user_by_telegram_id(message.from_user.id)
        referrer_id = user.referrer_id if user else None
        add_user(
            telegram_id=message.from_user.id,
            full_name=full_name,
            phone=phone,
            email=email,
            agreed_to_terms=True,
        )
        referrer_info = None
        if referrer_id:
            referrer = get_user_by_telegram_id(referrer_id)
            if referrer:
                referrer_info = {
                    "full_name": referrer.full_name,
                    "username": referrer.username,
                    "telegram_id": referrer_id,
                }
        notification = format_registration_notification(user, referrer_info)
        await bot.send_message(ADMIN_TELEGRAM_ID, notification, parse_mode="HTML")
        invite_link = await bot.create_chat_invite_link(
            chat_id=GROUP_ID, member_limit=1
        )
        invite_url = invite_link.invite_link
        registration_success = "===✨<i>Регистрация успешна!</i>✨===\n\n"
        registration_info = (
            f"Ваши данные:\n"
            f"👤 ФИО: {full_name}\n"
            f"📞 Телефон: {phone}\n"
            f"📧 Email: {email}\n\n"
            f"Присоединяйтесь к нашей группе: {invite_url}"
        )
        success_msg = registration_success + registration_info
        await message.answer(
            success_msg, reply_markup=create_invite_keyboard(), parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        logger.error(
            f"Ошибка при завершении регистрации для {message.from_user.id}: {str(e)}"
        )
        await message.answer("Ошибка при регистрации. Попробуйте снова.")


@router.callback_query(F.data == "info")
async def info(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показывает информацию о боте.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    info_message = (
        "ℹ️ Это бот коворкинга Parta!\n"
        "Вы можете:\n"
        "- Бронировать рабочие места и переговорные\n"
        "- Создавать заявки в техподдержку\n"
        "- Получать уведомления о ваших бронированиях\n\n"
        "Свяжитесь с нами: @partacoworking"
    )
    await callback_query.message.answer(
        info_message, reply_markup=create_invite_keyboard()
    )


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возвращает в главное меню.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await callback_query.message.answer(
        "Выберите действие:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Забронировать", callback_data="book")],
                [InlineKeyboardButton(text="Техподдержка", callback_data="ticket")],
                [InlineKeyboardButton(text="Информация", callback_data="info")],
            ]
        ),
    )
    await state.clear()


def register_reg_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики регистрации.

    Args:
        dp: Dispatcher бота.

    Сложность: O(1).
    """
    dp.include_router(router)
