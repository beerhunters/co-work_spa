import os
import pytz
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot, Dispatcher
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
from bot.config import create_back_keyboard
from bot.utils.localization import get_text, get_button_text
from bot.utils.error_handler import send_user_error, handle_api_error

logger = get_logger(__name__)

router = Router()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


class TicketForm(StatesGroup):
    DESCRIPTION = State()
    ASK_PHOTO = State()
    PHOTO = State()


def create_helpdesk_keyboard(lang="ru") -> InlineKeyboardMarkup:
    """Создание клавиатуры для поддержки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "support.create_ticket"), callback_data="create_ticket"
                )
            ],
            [InlineKeyboardButton(text=get_button_text(lang, "support.my_tickets"), callback_data="my_tickets")],
            [InlineKeyboardButton(text=get_button_text(lang, "back"), callback_data="main_menu")],
        ]
    )
    return keyboard


def create_photo_choice_keyboard(lang="ru") -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора добавления фото"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_button_text(lang, "support.add_photo"), callback_data="add_photo")],
            [
                InlineKeyboardButton(
                    text=get_button_text(lang, "support.continue_without_photo"), callback_data="no_photo"
                )
            ],
        ]
    )


def format_ticket_notification(user, ticket_data, lang="ru") -> str:
    """Форматирование уведомления о новом тикете для админа"""
    status_emojis = {"OPEN": "🟢", "IN_PROGRESS": "🟡", "CLOSED": "🔴"}
    status = ticket_data.get("status", "OPEN")
    status_emoji = status_emojis.get(status, "⚪")

    description = ticket_data.get("description", "")
    if len(description) > 200:
        description = description[:200] + "..."

    photo_info = ""
    if ticket_data.get("photo_id"):
        photo_info = f"\n{get_text(lang, 'support.ticket_photo_attached')}"

    message = f"""{get_text(lang, 'support.new_ticket_title')} {status_emoji}

{get_text(lang, 'support.ticket_user')} {user.get('full_name', get_text(lang, 'common.not_specified'))}
{get_text(lang, 'support.ticket_telegram')} @{user.get('username', get_text(lang, 'common.username_not_set'))}
{get_text(lang, 'support.ticket_phone')} {user.get('phone', get_text(lang, 'common.not_specified'))}

{get_text(lang, 'support.ticket_description')}
{description}{photo_info}

{get_text(lang, 'support.ticket_id')} #{ticket_data.get('id', 'N/A')}
{get_text(lang, 'support.ticket_created')} {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}

{get_text(lang, 'support.ticket_reply_note')}"""

    return message


@router.callback_query(F.data == "support")
async def support_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Меню поддержки"""
    lang = callback_query.from_user.language_code or "ru"
    await callback_query.message.edit_text(
        f"{get_text(lang, 'support.title')}\n\n{get_text(lang, 'support.description')}",
        reply_markup=create_helpdesk_keyboard(lang),
        parse_mode="HTML",
    )
    await callback_query.answer()


@router.callback_query(F.data == "create_ticket")
async def start_ticket_creation(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Начало создания тикета"""
    lang = callback_query.from_user.language_code or "ru"
    # Сохраняем telegram_id и язык для дальнейшего использования
    await state.update_data(telegram_id=callback_query.from_user.id, lang=lang)

    await callback_query.message.edit_text(
        get_text(lang, "support.enter_description"),
        parse_mode="HTML",
    )
    await state.set_state(TicketForm.DESCRIPTION)
    await callback_query.answer()


@router.message(TicketForm.DESCRIPTION)
async def process_description(message: Message, state: FSMContext) -> None:
    """Обработка описания проблемы"""
    data = await state.get_data()
    lang = data.get("lang", "ru")

    try:
        description = message.text.strip()

        if len(description) < 10:
            await message.answer(
                "❌ Описание слишком короткое. Пожалуйста, опишите вашу проблему подробнее (минимум 10 символов)."
            )
            return

        if len(description) > 1000:
            await message.answer(
                "❌ Описание слишком длинное. Пожалуйста, сократите текст до 1000 символов."
            )
            return

        await state.update_data(description=description)

        await message.answer(
            get_text(lang, "support.want_add_photo"),
            reply_markup=create_photo_choice_keyboard(lang),
        )
        await state.set_state(TicketForm.ASK_PHOTO)
    except Exception as e:
        logger.error(f"Ошибка при обработке описания тикета: {e}")
        await send_user_error(
            message,
            "errors.ticket_description_failed",
            lang=lang,
            error=e,
            show_support=True,
            state=state
        )


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "add_photo")
async def process_add_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Запрос на добавление фото"""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await callback_query.message.edit_text(
        get_text(lang, "support.send_photo")
    )
    await state.set_state(TicketForm.PHOTO)
    await callback_query.answer()


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "no_photo")
async def process_skip_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Пропуск добавления фото и создание тикета"""
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    description = data.get("description")
    lang = data.get("lang", "ru")

    await create_ticket(
        callback_query.message, telegram_id, description, None, callback_query.bot, lang
    )

    await state.clear()
    await callback_query.answer()


@router.message(TicketForm.PHOTO, F.content_type == "photo")
async def process_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка фото и создание тикета"""
    photo_id = message.photo[-1].file_id

    data = await state.get_data()
    description = data.get("description")
    lang = data.get("lang", "ru")

    await create_ticket(message, message.from_user.id, description, photo_id, bot, lang)

    await state.clear()


@router.message(TicketForm.PHOTO, ~F.content_type.in_(["photo"]))
async def process_invalid_photo(message: Message, state: FSMContext) -> None:
    """Обработка неверного типа файла"""
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await message.answer(
        "❌ Пожалуйста, отправьте фотографию. Другие типы файлов не поддерживаются.",
        reply_markup=create_photo_choice_keyboard(lang),
    )
    await state.set_state(TicketForm.ASK_PHOTO)


async def create_ticket(
    message: Message,
    telegram_id: int,
    description: str,
    photo_id: Optional[str],
    bot: Bot,
    lang: str = "ru",
) -> None:
    """Создание тикета через API"""
    try:
        api_client = await get_api_client()

        # Получаем пользователя
        user = await api_client.get_user_by_telegram_id(telegram_id)

        if not user:
            await message.answer(
                "😔 Не удалось найти вашу учетную запись. Пожалуйста, пройдите регистрацию заново через /start",
                reply_markup=create_back_keyboard(lang),
            )
            return

        # Создаем тикет через API
        ticket_data = {
            "user_id": telegram_id,
            "description": description,
            "photo_id": photo_id,
            "status": "OPEN",
        }

        result = await api_client.create_ticket(ticket_data)

        if "error" in result:
            logger.error(f"Ошибка API при создании тикета: {result}")
            await message.answer(
                "❌ К сожалению, не удалось создать обращение. Попробуйте еще раз через минуту или напишите напрямую администратору.",
                reply_markup=create_back_keyboard(lang),
            )
            return

        ticket_id = result.get("id")

        # Создаем уведомление для админки через API
        notification_data = {
            "user_id": user.get("id"),  # Используем внутренний ID пользователя
            "message": get_text(lang, "support.new_ticket_message", ticket_id=ticket_id),
            "target_url": f"/tickets",
            "ticket_id": ticket_id,
        }

        try:
            await api_client.create_notification(notification_data)
        except Exception as e:
            logger.error(f"Ошибка создания уведомления: {e}")

        # Формируем уведомление для админа в Telegram
        ticket_notification_data = {
            "id": ticket_id,
            "description": description,
            "photo_id": photo_id,
            "status": "OPEN",
        }

        admin_message = format_ticket_notification(user, ticket_notification_data, lang)

        # Отправляем уведомление админу в Telegram
        if ADMIN_TELEGRAM_ID:
            try:
                if photo_id:
                    # Отправляем с фото
                    await bot.send_photo(
                        ADMIN_TELEGRAM_ID,
                        photo=photo_id,
                        caption=admin_message,
                        parse_mode="HTML",
                    )
                else:
                    # Отправляем только текст
                    await bot.send_message(
                        ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")

        # Отправляем подтверждение пользователю
        await message.answer(
            get_text(lang, "support.ticket_created_success", ticket_id=ticket_id),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_button_text(lang, "my_tickets"), callback_data="my_tickets"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=get_button_text(lang, "main_menu"), callback_data="main_menu"
                        )
                    ],
                ]
            ),
        )

    except Exception as e:
        logger.error(f"Критическая ошибка при создании тикета: {e}")
        await send_user_error(
            message,
            "errors.ticket_creation_failed",
            lang=lang,
            error=e,
            show_support=True
        )


@router.callback_query(F.data == "my_tickets")
async def show_my_tickets(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показ списка обращений пользователя"""
    lang = callback_query.from_user.language_code or "ru"
    try:
        api_client = await get_api_client()
        telegram_id = callback_query.from_user.id

        logger.info(f"Запрос тикетов для пользователя {telegram_id}")

        # Получаем пользователя
        user = await api_client.get_user_by_telegram_id(telegram_id)

        if not user:
            logger.error(f"Пользователь с telegram_id {telegram_id} не найден в БД")
            await callback_query.message.edit_text(
                "😔 Не удалось найти вашу учетную запись. Пожалуйста, пройдите регистрацию заново через /start",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=get_button_text(lang, "main_menu"), callback_data="main_menu"
                            )
                        ]
                    ]
                ),
            )
            await callback_query.answer()
            return

        logger.info(f"Пользователь найден: {user.get('full_name', 'Не указано')}")

        # Получаем тикеты пользователя через API
        tickets = await api_client.get_user_tickets(telegram_id)

        logger.info(f"Получено тикетов для пользователя {telegram_id}: {len(tickets)}")

        if tickets:
            tickets_text = f"{get_text(lang, 'support.my_tickets')}\n\n"
            status_emojis = {"OPEN": "🟢", "IN_PROGRESS": "🟡", "CLOSED": "🔴"}

            for ticket in tickets[:10]:  # Показываем последние 10
                ticket_id = ticket.get("id")
                status = ticket.get("status", "OPEN")
                status_emoji = status_emojis.get(status, "⚪")
                description = ticket.get("description", "")

                # Обрезаем описание если слишком длинное
                if len(description) > 50:
                    description = description[:50] + "..."

                created_at = ticket.get("created_at")
                if created_at:
                    # Парсим дату
                    try:
                        # Убираем Z и добавляем +00:00 для правильного парсинга
                        if created_at.endswith("Z"):
                            created_at = created_at[:-1] + "+00:00"
                        elif (
                            not created_at.endswith(("+00:00", "Z"))
                            and "+" not in created_at[-6:]
                        ):
                            # Если нет указания временной зоны, добавляем UTC
                            created_at = created_at + "+00:00"

                        dt = datetime.fromisoformat(created_at)
                        # Конвертируем в московское время для отображения
                        moscow_dt = dt.astimezone(MOSCOW_TZ)
                        date_str = moscow_dt.strftime("%d.%m.%Y %H:%M")
                    except Exception as date_error:
                        logger.error(f"Ошибка парсинга даты {created_at}: {date_error}")
                        date_str = get_text(lang, "booking.date_unknown")
                else:
                    date_str = get_text(lang, "booking.date_unknown")

                # Получаем локализованные названия статусов
                status_names = {
                    "OPEN": get_text(lang, "support.status_open"),
                    "IN_PROGRESS": get_text(lang, "support.status_in_progress"),
                    "CLOSED": get_text(lang, "support.status_closed"),
                }
                status_name = status_names.get(status, status)

                tickets_text += f"{status_emoji} <b>#{ticket_id}</b> - {status_name}\n"
                tickets_text += f"   📝 {description}\n"
                tickets_text += f"   📅 {date_str}\n"

                # Показываем комментарий администратора если есть
                comment = ticket.get("comment")
                if comment:
                    comment_short = (
                        comment[:30] + "..." if len(comment) > 30 else comment
                    )
                    tickets_text += f"   💬 {comment_short}\n"

                tickets_text += "\n"

            if len(tickets) > 10:
                tickets_text += (
                    get_text(lang, "support.tickets_limit_note", count=len(tickets)) + "\n"
                )
        else:
            tickets_text = "📝 У вас пока нет обращений в поддержку.\n\nЕсли возникнут вопросы или проблемы, создайте новое обращение - мы всегда рады помочь!"

        await callback_query.message.edit_text(
            tickets_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_button_text(lang, "support.create_ticket"), callback_data="create_ticket"
                        )
                    ],
                    [InlineKeyboardButton(text=get_button_text(lang, "back"), callback_data="support")],
                ]
            ),
        )
        await callback_query.answer()

    except Exception as e:
        logger.error(
            f"Критическая ошибка при получении списка тикетов для пользователя {callback_query.from_user.id}: {e}"
        )
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке ваших обращений. Попробуйте еще раз через минуту.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_button_text(lang, "support.create_ticket"), callback_data="create_ticket"
                        )
                    ],
                    [InlineKeyboardButton(text=get_button_text(lang, "back"), callback_data="support")],
                ]
            ),
        )
        await callback_query.answer()


def register_ticket_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков тикетов"""
    dp.include_router(router)
