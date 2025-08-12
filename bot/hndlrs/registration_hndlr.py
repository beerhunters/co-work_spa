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

from utils.logger import get_logger
from utils.api_client import get_api_client
from bot.config import create_user_keyboard, save_user_avatar

logger = get_logger(__name__)

router = Router()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_LINK = os.getenv("BOT_LINK")
INVITE_LINK = os.getenv("INVITE_LINK")
GROUP_ID = os.getenv("GROUP_ID")

INFO_MESSAGE = (
    "ℹ️ <b>О PARTA коворкинг</b>\n\n"
    "PARTA - современное пространство для продуктивной работы в центре города.\n\n"
    "🏢 <b>Что мы предлагаем:</b>\n"
    "• Комфортные рабочие места в open space\n"
    "• Оборудованные переговорные комнаты\n"
    "• Высокоскоростной интернет (1 Гбит/с)\n"
    "• Бесплатные кофе, чай и снеки\n"
    "• Зоны отдыха и нетворкинга\n"
    "• Печать и сканирование документов\n"
    "• Парковка для автомобилей\n\n"
    "⏰ <b>Режим работы:</b>\n"
    "Круглосуточно 24/7\n\n"
    "📍 <b>Адрес:</b> г. Санкт-Петербург, Малый проспект ВО, д. 55\n"
    "📞 <b>Телефон:</b> +7 (812) 990-00-55\n"
    "🌐 <b>Сайт:</b> parta-works.ru\n\n"
    "Для начала работы пройдите быструю регистрацию!"
)


def format_registration_notification(user, referrer_info=None):
    """Форматирование уведомления о регистрации для админа"""
    referrer_text = ""
    if referrer_info:
        referrer_text = f"""
🔗 <b>Приглашен пользователем:</b>
   • Username: @{referrer_info['username']}
   • ID: {referrer_info['telegram_id']}
"""

    message = f"""🎉 <b>НОВЫЙ ПОЛЬЗОВАТЕЛЬ ЗАРЕГИСТРИРОВАН!</b>

👤 <b>Информация:</b>
📱 <b>Telegram ID:</b> {user.get('telegram_id')}
👤 <b>Username:</b> @{user.get('username', 'Не указан')}
📝 <b>Имя:</b> {user.get('full_name', 'Не указано')}
📞 <b>Телефон:</b> {user.get('phone', 'Не указан')}
📧 <b>Email:</b> {user.get('email', 'Не указан')}
🌍 <b>Язык:</b> {user.get('language_code', 'ru')}
{referrer_text}
📅 <b>Дата регистрации:</b> {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}

✅ Пользователь прошел полную регистрацию и принял условия соглашения."""
    return message


def create_register_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для регистрации"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Регистрация", callback_data="start_registration"
                )
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ Информация о коворкинге", callback_data="info_reg"
                )
            ],
        ]
    )
    return keyboard


def create_agreement_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для соглашения"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принимаю условия", callback_data="agree_to_terms"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Читать правила", url="https://parta-works.ru/main_rules"
                )
            ],
        ]
    )


def create_invite_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для приглашения друзей"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Пригласить друзей", callback_data="invite_friends"
                )
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )


class Registration(StatesGroup):
    agreement = State()
    full_name = State()
    phone = State()
    email = State()


welcome_message = (
    "🎉 <b>Добро пожаловать в PARTA коворкинг!</b>\n\n"
    "🤖 Я помогу вам:\n"
    "• 📅 Забронировать рабочее место\n"
    "• 🏢 Арендовать переговорную комнату\n"
    "• 🎫 Связаться со службой поддержки\n"
    "• 🎁 Использовать промокоды для скидок\n"
    "• 👥 Пригласить друзей и получить бонусы\n\n"
    "Для использования всех возможностей бота необходимо пройти регистрацию."
)


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

        if is_complete:
            # Пользователь полностью зарегистрирован - приветствуем и показываем главное меню
            full_name = user.get("full_name", "Пользователь")
            await message.answer(
                f"👋 <b>С возвращением, {full_name}!</b>\n\n"
                "Рад видеть вас снова в PARTA коворкинг.\n"
                "Выберите нужное действие из меню ниже:",
                reply_markup=create_user_keyboard(),
                parse_mode="HTML",
            )
        elif is_new:
            # Новый пользователь или не завершена регистрация
            welcome_text = welcome_message

            # Если есть реферер, добавляем информацию о нем
            if ref_id and is_new:
                referrer = await api_client.get_user_by_telegram_id(ref_id)
                if referrer:
                    referrer_username = (
                        f"@{referrer.get('username')}"
                        if referrer.get("username")
                        else f"пользователя #{referrer.get('telegram_id')}"
                    )
                    welcome_text = (
                        f"🎊 Вы перешли по приглашению от {referrer_username}!\n\n"
                        + welcome_text
                    )

            # Показываем приветственное сообщение с предложением зарегистрироваться
            await message.answer(
                welcome_text, reply_markup=create_register_keyboard(), parse_mode="HTML"
            )
        # Если пользователь существует, но регистрация не завершена
        else:
            await message.answer(
                "Похоже, вы не завершили регистрацию. Давайте продолжим!",
                reply_markup=create_register_keyboard(),
            )
        # Очищаем состояние на всякий случай
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /start: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
        )


@router.callback_query(F.data == "start_registration")
async def start_registration(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса регистрации"""
    await callback_query.message.edit_text(
        "📋 <b>Пользовательское соглашение</b>\n\n"
        "Для продолжения регистрации необходимо ознакомиться и принять условия пользовательского соглашения.\n\n"
        "Нажмите кнопку «Читать правила» для ознакомления с условиями использования коворкинга.\n\n"
        "После ознакомления нажмите «Принимаю условия» для продолжения регистрации.",
        reply_markup=create_agreement_keyboard(),
        parse_mode="HTML",
    )
    await state.set_state(Registration.agreement)
    await callback_query.answer()


@router.callback_query(Registration.agreement, F.data == "agree_to_terms")
async def agree_to_terms(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Согласие с условиями"""
    # Сохраняем факт согласия с условиями
    await state.update_data(agreed_to_terms=True)

    await callback_query.message.edit_text(
        "📝 <b>Регистрация - Шаг 1/3</b>\n\n" "Введите ваше полное имя (ФИО):",
        parse_mode="HTML",
    )
    await state.set_state(Registration.full_name)
    await callback_query.answer()


@router.message(Registration.agreement)
async def handle_invalid_agreement(message: Message, state: FSMContext) -> None:
    """Обработка неверного ввода на этапе соглашения"""
    await message.answer(
        "⚠️ Пожалуйста, используйте кнопки для принятия соглашения.",
        reply_markup=create_agreement_keyboard(),
    )


@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext) -> None:
    """Обработка ввода имени"""
    full_name = message.text.strip()

    if len(full_name) < 2:
        await message.answer("⚠️ Имя слишком короткое. Введите полное имя:")
        return

    if len(full_name) > 100:
        await message.answer("⚠️ Имя слишком длинное. Введите корректное имя:")
        return

    await state.update_data(full_name=full_name)
    await message.answer(
        "📝 <b>Регистрация - Шаг 2/3</b>\n\n"
        "Введите ваш номер телефона в формате:\n"
        "+7XXXXXXXXXX или 8XXXXXXXXXX",
        parse_mode="HTML",
    )
    await state.set_state(Registration.phone)


@router.message(Registration.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    """Обработка ввода телефона"""
    import re

    phone = message.text.strip()

    # Очищаем номер от лишних символов
    phone_digits = re.sub(r"[^\d+]", "", phone)

    # Проверяем формат
    if not re.match(r"^(\+7|8|7)\d{10}$", phone_digits):
        await message.answer(
            "⚠️ Неверный формат номера.\n"
            "Пожалуйста, введите номер в формате:\n"
            "+7XXXXXXXXXX или 8XXXXXXXXXX"
        )
        return

    # Приводим к единому формату +7
    if phone_digits.startswith("8"):
        phone_digits = "+7" + phone_digits[1:]
    elif phone_digits.startswith("7"):
        phone_digits = "+" + phone_digits

    await state.update_data(phone=phone_digits)
    await message.answer(
        "📝 <b>Регистрация - Шаг 3/3</b>\n\n" "Введите ваш email адрес:",
        parse_mode="HTML",
    )
    await state.set_state(Registration.email)


@router.message(Registration.email)
async def process_email(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка ввода email и завершение регистрации"""
    import re

    email = message.text.strip().lower()

    # Проверяем формат email
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        await message.answer("⚠️ Неверный формат email. Попробуйте еще раз:")
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

            updated_user = await api_client.update_user(user.get("id"), update_data)

            # Создаем уведомление для админки через API
            notification_data = {
                "user_id": user.get("id"),
                "message": f"Новая регистрация: {full_name} (@{message.from_user.username or 'без username'})",
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
            if user.get("referrer_id"):
                referrer = await api_client.get_user_by_telegram_id(
                    user.get("referrer_id")
                )
                if referrer:
                    referrer_info = {
                        "username": referrer.get("username"),
                        "telegram_id": referrer.get("telegram_id"),
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

            # Формируем сообщение успешной регистрации
            success_msg = (
                "✅ <b>Регистрация успешно завершена!</b>\n\n"
                "🛜 WiFi: <b>Parta</b> Пароль: <code>Parta2024</code>\n\n"
                f"📝 <b>Ваши данные:</b>\n"
                f"👤 Имя: {full_name}\n"
                f"📞 Телефон: {phone}\n"
                f"📧 Email: {email}\n\n"
                f"🎉 Теперь вам доступны все функции бота!\n\n"
                f"💡 <b>Что дальше?</b>\n"
                f"• Забронируйте рабочее место или переговорную\n"
                f"• Пригласите друзей и получите бонусы\n"
                f"• Присоединяйтесь к нашей группе: {invite_url}"
            )

            await message.answer(
                success_msg, parse_mode="HTML", reply_markup=create_invite_keyboard()
            )

            # Отправляем уведомление админу в Telegram
            if ADMIN_TELEGRAM_ID:
                notification = format_registration_notification(
                    updated_user, referrer_info
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
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте позже или обратитесь в поддержку."
        )


@router.callback_query(F.data == "invite_friends")
async def invite_friends(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обработка приглашения друзей"""
    user_id = callback_query.from_user.id
    deeplink = f"{INVITE_LINK}?start={user_id}"

    share_text = (
        f"🚀 Присоединяйся к PARTA коворкинг!\n\n"
        f"Современное пространство для работы и творчества.\n"
        f"Используй мою ссылку для регистрации:\n\n"
        f"{deeplink}"
    )
    await callback_query.message.edit_text(
        text="Выберите, с кем поделиться ссылкой:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Поделиться", switch_inline_query=share_text
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню", callback_data="main_menu"
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
    info_message = INFO_MESSAGE

    await callback_query.message.edit_text(
        info_message,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")],
            ]
        ),
    )
    await callback_query.answer()


@router.callback_query(F.data == "info_reg")
async def info(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показ информации о коворкинге"""
    info_message = INFO_MESSAGE

    await callback_query.message.edit_text(
        info_message,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Начать регистрацию", callback_data="start_registration"
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_start")],
            ]
        ),
    )
    await callback_query.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню"""
    await state.clear()

    await callback_query.message.edit_text(
        "🏠 <b>Главное меню</b>\n\n" "Выберите нужное действие:",
        reply_markup=create_user_keyboard(),
        parse_mode="HTML",
    )
    await callback_query.answer()


@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к стартовому сообщению"""
    await callback_query.message.edit_text(
        welcome_message, reply_markup=create_register_keyboard(), parse_mode="HTML"
    )
    await callback_query.answer()


def register_reg_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков"""
    dp.include_router(router)
