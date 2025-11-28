import os
import pytz
from datetime import datetime
from aiogram import Router, F, Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pydantic import EmailStr, ValidationError

from utils.logger import get_logger
from utils.api_client import get_api_client
from bot.config import create_user_keyboard, save_user_avatar
from bot.utils.localization import get_text, get_button_text
from bot.utils.error_handler import send_user_error, handle_api_error

logger = get_logger(__name__)

router = Router()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_LINK = os.getenv("BOT_LINK")
INVITE_LINK = os.getenv("INVITE_LINK")
GROUP_ID = os.getenv("GROUP_ID")


def get_info_message(lang="ru") -> str:
    """Получает информационное сообщение на нужном языке"""
    return f"""{get_text(lang, "info.title")}

{get_text(lang, "info.description")}

{get_text(lang, "info.offers")}

{get_text(lang, "info.schedule")}

{get_text(lang, "info.address")}
{get_text(lang, "info.phone")}
{get_text(lang, "info.website")}

{get_text(lang, "info.registration_needed")}"""


def format_registration_notification(user, referrer_info=None, lang="ru"):
    """Форматирование уведомления о регистрации для админа"""
    referrer_text = ""
    if referrer_info:
        referrer_text = f"""
{get_text(lang, "registration.invited_by")}
   • Username: @{referrer_info.get('username', get_text(lang, 'common.not_specified'))}
   • ID: {referrer_info.get('telegram_id', get_text(lang, 'common.not_specified'))}
"""

    # Безопасное получение данных с fallback значениями
    telegram_id = user.get("telegram_id", get_text(lang, "common.not_specified"))
    username = user.get("username", get_text(lang, "common.not_specified"))
    full_name = user.get("full_name", get_text(lang, "common.not_specified_n"))
    phone = user.get("phone", get_text(lang, "common.not_specified"))
    email = user.get("email", get_text(lang, "common.not_specified"))
    language_code = user.get("language_code", "ru")

    # Разбиваем полное имя на части
    surname = get_text(lang, "common.not_specified_f")
    first_name = get_text(lang, "common.not_specified_n")
    middle_name = get_text(lang, "common.not_specified_n")

    if full_name and full_name != get_text(lang, "common.not_specified_n"):
        name_parts = full_name.strip().split()
        if len(name_parts) >= 1:
            surname = name_parts[0]
        if len(name_parts) >= 2:
            first_name = name_parts[1]
        if len(name_parts) >= 3:
            middle_name = " ".join(name_parts[2:])

    message = f"""{get_text(lang, "registration.title")}

{get_text(lang, "registration.user_info")}
{get_text(lang, "registration.telegram_id")} {telegram_id}
{get_text(lang, "registration.username")} @{username}
{get_text(lang, "registration.surname")} <code>{surname}</code>
{get_text(lang, "registration.first_name")} <code>{first_name}</code>
{get_text(lang, "registration.middle_name")} <code>{middle_name}</code>
{get_text(lang, "registration.phone")} <code>{phone}</code>
{get_text(lang, "registration.email")} <code>{email}</code>
{get_text(lang, "registration.language")} {language_code}
{referrer_text}
{get_text(lang, "registration.reg_date")} {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}

{get_text(lang, "registration.completed")}"""
    return message


def create_register_keyboard(lang="ru") -> InlineKeyboardMarkup:
    """Создание клавиатуры для регистрации"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "register"),
                    callback_data="start_registration",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "info"), callback_data="info_reg"
                )
            ],
        ]
    )
    return keyboard


def create_agreement_keyboard(lang="ru") -> InlineKeyboardMarkup:
    """Создание клавиатуры для соглашения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "agree"), callback_data="agree_to_terms"
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "read_rules"),
                    url="https://parta-works.ru/main_rules",
                )
            ],
        ]
    )


def create_invite_keyboard(lang="ru") -> InlineKeyboardMarkup:
    """Создание клавиатуры для приглашения друзей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "invite_friends"),
                    callback_data="invite_friends",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "main_menu"), callback_data="main_menu"
                )
            ],
        ]
    )


class Registration(StatesGroup):
    agreement = State()
    full_name = State()
    phone = State()
    email = State()


def get_welcome_message(lang="ru") -> str:
    """Получает приветственное сообщение на нужном языке"""
    return f"""{get_text(lang, "welcome.title")}

{get_text(lang, "welcome.description")}"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Обработка команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    language_code = message.from_user.language_code or "ru"

    # Проверяем наличие реферального кода
    text_parts = message.text.split(maxsplit=1)
    ref_id = None
    if len(text_parts) > 1:
        try:
            ref_id = int(text_parts[1])
        except ValueError:
            pass
    try:
        # Получаем API клиента
        api_client = await get_api_client()

        # Проверяем и добавляем пользователя через API
        result = await api_client.check_and_add_user(
            telegram_id=user_id,
            username=username or "",
            language_code=language_code,
            referrer_id=ref_id,
        )

        user = result.get("user")
        is_new = result.get("is_new", False)
        is_complete = result.get("is_complete", False)

        # Если пользователь уже существует (не новый), сбрасываем флаг bot_blocked
        # Это означает, что пользователь вернулся и снова начал взаимодействие с ботом
        if not is_new and user:
            try:
                await api_client.update_user_by_telegram_id(
                    user_id, {"bot_blocked": False, "bot_blocked_at": None}
                )
                logger.info(f"Сброшен флаг bot_blocked для пользователя {user_id}")
            except Exception as e:
                # Логируем ошибку, но не прерываем процесс приветствия
                logger.warning(
                    f"Не удалось обновить статус пользователя {user_id}: {e}"
                )

        if is_complete:
            # Пользователь полностью зарегистрирован - приветствуем и показываем главное меню
            full_name = user.get("full_name", get_text(language_code, "common.user"))
            await message.answer(
                get_text(language_code, "welcome.returning", name=full_name),
                reply_markup=create_user_keyboard(language_code),
                parse_mode="HTML",
            )
        elif is_new:
            # Новый пользователь или не завершена регистрация
            welcome_text = get_welcome_message(language_code)

            # Если есть реферер, добавляем информацию о нем
            if ref_id and is_new:
                referrer = await api_client.get_user_by_telegram_id(ref_id)
                if referrer:
                    referrer_username = (
                        f"@{referrer.get('username')}"
                        if referrer.get("username")
                        else get_text(
                            language_code,
                            "registration.referrer_user_id",
                            user_id=referrer.get("telegram_id"),
                        )
                    )
                    welcome_text = (
                        get_text(
                            language_code, "welcome.invited", referrer=referrer_username
                        )
                        + "\n\n"
                        + welcome_text
                    )

            # Показываем приветственное сообщение с предложением зарегистрироваться
            await message.answer(
                welcome_text,
                reply_markup=create_register_keyboard(language_code),
                parse_mode="HTML",
            )
        # Если пользователь существует, но регистрация не завершена
        else:
            await message.answer(
                get_text(language_code, "welcome.incomplete"),
                reply_markup=create_register_keyboard(language_code),
            )
        # Очищаем состояние на всякий случай
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        await send_user_error(
            message,
            "errors.registration_failed",
            lang=language_code,
            error=e,
            show_support=True,
        )


@router.callback_query(F.data == "start_registration")
async def start_registration(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса регистрации"""
    # Получаем язык пользователя
    user_language = callback_query.from_user.language_code or "ru"

    await callback_query.message.edit_text(
        f"{get_text(user_language, 'registration.agreement_title')}\n\n{get_text(user_language, 'registration.agreement_text')}",
        reply_markup=create_agreement_keyboard(user_language),
        parse_mode="HTML",
    )
    await state.set_state(Registration.agreement)
    await callback_query.answer()


@router.callback_query(Registration.agreement, F.data == "agree_to_terms")
async def agree_to_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Согласие с условиями"""
    # Получаем язык пользователя
    user_language = callback_query.from_user.language_code or "ru"

    # Сохраняем факт согласия с условиями
    await state.update_data(agreed_to_terms=True)

    await callback_query.message.edit_text(
        get_text(user_language, "registration.step_name"),
        parse_mode="HTML",
    )
    await state.set_state(Registration.full_name)
    await callback_query.answer()


@router.message(Registration.agreement)
async def handle_invalid_agreement(message: Message, state: FSMContext) -> None:
    """Обработка неверного ввода на этапе соглашения"""
    user_language = message.from_user.language_code or "ru"
    await message.answer(
        "⚠️ Пожалуйста, используйте кнопки ниже для продолжения регистрации.",
        reply_markup=create_agreement_keyboard(user_language),
    )


@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Обработка ввода имени"""
    user_language = message.from_user.language_code or "ru"
    try:
        full_name = message.text.strip()

        if len(full_name) < 2:
            await message.answer(
                "❌ Имя слишком короткое. Пожалуйста, укажите полное имя (минимум 2 символа)."
            )
            return

        if len(full_name) > 100:
            await message.answer(
                "❌ Имя слишком длинное. Пожалуйста, укажите имя не длиннее 100 символов."
            )
            return

        await state.update_data(full_name=full_name)
        await message.answer(
            get_text(user_language, "registration.step_phone"),
            parse_mode="HTML",
        )
        await state.set_state(Registration.phone)
    except Exception as e:
        logger.error(f"Ошибка при обработке имени: {e}")
        await send_user_error(
            message,
            "errors.registration_name_failed",
            lang=user_language,
            error=e,
            show_support=True,
            state=state,
        )


@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    """Обработка ввода телефона"""
    import re

    user_language = message.from_user.language_code or "ru"
    try:
        phone = message.text.strip()

        # Очищаем номер от лишних символов
        phone_digits = re.sub(r"[^\d+]", "", phone)

        # Проверяем формат
        if not re.match(r"^(\+7|8|7)\d{10}$", phone_digits):
            await message.answer(
                "❌ Неверный формат номера телефона. Пожалуйста, введите российский номер в формате +79991234567 или 89991234567"
            )
            return

        # Приводим к единому формату +7
        if phone_digits.startswith("8"):
            phone_digits = "+7" + phone_digits[1:]
        elif phone_digits.startswith("7"):
            phone_digits = "+" + phone_digits

        await state.update_data(phone=phone_digits)
        await message.answer(
            get_text(user_language, "registration.step_email"),
            parse_mode="HTML",
        )
        await state.set_state(Registration.email)
    except Exception as e:
        logger.error(f"Ошибка при обработке телефона: {e}")
        await send_user_error(
            message,
            "errors.registration_phone_failed",
            lang=user_language,
            error=e,
            show_support=True,
            state=state,
        )


@router.message(Registration.email)
async def process_email(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка ввода email и завершение регистрации"""
    email = message.text.strip().lower()
    user_language = message.from_user.language_code or "ru"

    # Проверяем формат email через Pydantic EmailStr (более строгая валидация)
    try:
        EmailStr._validate(email)
    except (ValidationError, ValueError):
        await message.answer(
            "❌ Неверный формат email. Пожалуйста, введите корректный адрес электронной почты (например, example@mail.ru)"
        )
        return

    try:
        # Получаем данные из состояния
        data = await state.get_data()
        full_name = data["full_name"]
        phone = data["phone"]
        agreed_to_terms = data.get("agreed_to_terms", True)

        # Получаем API клиента
        api_client = await get_api_client()

        # Получаем пользователя
        user = await api_client.get_user_by_telegram_id(message.from_user.id)

        if user:
            # Сначала сохраняем аватар
            avatar_filename = None
            try:
                file_path = await save_user_avatar(bot, message.from_user.id)
                if file_path:
                    # Извлекаем только имя файла для БД
                    avatar_filename = os.path.basename(file_path)
                    logger.info(f"Аватар сохранен: {avatar_filename}")
            except Exception as e:
                logger.error(f"Ошибка сохранения аватара: {e}")

            # Подготавливаем данные для обновления
            current_time = datetime.now(MOSCOW_TZ)
            # Обновляем данные пользователя через API
            update_data = {
                "full_name": full_name,
                "phone": phone,
                "email": email,
                "agreed_to_terms": agreed_to_terms,
                "reg_date": current_time.isoformat(),  # Дата завершения регистрации
            }

            # Добавляем имя файла аватара если есть
            if avatar_filename:
                update_data["avatar"] = avatar_filename

            # Обновляем пользователя
            await api_client.update_user(user.get("id"), update_data)

            # ВАЖНО: Получаем обновленные данные пользователя после сохранения
            updated_user = await api_client.get_user_by_telegram_id(
                message.from_user.id
            )

            # Дополняем данные пользователя информацией из Telegram
            if not updated_user.get("telegram_id"):
                updated_user["telegram_id"] = message.from_user.id
            if not updated_user.get("username"):
<<<<<<< HEAD
                updated_user["username"] = message.from_user.username or get_text(user_language, "common.username_not_set")
=======
                updated_user["username"] = message.from_user.username or get_text(
                    user_language, "common.username_not_set"
                )
>>>>>>> a09df84dbc3f900cfe190c852bfc3d563d224997

            # Создаем уведомление для админки через API
            notification_data = {
                "user_id": user.get("id"),
                "message": f"Новая регистрация: {full_name}",
                "target_url": f"/users/{user.get('id')}",
            }

            try:
                await api_client.send_notification(
                    user.get("id"),
                    notification_data["message"],
                    notification_data["target_url"],
                )
            except Exception as e:
                logger.error(f"Ошибка создания уведомления: {e}")

            # Подготавливаем информацию о реферере
            referrer_info = None
            if updated_user.get("referrer_id"):
                referrer = await api_client.get_user_by_telegram_id(
                    updated_user.get("referrer_id")
                )
                if referrer:
                    referrer_info = {
                        "username": referrer.get(
                            "username", get_text("ru", "common.username_not_set")
                        ),
                        "telegram_id": referrer.get(
                            "telegram_id", get_text("ru", "common.username_not_set")
                        ),
                    }

            # Создаем ссылку на группу
            invite_url = "https://t.me/partacowo"
            if GROUP_ID:
                try:
                    invite_link = await bot.create_chat_invite_link(
                        chat_id=GROUP_ID, member_limit=1, creates_join_request=False
                    )
                    invite_url = invite_link.invite_link
                except Exception as e:
                    logger.error(f"Ошибка создания ссылки на группу: {e}")

            # Первое сообщение - информация о регистрации
            success_msg = f"""{get_text(user_language, "registration.success_title")}

{get_text(user_language, "registration.wifi_info")}

{get_text(user_language, "registration.your_data")}
{get_text(user_language, "registration.name_field")} {full_name}
{get_text(user_language, "registration.phone_field")} {phone}
{get_text(user_language, "registration.email_field")} {email}

{get_text(user_language, "registration.features_available")}"""

            await message.answer(success_msg, parse_mode="HTML")

            # Второе сообщение - действия с клавиатурой
            actions_msg = (
                get_text(user_language, "registration.what_next") + " " + invite_url
            )

            await message.answer(
                actions_msg,
                parse_mode="HTML",
                reply_markup=create_invite_keyboard(user_language),
            )

            # Отправляем уведомление админу в Telegram
            if ADMIN_TELEGRAM_ID:
                # Используем обновленные данные пользователя для уведомления
                notification = format_registration_notification(
                    updated_user, referrer_info, user_language
                )
                try:
                    await bot.send_message(
                        ADMIN_TELEGRAM_ID, notification, parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления админу: {e}")

        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при завершении регистрации: {e}")
        await send_user_error(
            message,
            "errors.registration_save_failed",
            lang=user_language,
            error=e,
            show_support=True,
        )


@router.callback_query(F.data == "invite_friends")
async def invite_friends(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка приглашения друзей"""
    user_language = callback_query.from_user.language_code or "ru"
    user_id = callback_query.from_user.id
    deeplink = f"{INVITE_LINK}?start={user_id}"

    share_text = get_text(user_language, "invite.text", link=deeplink)

    await callback_query.message.edit_text(
        text=get_text(user_language, "invite.select"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_button_text(user_language, "share"),
                        switch_inline_query=share_text,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_button_text(user_language, "main_menu"),
                        callback_data="main_menu",
                    )
                ],
            ]
        ),
        parse_mode="HTML",
    )
    await callback_query.answer()


@router.callback_query(F.data == "info")
async def info(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показ информации о коворкинге"""
    user_language = callback_query.from_user.language_code or "ru"
    info_message = get_info_message(user_language)

    await callback_query.message.edit_text(
        info_message,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_button_text(user_language, "back"),
                        callback_data="main_menu",
                    )
                ],
            ]
        ),
    )
    await callback_query.answer()


@router.callback_query(F.data == "info_reg")
async def info_reg(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показ информации о коворкинге"""
    user_language = callback_query.from_user.language_code or "ru"
    info_message = get_info_message(user_language)

    await callback_query.message.edit_text(
        info_message,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_button_text(user_language, "start_registration"),
                        callback_data="start_registration",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=get_button_text(user_language, "back"),
                        callback_data="back_to_start",
                    )
                ],
            ]
        ),
    )
    await callback_query.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню"""
    user_language = callback_query.from_user.language_code or "ru"
    await state.clear()

    await callback_query.message.edit_text(
        get_text(user_language, "menu.main_title"),
        reply_markup=create_user_keyboard(user_language),
        parse_mode="HTML",
    )
    await callback_query.answer()


@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к стартовому сообщению"""
    user_language = callback_query.from_user.language_code or "ru"
    await callback_query.message.edit_text(
        get_welcome_message(user_language),
        reply_markup=create_register_keyboard(user_language),
        parse_mode="HTML",
    )
    await callback_query.answer()


def register_reg_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков"""
    dp.include_router(router)
