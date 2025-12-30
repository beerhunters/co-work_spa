from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.api_client import get_api_client
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID

router = Router()
logger = get_logger(__name__)


class OfficeSubscriptionStates(StatesGroup):
    """Состояния FSM для подписки на офисы."""
    selecting_sizes = State()


# Маппинг размеров офисов для отображения
OFFICE_SIZES = {
    1: "Офис на 1 человека",
    2: "Офис на 2 человека",
    4: "Офис на 4 человека",
    6: "Офис на 6 человек"
}


def build_office_keyboard(selected_sizes: set[int]) -> InlineKeyboardBuilder:
    """
    Построить клавиатуру с чекбоксами для выбора размеров офисов.

    Args:
        selected_sizes: Множество уже выбранных размеров
    """
    builder = InlineKeyboardBuilder()

    for size in [1, 2, 4, 6]:
        checkmark = "✅ " if size in selected_sizes else ""
        text = f"{checkmark}{OFFICE_SIZES[size]}"
        builder.button(text=text, callback_data=f"office_size_{size}")

    # Располагаем кнопки в 2 столбца
    builder.adjust(2)

    # Кнопка подтверждения (только если что-то выбрано)
    if selected_sizes:
        builder.row()
        builder.button(text="✅ Подтвердить выбор", callback_data="office_confirm")

    # Кнопка отмены
    builder.row()
    builder.button(text="❌ Отменить", callback_data="office_cancel")

    return builder


async def start_office_subscription(user_id: int, user_fullname: str, state: FSMContext, send_message_func):
    """
    Общая логика начала подписки на офисы.

    Args:
        user_id: Telegram ID пользователя
        user_fullname: Полное имя пользователя
        state: FSM контекст
        send_message_func: Функция для отправки сообщения (async)
    """
    api_client = await get_api_client()

    # Проверяем, зарегистрирован ли пользователь
    user_data = await api_client.get_user_by_telegram_id(user_id)

    if not user_data:
        await send_message_func(
            "⚠️ Вы не зарегистрированы в системе.\n\n"
            "Пожалуйста, используйте команду /start для регистрации."
        )
        return

    # Проверяем, есть ли уже подписка
    existing_subscription = await api_client._make_request("GET", f"/office-subscriptions/user/{user_id}")

    if existing_subscription and "error" not in existing_subscription:
        await send_message_func(
            "ℹ️ У вас уже есть активная подписка на офисы.\n\n"
            "Для изменения подписки сначала отмените текущую через команду /unsubscribe_office"
        )
        return

    # Инициализируем пустой набор выбранных размеров
    await state.set_state(OfficeSubscriptionStates.selecting_sizes)
    await state.update_data(selected_sizes=set())

    keyboard = build_office_keyboard(set())

    await send_message_func(
        "🏢 <b>Подписка на уведомления о доступности офисов</b>\n\n"
        "Выберите размеры офисов, которые вас интересуют.\n"
        "Вы можете выбрать несколько вариантов.\n\n"
        "Когда офис нужного размера станет доступен, мы вам сообщим!",
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )


@router.message(Command("subscribe_office"))
async def cmd_subscribe_office(message: Message, state: FSMContext):
    """
    Команда /subscribe_office - начало подписки на офисы.

    Также доступна через кнопку "Подписаться на офис" в главном меню.
    """
    user_id = message.from_user.id
    await start_office_subscription(
        user_id=user_id,
        user_fullname=message.from_user.full_name or "Пользователь",
        state=state,
        send_message_func=message.answer
    )


@router.callback_query(F.data == "subscribe_office")
async def callback_subscribe_office(callback: CallbackQuery, state: FSMContext):
    """
    Обработка нажатия на кнопку "Подписаться на офис" в главном меню.
    """
    async def send_or_edit(text, **kwargs):
        """Helper для отправки/редактирования сообщения в callback."""
        try:
            await callback.message.edit_text(text, **kwargs)
        except Exception:
            # Если не удалось отредактировать, отправляем новое
            await callback.message.answer(text, **kwargs)

    user_id = callback.from_user.id
    await start_office_subscription(
        user_id=user_id,
        user_fullname=callback.from_user.full_name or "Пользователь",
        state=state,
        send_message_func=send_or_edit
    )
    await callback.answer()


@router.callback_query(F.data.startswith("office_size_"), OfficeSubscriptionStates.selecting_sizes)
async def toggle_office_size(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора/отмены размера офиса (toggle чекбокса)."""
    size = int(callback.data.split("_")[-1])

    # Получаем текущий набор выбранных размеров
    data = await state.get_data()
    selected_sizes: set = data.get("selected_sizes", set())

    # Toggle: если уже выбран - убираем, если нет - добавляем
    if size in selected_sizes:
        selected_sizes.remove(size)
    else:
        selected_sizes.add(size)

    await state.update_data(selected_sizes=selected_sizes)

    # Обновляем клавиатуру
    keyboard = build_office_keyboard(selected_sizes)

    await callback.message.edit_reply_markup(reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data == "office_confirm", OfficeSubscriptionStates.selecting_sizes)
async def confirm_subscription(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выбора и создание подписки."""
    user = callback.from_user
    data = await state.get_data()
    selected_sizes: set = data.get("selected_sizes", set())

    if not selected_sizes:
        await callback.answer("⚠️ Выберите хотя бы один размер офиса!", show_alert=True)
        return

    # Формируем данные для API
    subscription_data = {
        "office_1": 1 in selected_sizes,
        "office_2": 2 in selected_sizes,
        "office_4": 4 in selected_sizes,
        "office_6": 6 in selected_sizes
    }

    # Создаем подписку через API
    try:
        api_client = await get_api_client()
        response = await api_client._make_request(
            "POST",
            f"/office-subscriptions/user/{user.id}",
            json=subscription_data
        )

        if "error" in response:
            raise Exception(response["error"])

        # Уведомление пользователю
        selected_list = "\n".join([f"  • {OFFICE_SIZES[size]}" for size in sorted(selected_sizes)])

        await callback.message.edit_text(
            f"✅ <b>Подписка оформлена!</b>\n\n"
            f"Вы подписались на уведомления для:\n{selected_list}\n\n"
            f"Мы сообщим вам, когда офис нужного размера станет доступен.",
            parse_mode="HTML"
        )

        # Уведомление администратору
        bot = get_bot()
        admin_message = (
            f"🔔 <b>Новая подписка на офис</b>\n\n"
            f"👤 Пользователь: {user.full_name or 'Неизвестно'}\n"
            f"🆔 ID: {user.id}\n"
        )

        if user.username:
            admin_message += f"📱 TG: @{user.username}\n"

        admin_message += f"\n📋 Выбранные размеры:\n{selected_list}"

        await bot.send_message(ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML")

        logger.info(f"User {user.id} subscribed to offices: {selected_sizes}")

    except Exception as e:
        logger.error(f"Error creating office subscription for user {user.id}: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при оформлении подписки.\n"
            "Пожалуйста, попробуйте позже или обратитесь в поддержку."
        )

    finally:
        await state.clear()
        await callback.answer()


@router.callback_query(F.data == "office_cancel", OfficeSubscriptionStates.selecting_sizes)
async def cancel_subscription(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса подписки."""
    await state.clear()
    await callback.message.edit_text("❌ Подписка отменена.")
    await callback.answer()


@router.message(Command("unsubscribe_office"))
async def cmd_unsubscribe_office(message: Message):
    """Отмена подписки на офисы."""
    user_id = message.from_user.id

    try:
        api_client = await get_api_client()
        response = await api_client._make_request("DELETE", f"/office-subscriptions/user/{user_id}")

        if "error" in response:
            await message.answer("ℹ️ У вас нет активной подписки на офисы.")
            return

        await message.answer(
            "✅ Подписка на уведомления об офисах отменена.\n\n"
            "Вы можете снова подписаться в любое время командой /subscribe_office"
        )

        logger.info(f"User {user_id} unsubscribed from offices")

    except Exception as e:
        logger.error(f"Error unsubscribing user {user_id}: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


def register_office_subscription_handlers(dp):
    """Регистрация обработчиков подписки на офисы."""
    dp.include_router(router)
    logger.info("Office subscription handlers registered")
