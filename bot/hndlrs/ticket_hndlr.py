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
from models.models import (
    create_ticket,
    get_user_by_telegram_id,
    Session,
    format_ticket_notification,
    TicketStatus,
)
from utils.logger import get_logger
import os

logger = get_logger(__name__)
router = Router()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")


class TicketForm(StatesGroup):
    DESCRIPTION = State()
    ASK_PHOTO = State()
    PHOTO = State()


def create_helpdesk_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для техподдержки.

    Returns:
        InlineKeyboardMarkup с кнопками.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Создать заявку", callback_data="create_ticket"
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
        ]
    )
    return keyboard


def create_photo_choice_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора добавления фото.

    Returns:
        InlineKeyboardMarkup с кнопками.

    Сложность: O(1).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить фото", callback_data="add_photo")],
            [InlineKeyboardButton(text="Без фото", callback_data="no_photo")],
        ]
    )
    return keyboard


@router.callback_query(F.data == "create_ticket")
async def start_ticket_creation(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Начинает процесс создания заявки.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await callback_query.message.answer("Опишите проблему:")
    await state.set_state(TicketForm.DESCRIPTION)
    await state.update_data(telegram_id=callback_query.from_user.id)


@router.message(TicketForm.DESCRIPTION)
async def process_description(message: Message, state: FSMContext) -> None:
    """Обрабатывает описание заявки.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.

    Сложность: O(1).
    """
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=description)
    await message.answer(
        "Хотите прикрепить фото?", reply_markup=create_photo_choice_keyboard()
    )
    await state.set_state(TicketForm.ASK_PHOTO)


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "add_photo")
async def process_add_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор добавления фото.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await callback_query.message.answer("Отправьте фото:")
    await state.set_state(TicketForm.PHOTO)


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "no_photo")
async def process_skip_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает пропуск добавления фото.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    description = data.get("description")
    try:
        ticket, admin_message, session = create_ticket(telegram_id, description, None)
        if not ticket:
            await callback_query.message.answer(admin_message)
            return
        await callback_query.message.bot.send_message(
            ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
        )
        await callback_query.message.answer(
            f"Заявка #{ticket.id} создана. Ожидайте ответа."
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при создании заявки для {telegram_id}: {str(e)}")
        await callback_query.message.answer("Ошибка при создании заявки.")
    finally:
        if session:
            session.close()


@router.message(TicketForm.PHOTO, F.content_type == "photo")
async def process_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обрабатывает отправку фото для заявки.

    Args:
        message: Сообщение пользователя.
        state: Контекст FSM.
        bot: Экземпляр бота.

    Сложность: O(1).
    """
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    description = data.get("description")
    try:
        ticket, admin_message, session = create_ticket(
            telegram_id, description, photo_id
        )
        if not ticket:
            await message.answer(admin_message)
            return
        await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML")
        await bot.send_photo(ADMIN_TELEGRAM_ID, photo_id)
        await message.answer(f"Заявка #{ticket.id} создана с фото. Ожидайте ответа.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при создании заявки с фото для {telegram_id}: {str(e)}")
        await message.answer("Ошибка при создании заявки.")
    finally:
        if session:
            session.close()


@router.callback_query(F.data == "cancel")
async def cancel_ticket(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Отменяет процесс создания заявки.

    Args:
        callback_query: Callback-запрос.
        state: Контекст FSM.

    Сложность: O(1).
    """
    await state.clear()
    await callback_query.message.answer("Создание заявки отменено.")


def register_ticket_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики заявок.

    Args:
        dp: Dispatcher бота.

    Сложность: O(1).
    """
    dp.include_router(router)
