"""
Error Handler Helper - централизованная обработка ошибок для бота.

Этот модуль предоставляет функции для отправки понятных сообщений об ошибках
пользователям с автоматическим логированием и категоризацией ошибок.
"""
from enum import Enum
from typing import Optional, Union
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import aiohttp

from bot.utils.localization import get_text
from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorCategory(Enum):
    """Категории ошибок для классификации."""
    NETWORK = "network"           # Сетевые ошибки (API недоступен)
    DATA = "data"                 # Ошибки данных (пользователь не найден)
    VALIDATION = "validation"     # Ошибки валидации (неверный формат)
    BUSINESS = "business"         # Ошибки бизнес-логики (тариф недоступен)
    SYSTEM = "system"             # Критические системные ошибки
    PAYMENT = "payment"           # Ошибки оплаты


def _get_error_category(error: Exception) -> ErrorCategory:
    """
    Автоматически определяет категорию ошибки по типу исключения.

    Args:
        error: Исключение

    Returns:
        Категория ошибки
    """
    if isinstance(error, (aiohttp.ClientError, aiohttp.ServerTimeoutError, TimeoutError)):
        return ErrorCategory.NETWORK
    elif isinstance(error, (KeyError, AttributeError)):
        return ErrorCategory.DATA
    elif isinstance(error, (ValueError, TypeError)):
        return ErrorCategory.VALIDATION
    else:
        return ErrorCategory.SYSTEM


def _create_support_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с кнопкой "Связаться с поддержкой".

    Args:
        lang: Код языка

    Returns:
        Inline клавиатура
    """
    button_text = get_text(lang, "buttons.contact_support")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=button_text,
            callback_data="create_ticket"
        )]
    ])
    return keyboard


async def send_user_error(
    event: Union[Message, CallbackQuery],
    error_key: str,
    lang: str = "ru",
    error: Optional[Exception] = None,
    show_support: bool = False,
    state: Optional[FSMContext] = None,
    **format_kwargs
) -> None:
    """
    Отправляет понятное сообщение об ошибке пользователю.

    Функция автоматически:
    - Логирует ошибку с контекстом
    - Отправляет локализованное сообщение пользователю
    - Добавляет кнопку поддержки при необходимости
    - Классифицирует ошибку для аналитики

    Args:
        event: Message или CallbackQuery событие
        error_key: Ключ сообщения в локализации (например, "errors.api_unavailable")
        lang: Код языка (по умолчанию "ru")
        error: Объект исключения (для логирования)
        show_support: Показать кнопку "Связаться с поддержкой"
        state: FSM контекст (для логирования состояния)
        **format_kwargs: Дополнительные параметры для форматирования сообщения

    Example:
        >>> await send_user_error(
        ...     message,
        ...     "errors.tariff_not_available",
        ...     lang="ru",
        ...     error=e,
        ...     tariff_name="Час работы"
        ... )
    """
    user_id = event.from_user.id
    username = event.from_user.username or "unknown"

    # Получаем локализованное сообщение
    error_message = get_text(lang, error_key, **format_kwargs)

    # Определяем категорию ошибки
    error_category = _get_error_category(error) if error else ErrorCategory.BUSINESS

    # Собираем контекст для логирования
    log_context = {
        "user_id": user_id,
        "username": username,
        "error_key": error_key,
        "error_category": error_category.value,
        "event_type": "message" if isinstance(event, Message) else "callback",
    }

    # Добавляем информацию о состоянии FSM
    if state:
        try:
            current_state = await state.get_state()
            fsm_data = await state.get_data()
            log_context["fsm_state"] = current_state
            log_context["fsm_data_keys"] = list(fsm_data.keys()) if fsm_data else []
        except Exception as e:
            logger.warning(f"Не удалось получить FSM данные для логирования: {e}")

    # Логируем ошибку
    if error:
        logger.error(
            f"Ошибка для пользователя {user_id}: {error_key}",
            extra=log_context,
            exc_info=error
        )
    else:
        logger.warning(
            f"Бизнес-ошибка для пользователя {user_id}: {error_key}",
            extra=log_context
        )

    # Создаём клавиатуру если нужна поддержка
    reply_markup = _create_support_keyboard(lang) if show_support else None

    # Отправляем сообщение пользователю
    try:
        if isinstance(event, Message):
            await event.answer(error_message, reply_markup=reply_markup)
        elif isinstance(event, CallbackQuery):
            # Для callback query пробуем редактировать сообщение
            try:
                await event.message.edit_text(error_message, reply_markup=reply_markup)
            except Exception:
                # Если не получилось отредактировать, отвечаем через answer
                await event.answer(error_message[:200], show_alert=True)
                await event.message.answer(error_message, reply_markup=reply_markup)
            finally:
                await event.answer()  # Убираем часики с callback button
    except Exception as send_error:
        logger.error(
            f"Не удалось отправить сообщение об ошибке пользователю {user_id}: {send_error}",
            extra=log_context
        )


async def handle_api_error(
    event: Union[Message, CallbackQuery],
    error: Exception,
    lang: str = "ru",
    operation: str = "operation",
    state: Optional[FSMContext] = None
) -> None:
    """
    Специализированный обработчик для ошибок API.

    Автоматически определяет тип ошибки API и отправляет соответствующее сообщение.

    Args:
        event: Message или CallbackQuery событие
        error: Исключение от API
        lang: Код языка
        operation: Описание операции для логирования
        state: FSM контекст

    Example:
        >>> try:
        ...     user = await api_client.get_user(user_id)
        ... except Exception as e:
        ...     await handle_api_error(message, e, lang, "get_user", state)
    """
    user_id = event.from_user.id
    logger.error(f"API error during {operation} for user {user_id}: {error}")

    # Определяем тип ошибки API
    if isinstance(error, aiohttp.ServerTimeoutError):
        error_key = "errors.network_timeout"
    elif isinstance(error, aiohttp.ClientError):
        error_key = "errors.api_unavailable"
    else:
        error_key = "errors.api_error"

    await send_user_error(
        event,
        error_key,
        lang=lang,
        error=error,
        show_support=True,
        state=state,
        operation=operation
    )


async def handle_validation_error(
    event: Union[Message, CallbackQuery],
    field_name: str,
    lang: str = "ru",
    example: Optional[str] = None
) -> None:
    """
    Обработчик ошибок валидации с примером правильного формата.

    Args:
        event: Message или CallbackQuery событие
        field_name: Название поля (date, phone, email, etc.)
        lang: Код языка
        example: Пример правильного значения

    Example:
        >>> await handle_validation_error(
        ...     message,
        ...     "phone",
        ...     lang="ru",
        ...     example="+7 900 123-45-67"
        ... )
    """
    error_key = f"errors.invalid_{field_name}"

    format_kwargs = {}
    if example:
        format_kwargs["example"] = example

    await send_user_error(
        event,
        error_key,
        lang=lang,
        show_support=False,
        **format_kwargs
    )
