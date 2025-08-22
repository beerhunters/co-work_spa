"""
Главный файл бота с поддержкой работы через API
"""

import asyncio
import os
import traceback
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

import pytz
from aiogram import Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, CallbackQuery, Message, Update

from bot.hndlrs.booking_hndlr import register_book_handlers
from bot.hndlrs.registration_hndlr import register_reg_handlers
from bot.hndlrs.ticket_hndlr import register_ticket_handlers
from utils.api_client import get_api_client, close_api_client
from utils.bot_instance import get_bot
from utils.logger import get_logger

logger = get_logger(__name__)
LOGS_CHAT_ID = os.getenv("FOR_LOGS")


class ErrorLoggingMiddleware(BaseMiddleware):
    """
    Middleware для перехвата и логирования ошибок в обработчиках сообщений и callback-запросов.
    Отправляет уведомления об ошибках в группу, указанную в FOR_LOGS.
    """

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        try:
            # Вызываем обработчик события
            return await handler(event, data)
        except Exception as e:
            # Формируем информацию об ошибке
            bot = data.get("bot") or get_bot()
            event_type = "unknown"
            user_id = "Неизвестно"
            username = "Неизвестно"
            event_text = "Неизвестно"

            if isinstance(event, Message):
                event_type = "message"
                user_id = str(event.from_user.id)
                username = (
                    event.from_user.username
                    or event.from_user.full_name
                    or "Не указано"
                )
                event_text = event.text or event.caption or "Пустое сообщение"
            elif isinstance(event, CallbackQuery):
                event_type = "callback_query"
                user_id = str(event.from_user.id)
                username = (
                    event.from_user.username
                    or event.from_user.full_name
                    or "Не указано"
                )
                event_text = event.data or "Пустой callback"

            # Формируем стек вызовов
            stack_trace = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )

            # Форматируем сообщение об ошибке
            moscow_tz = pytz.timezone("Europe/Moscow")
            error_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
            error_message = (
                f"⚠️ <b>ОШИБКА В БОТЕ</b>\n\n"
                f"📌 <b>Тип события:</b> {event_type}\n"
                f"👤 <b>Пользователь:</b> ID {user_id} (@{username})\n"
                f"📝 <b>Событие:</b> <code>{event_text}</code>\n"
                f"🔴 <b>Ошибка:</b> {type(e).__name__}: {str(e)}\n"
                f"📜 <b>Стек вызовов:</b>\n<code>{stack_trace}</code>\n"
                f"⏰ <b>Время:</b> {error_time}"
            )

            # Логируем ошибку
            logger.error(
                f"Ошибка при обработке {event_type} от пользователя {user_id}: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

            # Отправляем уведомление в группу, если FOR_LOGS задан
            if LOGS_CHAT_ID:
                try:
                    await bot.send_message(
                        chat_id=LOGS_CHAT_ID, text=error_message, parse_mode="HTML"
                    )
                except Exception as send_error:
                    logger.error(
                        f"Не удалось отправить ошибку в группу {LOGS_CHAT_ID}: {str(send_error)}"
                    )

            # Пропускаем исключение дальше
            raise


async def main() -> None:
    """
    Основная функция запуска бота.

    Сложность: O(1).
    """
    logger.info("Запуск бота...")

    # Инициализируем API клиента
    api_client = await get_api_client()
    logger.info("API клиент инициализирован")

    # Проверяем соединение с API
    try:
        # Пытаемся получить статистику как тест соединения
        test_result = await api_client._make_request("GET", "/")
        if "error" not in test_result:
            logger.info("Соединение с API установлено успешно")
        else:
            logger.error("Ошибка соединения с API")
            return
    except Exception as e:
        logger.error(f"Не удалось подключиться к API: {e}")
        return

    # Получаем бота
    bot = get_bot()

    # Создаем диспетчер с хранилищем в памяти
    dp = Dispatcher(storage=MemoryStorage())

    # Добавляем middleware для обработки ошибок
    dp.message.middleware(ErrorLoggingMiddleware())
    dp.callback_query.middleware(ErrorLoggingMiddleware())

    # Регистрируем обработчики
    register_reg_handlers(dp)
    register_book_handlers(dp)
    register_ticket_handlers(dp)

    logger.info("Обработчики зарегистрированы")

    # Создаем файл-индикатор для healthcheck
    try:
        with open("/app/data/bot_initialized", "w") as f:
            f.write("1")
        logger.info("Файл инициализации создан")
    except Exception as e:
        logger.error(f"Не удалось создать файл инициализации: {e}")

    # Запускаем polling
    try:
        logger.info("Бот успешно запущен и ожидает сообщений...")
        await dp.start_polling(bot)
    finally:
        # Закрываем соединения при остановке
        await close_api_client()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
