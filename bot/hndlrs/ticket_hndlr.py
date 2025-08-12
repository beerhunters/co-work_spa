# import os
#
# from aiogram import Router, Bot, F, Dispatcher
# from aiogram.filters import StateFilter
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import (
#     Message,
#     CallbackQuery,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )
#
# from bot.config import create_user_keyboard, create_back_keyboard
# from models.models import create_ticket
# from utils.logger import get_logger
#
# # Тихая настройка логгера для модуля
# logger = get_logger(__name__)
#
# router = Router()
# ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
#
#
# class TicketForm(StatesGroup):
#     """Состояния для процесса создания заявки."""
#
#     DESCRIPTION = State()
#     ASK_PHOTO = State()
#     PHOTO = State()
#
#
# def create_helpdesk_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создаёт инлайн-клавиатуру для Helpdesk.
#
#     Returns:
#         InlineKeyboardMarkup: Клавиатура с кнопкой Helpdesk и отмены.
#     """
#     try:
#         keyboard = InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [
#                     InlineKeyboardButton(
#                         text="Создать заявку", callback_data="create_ticket"
#                     )
#                 ],
#                 [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
#             ]
#         )
#         logger.debug("Создана клавиатура для Helpdesk")
#         return keyboard
#     except Exception as e:
#         logger.error(f"Ошибка при создании клавиатуры Helpdesk: {str(e)}")
#         return InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
#             ]
#         )
#
#
# def create_photo_choice_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создаёт клавиатуру для выбора добавления фото.
#
#     Returns:
#         InlineKeyboardMarkup: Клавиатура с кнопками 'Да', 'Нет' и 'Отмена'.
#     """
#     logger.debug("Создание клавиатуры для выбора добавления фото")
#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(text="Да", callback_data="add_photo"),
#                 InlineKeyboardButton(text="Нет", callback_data="no_photo"),
#             ],
#             [InlineKeyboardButton(text="Отмена", callback_data="cancel")],
#         ]
#     )
#     return keyboard
#
#
# @router.callback_query(F.data == "helpdesk")
# async def start_helpdesk(
#     callback_query: CallbackQuery, state: FSMContext, bot: Bot
# ) -> None:
#     """
#     Обработчик нажатия кнопки 'Helpdesk'. Запрашивает описание проблемы.
#
#     Args:
#         callback_query: Callback-запрос от кнопки.
#         state: Контекст состояния FSM.
#         bot: Экземпляр бота.
#     """
#     await state.set_state(TicketForm.DESCRIPTION)
#     # Сохраняем telegram_id пользователя
#     await state.update_data(telegram_id=callback_query.from_user.id)
#     await callback_query.message.edit_text(
#         "Опишите вашу проблему или пожелание:",
#         reply_markup=create_back_keyboard(),
#     )
#     logger.info(f"Пользователь {callback_query.from_user.id} начал создание заявки")
#     await callback_query.answer()
#
#
# @router.message(TicketForm.DESCRIPTION)
# async def process_description(message: Message, state: FSMContext) -> None:
#     """
#     Обработка описания проблемы. Запрашивает добавление фото.
#
#     Args:
#         message: Входящее сообщение с описанием.
#         state: Контекст состояния FSM.
#     """
#     description = message.text.strip()
#     if not description:
#         await message.answer(
#             "Описание не может быть пустым. Пожалуйста, введите описание:",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.warning(f"Пользователь {message.from_user.id} ввёл пустое описание")
#         return
#
#     await state.update_data(description=description)
#     await state.set_state(TicketForm.ASK_PHOTO)
#     await message.answer(
#         "Хотите прикрепить фото к заявке?",
#         reply_markup=create_photo_choice_keyboard(),
#     )
#     logger.info(f"Пользователь {message.from_user.id} ввёл описание: {description}")
#
#
# @router.callback_query(TicketForm.ASK_PHOTO, F.data == "add_photo")
# async def process_add_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
#     """
#     Обработка выбора добавления фото.
#
#     Args:
#         callback_query: Callback-запрос.
#         state: Контекст состояния FSM.
#     """
#     await state.set_state(TicketForm.PHOTO)
#     await callback_query.message.edit_text(
#         text="Пожалуйста, отправьте фото.",
#         reply_markup=create_back_keyboard(),
#     )
#     logger.info(f"Пользователь {callback_query.from_user.id} выбрал добавление фото")
#     await callback_query.answer()
#
#
# @router.callback_query(TicketForm.ASK_PHOTO, F.data == "no_photo")
# async def process_skip_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
#     try:
#         data = await state.get_data()
#         telegram_id = data.get("telegram_id")
#         description = data.get("description")
#
#         # Создаем тикет без фото
#         ticket, telegram_message = create_ticket(
#             user_id=telegram_id, description=description, photo_id=None
#         )
#
#         if ticket and telegram_message:
#             try:
#                 # Отправляем уведомление админу в Telegram
#                 await callback_query.bot.send_message(
#                     chat_id=ADMIN_TELEGRAM_ID, text=telegram_message, parse_mode="HTML"
#                 )
#                 logger.info(f"Уведомление о тикете #{ticket.id} отправлено админу")
#             except Exception as e:
#                 logger.error(f"Ошибка отправки уведомления админу: {e}")
#
#             await callback_query.message.edit_text(
#                 "✅ Ваша заявка успешно отправлена!\n\n"
#                 f"🏷 <b>Номер заявки:</b> #{ticket.id}\n"
#                 "📞 Мы свяжемся с вами в ближайшее время для решения вопроса.",
#                 reply_markup=create_user_keyboard(),
#                 parse_mode="HTML",
#             )
#             logger.info(
#                 f"Тикет #{ticket.id} успешно создан пользователем {telegram_id}"
#             )
#         else:
#             await callback_query.message.edit_text(
#                 "❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.",
#                 reply_markup=create_user_keyboard(),
#             )
#             logger.error(f"Не удалось создать тикет для пользователя {telegram_id}")
#
#     except Exception as e:
#         logger.error(f"Ошибка в process_skip_photo: {e}")
#         await callback_query.message.edit_text(
#             "❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.",
#             reply_markup=create_user_keyboard(),
#         )
#
#     await callback_query.answer()
#     await state.clear()
#
#
# @router.message(TicketForm.PHOTO, F.content_type == "photo")
# async def process_photo(message: Message, state: FSMContext, bot: Bot) -> None:
#     try:
#         photo_id = message.photo[-1].file_id
#         data = await state.get_data()
#         telegram_id = data.get("telegram_id")
#         description = data.get("description")
#
#         # Создаем тикет с фото
#         ticket, telegram_message = create_ticket(
#             user_id=telegram_id, description=description, photo_id=photo_id
#         )
#
#         if ticket and telegram_message:
#             try:
#                 # Отправляем фото админу с сообщением в Telegram
#                 await bot.send_photo(
#                     chat_id=ADMIN_TELEGRAM_ID,
#                     photo=photo_id,
#                     caption=telegram_message,
#                     parse_mode="HTML",
#                 )
#                 logger.info(
#                     f"Уведомление о тикете #{ticket.id} с фото отправлено админу"
#                 )
#             except Exception as e:
#                 logger.error(f"Ошибка отправки уведомления админу: {e}")
#                 # Если не удалось отправить фото, отправляем просто текст
#                 try:
#                     await bot.send_message(
#                         chat_id=ADMIN_TELEGRAM_ID,
#                         text=telegram_message,
#                         parse_mode="HTML",
#                     )
#                     logger.info(
#                         f"Текстовое уведомление о тикете #{ticket.id} отправлено админу"
#                     )
#                 except Exception as e2:
#                     logger.error(f"Ошибка отправки текстового уведомления админу: {e2}")
#
#             await message.answer(
#                 "✅ Ваша заявка успешно отправлена!\n\n"
#                 f"🏷 <b>Номер заявки:</b> #{ticket.id}\n"
#                 "📞 Мы свяжемся с вами в ближайшее время для решения вопроса.",
#                 reply_markup=create_user_keyboard(),
#                 parse_mode="HTML",
#             )
#             logger.info(
#                 f"Тикет #{ticket.id} с фото успешно создан пользователем {telegram_id}"
#             )
#         else:
#             await message.answer(
#                 "❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.",
#                 reply_markup=create_user_keyboard(),
#             )
#             logger.error(
#                 f"Не удалось создать тикет с фото для пользователя {telegram_id}"
#             )
#
#     except Exception as e:
#         logger.error(f"Ошибка в process_photo: {e}")
#         await message.answer(
#             "❌ Произошла ошибка при отправке заявки. Попробуйте еще раз.",
#             reply_markup=create_user_keyboard(),
#         )
#
#     await state.clear()
#
#
# @router.message(TicketForm.PHOTO, ~F.content_type.in_(["photo"]))
# async def process_invalid_photo(message: Message, state: FSMContext) -> None:
#     """Обработка неправильного типа файла вместо фото."""
#     await message.answer(
#         "❌ Пожалуйста, отправьте именно фото, а не другой тип файла.",
#         reply_markup=create_back_keyboard(),
#     )
#     logger.warning(
#         f"Пользователь {message.from_user.id} отправил не фото в состоянии PHOTO"
#     )
#
#
# @router.callback_query(
#     StateFilter(TicketForm.DESCRIPTION, TicketForm.ASK_PHOTO, TicketForm.PHOTO),
#     F.data == "cancel",
# )
# @router.callback_query(
#     StateFilter(TicketForm.DESCRIPTION, TicketForm.ASK_PHOTO, TicketForm.PHOTO),
#     F.data == "main_menu",
# )
# async def cancel_ticket_creation(
#     callback_query: CallbackQuery, state: FSMContext
# ) -> None:
#     """
#     Обработка отмены создания заявки.
#
#     Args:
#         callback_query: Callback-запрос.
#         state: Контекст состояния FSM.
#     """
#     await state.clear()
#     await callback_query.message.edit_text(
#         text="Создание заявки отменено.",
#         reply_markup=create_user_keyboard(),
#     )
#     logger.info(f"Пользователь {callback_query.from_user.id} отменил создание заявки")
#     await callback_query.answer()
#
#
# def register_ticket_handlers(dp: Dispatcher) -> None:
#     """Регистрация обработчиков для тикетов."""
#     dp.include_router(router)
"""
Обновленный обработчик тикетов для работы через API
"""
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

logger = get_logger(__name__)

router = Router()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
MOSCOW_TZ = pytz.timezone("Europe/Moscow")


class TicketForm(StatesGroup):
    DESCRIPTION = State()
    ASK_PHOTO = State()
    PHOTO = State()


def create_helpdesk_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для поддержки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Создать обращение", callback_data="create_ticket"
                )
            ],
            [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_tickets")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")],
        ]
    )
    return keyboard


def create_photo_choice_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора добавления фото"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Добавить фото", callback_data="add_photo")],
            [
                InlineKeyboardButton(
                    text="➡️ Продолжить без фото", callback_data="no_photo"
                )
            ],
        ]
    )


def format_ticket_notification(user, ticket_data) -> str:
    """Форматирование уведомления о новом тикете для админа"""
    status_emojis = {"OPEN": "🟢", "IN_PROGRESS": "🟡", "CLOSED": "🔴"}
    status = ticket_data.get("status", "OPEN")
    status_emoji = status_emojis.get(status, "⚪")

    description = ticket_data.get("description", "")
    if len(description) > 200:
        description = description[:200] + "..."

    photo_info = ""
    if ticket_data.get("photo_id"):
        photo_info = "\n📸 <b>Прикреплено фото</b>"

    message = f"""🎫 <b>НОВЫЙ ТИКЕТ!</b> {status_emoji}

👤 <b>Пользователь:</b> {user.get('full_name', 'Не указано')}
📱 <b>Telegram:</b> @{user.get('username', 'Не указан')}
📞 <b>Телефон:</b> {user.get('phone', 'Не указан')}

📝 <b>Описание:</b>
{description}{photo_info}

🆔 <b>ID тикета:</b> #{ticket_data.get('id', 'N/A')}
📅 <b>Создан:</b> {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}

💬 Ответить можно через админ-панель"""

    return message


@router.callback_query(F.data == "support")
async def support_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Меню поддержки"""
    await callback_query.message.edit_text(
        "🎫 <b>Служба поддержки</b>\n\n"
        "Здесь вы можете создать обращение или посмотреть статус существующих.\n\n"
        "Выберите действие:",
        reply_markup=create_helpdesk_keyboard(),
        parse_mode="HTML",
    )
    await callback_query.answer()


@router.callback_query(F.data == "create_ticket")
async def start_ticket_creation(
    callback_query: CallbackQuery, state: FSMContext
) -> None:
    """Начало создания тикета"""
    # Сохраняем telegram_id для дальнейшего использования
    await state.update_data(telegram_id=callback_query.from_user.id)

    await callback_query.message.edit_text(
        "📝 <b>Создание обращения</b>\n\n"
        "Опишите вашу проблему или вопрос как можно подробнее:",
        parse_mode="HTML",
    )
    await state.set_state(TicketForm.DESCRIPTION)
    await callback_query.answer()


@router.message(TicketForm.DESCRIPTION)
async def process_description(message: Message, state: FSMContext) -> None:
    """Обработка описания проблемы"""
    description = message.text.strip()

    if len(description) < 10:
        await message.answer(
            "⚠️ Описание слишком короткое. Пожалуйста, опишите проблему подробнее:"
        )
        return

    await state.update_data(description=description)

    await message.answer(
        "Хотите прикрепить фото к обращению?",
        reply_markup=create_photo_choice_keyboard(),
    )
    await state.set_state(TicketForm.ASK_PHOTO)


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "add_photo")
async def process_add_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Запрос на добавление фото"""
    await callback_query.message.edit_text(
        "📸 Отправьте фото, связанное с вашим обращением:"
    )
    await state.set_state(TicketForm.PHOTO)
    await callback_query.answer()


@router.callback_query(TicketForm.ASK_PHOTO, F.data == "no_photo")
async def process_skip_photo(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Пропуск добавления фото и создание тикета"""
    data = await state.get_data()
    telegram_id = data.get("telegram_id")
    description = data.get("description")

    await create_ticket(
        callback_query.message, telegram_id, description, None, callback_query.bot
    )

    await state.clear()
    await callback_query.answer()


@router.message(TicketForm.PHOTO, F.content_type == "photo")
async def process_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработка фото и создание тикета"""
    photo_id = message.photo[-1].file_id

    data = await state.get_data()
    description = data.get("description")

    await create_ticket(message, message.from_user.id, description, photo_id, bot)

    await state.clear()


@router.message(TicketForm.PHOTO, ~F.content_type.in_(["photo"]))
async def process_invalid_photo(message: Message, state: FSMContext) -> None:
    """Обработка неверного типа файла"""
    await message.answer(
        "⚠️ Пожалуйста, отправьте фото. Или нажмите кнопку «Продолжить без фото»",
        reply_markup=create_photo_choice_keyboard(),
    )
    await state.set_state(TicketForm.ASK_PHOTO)


async def create_ticket(
    message: Message,
    telegram_id: int,
    description: str,
    photo_id: Optional[str],
    bot: Bot,
) -> None:
    """Создание тикета через API"""
    api_client = await get_api_client()

    # Получаем пользователя
    user = await api_client.get_user_by_telegram_id(telegram_id)

    if not user:
        await message.answer(
            "❌ Ошибка: пользователь не найден. Пожалуйста, зарегистрируйтесь.",
            reply_markup=create_back_keyboard(),
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
        await message.answer(
            "❌ Ошибка создания обращения. Попробуйте позже.",
            reply_markup=create_back_keyboard(),
        )
        return

    ticket_id = result.get("id")

    # Создаем уведомление для админки через API
    notification_data = {
        "user_id": user.get("id"),
        "message": f"Новая тикет",
        "target_url": f"/tickets/{ticket_id}",
    }

    try:
        await api_client.send_notification(
            user.get("id"),
            notification_data["message"],
            notification_data["target_url"],
        )
    except Exception as e:
        logger.error(f"Ошибка создания уведомления: {e}")

    # Формируем уведомление для админа
    ticket_notification_data = {
        "id": ticket_id,
        "description": description,
        "photo_id": photo_id,
        "status": "OPEN",
    }

    admin_message = format_ticket_notification(user, ticket_notification_data)

    # Отправляем уведомление админу
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
        f"✅ <b>Обращение создано!</b>\n\n"
        f"🆔 Номер обращения: #{ticket_id}\n"
        f"📋 Статус: Открыто\n\n"
        f"Мы рассмотрим ваше обращение в ближайшее время и свяжемся с вами.\n"
        f"Среднее время ответа: 2-4 часа в рабочее время.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 Мои обращения", callback_data="my_tickets"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню", callback_data="main_menu"
                    )
                ],
            ]
        ),
    )


@router.callback_query(F.data == "my_tickets")
async def show_my_tickets(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Показ списка обращений пользователя"""
    api_client = await get_api_client()

    # Получаем пользователя
    user = await api_client.get_user_by_telegram_id(callback_query.from_user.id)

    if not user:
        await callback_query.message.edit_text(
            "❌ Ошибка: пользователь не найден.", reply_markup=create_back_keyboard()
        )
        await callback_query.answer()
        return

    # Получаем тикеты пользователя через API
    tickets = await api_client.get_user_tickets(callback_query.from_user.id)

    tickets_text = "📋 <b>Ваши обращения:</b>\n\n"

    if tickets:
        status_emojis = {"Открыта": "🟢", "В работе": "🟡", "Закрыта": "🔴"}

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
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    date_str = "Неизвестно"
            else:
                date_str = "Неизвестно"

            tickets_text += f"{status_emoji} <b>#{ticket_id}</b> - {status}\n"
            tickets_text += f"   📝 {description}\n"
            tickets_text += f"   📅 {date_str}\n\n"

        if len(tickets) > 10:
            tickets_text += (
                f"<i>Показаны последние 10 из {len(tickets)} обращений</i>\n"
            )
    else:
        tickets_text += "У вас пока нет обращений.\n"

    tickets_text += "\n💡 <i>Для получения подробной информации об обращении обратитесь в поддержку</i>"

    await callback_query.message.edit_text(
        tickets_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Создать обращение", callback_data="create_ticket"
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="support")],
            ]
        ),
    )
    await callback_query.answer()
    # tickets = await api_client.get_user_tickets(user.get("id"))

    tickets_text += "У вас пока нет обращений."

    await callback_query.message.edit_text(
        tickets_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Создать обращение", callback_data="create_ticket"
                    )
                ],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="support")],
            ]
        ),
    )
    await callback_query.answer()


def register_ticket_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков тикетов"""
    dp.include_router(router)
