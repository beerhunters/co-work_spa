from typing import Optional
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from utils.bot_instance import init_bot, get_bot
from utils.logger import init_simple_logging, get_logger
from bot.hndlrs.booking_hndlr import register_book_handlers
from bot.hndlrs.registration_hndlr import register_reg_handlers
from bot.hndlrs.ticket_hndlr import register_ticket_handlers
from models.models import init_db, create_admin
import os
import asyncio
import traceback
from datetime import datetime
import pytz

logger = init_simple_logging("CoworkingBot")
LOGS_CHAT_ID = os.getenv("FOR_LOGS")


class ErrorLoggingMiddleware(BaseMiddleware):
    """Middleware для логирования ошибок.

    Сложность: O(1) для обработки событий, O(n) для форматирования stack trace.
    """

    async def __call__(self, handler, event: Update, data: dict) -> Optional[dict]:
        try:
            return await handler(event, data)
        except Exception as e:
            bot = data.get("bot") or get_bot()
            event_type = "unknown"
            user_id = "Неизвестно"
            username = "Неизвестно"
            event_text = "Неизвестно"
            if event.message:
                event_type = "message"
                user_id = str(event.message.from_user.id)
                username = event.message.from_user.username or "Неизвестно"
                event_text = (
                    event.message.text or event.message.caption or "Пустое сообщение"
                )
            elif event.callback_query:
                event_type = "callback_query"
                user_id = str(event.callback_query.from_user.id)
                username = event.callback_query.from_user.username or "Неизвестно"
                event_text = event.callback_query.data or "Пустой callback"
            stack_trace = "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            moscow_tz = pytz.timezone("Europe/Moscow")
            error_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
            error_message = (
                f"❗ <b>Ошибка в боте</b>\n"
                f"⏰ <b>Время:</b> {error_time}\n"
                f"👤 <b>Пользователь:</b> {username} (ID: {user_id})\n"
                f"📩 <b>Тип события:</b> {event_type}\n"
                f"📝 <b>Текст:</b> {event_text}\n"
                f"⚠️ <b>Ошибка:</b> {str(e)}\n"
                f"📜 <b>Stack trace:</b>\n<code>{stack_trace}</code>"
            )
            logger.error(
                f"Ошибка: {str(e)}, пользователь: {user_id}, событие: {event_type}"
            )
            if LOGS_CHAT_ID:
                await bot.send_message(LOGS_CHAT_ID, error_message, parse_mode="HTML")
            raise


async def main() -> None:
    """Основная функция для запуска бота.

    Сложность: O(1).
    """
    try:
        init_db()
        admin_login = os.getenv("ADMIN_LOGIN", "admin")
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        create_admin(admin_login, admin_password)
        bot = get_bot()
        dp = Dispatcher(storage=MemoryStorage())
        dp.message.middleware(ErrorLoggingMiddleware())
        dp.callback_query.middleware(ErrorLoggingMiddleware())
        register_reg_handlers(dp)
        register_book_handlers(dp)
        register_ticket_handlers(dp)
        await dp.start_polling(bot)
        with open("/data/bot_initialized", "w") as f:
            f.write("initialized")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
