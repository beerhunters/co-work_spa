"""
Главный файл бота с поддержкой работы через API
"""

import asyncio
import os
import logging
from datetime import datetime

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramNetworkError, TelegramServerError

from bot.hndlrs.booking_hndlr import register_book_handlers
from bot.hndlrs.registration_hndlr import register_reg_handlers
from bot.hndlrs.ticket_hndlr import register_ticket_handlers
from bot.middlewares.fsm_timeout import FSMTimeoutMiddleware
from utils.api_client import get_api_client, close_api_client
from utils.bot_instance import get_bot
from utils.logger import get_logger
from utils.error_notifier import notify_error
from config import ADMIN_URL

logger = get_logger(__name__)
LOGS_CHAT_ID = os.getenv("FOR_LOGS")

# Дедупликация ошибок теперь обрабатывается в TelegramLogHandler


class BanCheckMiddleware:
    """
    Middleware для проверки бана пользователя.
    Если пользователь забанен, отправляет ему сообщение и блокирует дальнейшую обработку.
    """

    def __init__(self):
        self.api_client = None

    async def __call__(self, handler, event, data):
        # Получаем пользователя из события
        user = None
        if hasattr(event, "from_user") and event.from_user:
            user = event.from_user
        elif hasattr(event, "message") and hasattr(event.message, "from_user"):
            user = event.message.from_user

        if user:
            try:
                # Получаем API клиента
                if not self.api_client:
                    self.api_client = await get_api_client()

                # Проверяем, забанен ли пользователь
                user_data = await self.api_client._make_request(
                    "GET", f"/users/telegram/{user.id}"
                )

                if user_data and user_data.get("is_banned"):
                    # Пользователь забанен - отправляем сообщение и блокируем обработку
                    ban_reason = user_data.get("ban_reason", "Не указана")

                    # ban_message = (
                    #     f"⛔️ Ваш доступ к боту ограничен.\n\n"
                    #     f"Для использования бота свяжитесь с администратором: {ADMIN_URL}"
                    # )
                    ban_message = (
                        # f"⛔️ Ваш доступ к боту ограничен.\n\n"
                        f"Свяжитесь с администратором: {ADMIN_URL}"
                    )

                    # Отправляем сообщение пользователю
                    from utils.bot_instance import get_bot

                    bot = get_bot()

                    # Определяем, что отправлять - сообщение или ответ на callback
                    if hasattr(event, "message") and hasattr(event, "answer"):
                        # Это callback query
                        await event.answer(
                            "⛔️ Ваш доступ к боту ограничен. Обратитесь к администратору.",
                            show_alert=True,
                        )
                    else:
                        # Это обычное сообщение
                        await bot.send_message(user.id, ban_message)

                    logger.info(
                        f"Заблокирован доступ для забаненного пользователя {user.id}"
                    )

                    # Блокируем дальнейшую обработку
                    return None

            except Exception as e:
                # Если не удалось проверить статус бана, пропускаем проверку
                # (чтобы не блокировать работу бота)
                logger.debug(
                    f"Не удалось проверить статус бана пользователя {user.id}: {e}"
                )

        # Пользователь не забанен или проверка не прошла - продолжаем обработку
        return await handler(event, data)


class ErrorLoggingMiddleware:
    """
    Упрощенный middleware для логирования ошибок.
    Использует централизованную систему уведомлений.
    """

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception as e:
            # Определяем тип события для контекста
            event_type = "unknown"
            user_id = "unknown"

            if hasattr(event, "from_user") and event.from_user:
                user_id = str(event.from_user.id)

            if hasattr(event, "text"):
                event_type = "message"
            elif hasattr(event, "data"):
                event_type = "callback_query"

            # Отправляем ОДНО уведомление через централизованную систему
            notify_error(
                exc_info=(type(e), e, e.__traceback__),
                message=f"Ошибка в bot handler ({event_type}) от пользователя {user_id}",
                context={
                    "event_type": event_type,
                    "user_id": user_id,
                    "source": "bot_middleware",
                },
            )

            # Логируем локально БЕЗ отправки в Telegram
            # (отключаем полностью, чтобы избежать дублирования)
            pass

            # Пропускаем ошибку дальше
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

    # Проверяем на неожиданное завершение (краш) перед полным запуском
    try:
        from utils.system_status import (
            detect_unexpected_shutdown,
            send_unexpected_shutdown_notification,
        )

        crash_info = detect_unexpected_shutdown()
        if crash_info:
            logger.warning(
                "🔴 Бот обнаружил неожиданное завершение системы в предыдущем запуске!"
            )
            # Уведомление уже может быть отправлено web компонентом, но на всякий случай логируем
            logger.info("📱 Web компонент должен был отправить уведомление о крахе")
        else:
            logger.info(
                "✅ Предыдущее завершение бота было нормальным (или первый запуск)"
            )
    except Exception as e:
        logger.warning(f"Ошибка проверки на неожиданное завершение в боте: {e}")

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

    # Отключаем логирование ошибок диспетчера в Telegram
    # (устанавливаем уровень выше ERROR чтобы не логировать через handlers)
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_dispatcher_logger = logging.getLogger("aiogram.dispatcher.dispatcher")

    # Устанавливаем уровень выше ERROR для предотвращения отправки в Telegram
    for logger_name in [
        "aiogram",
        "aiogram.dispatcher",
        "aiogram.dispatcher.dispatcher",
    ]:
        aiogram_log = logging.getLogger(logger_name)
        # Оставляем локальное логирование но НЕ отправляем в Telegram
        aiogram_log.setLevel(logging.CRITICAL + 1)  # Отключаем ERROR логи

    # Добавляем middleware для проверки бана (должен быть первым)
    dp.message.middleware(BanCheckMiddleware())
    dp.callback_query.middleware(BanCheckMiddleware())

    # Добавляем middleware для FSM timeout (автоматическая очистка состояний через 5 минут)
    dp.message.middleware(FSMTimeoutMiddleware())
    dp.callback_query.middleware(FSMTimeoutMiddleware())

    # Добавляем упрощенный middleware для логирования ошибок
    dp.message.middleware(ErrorLoggingMiddleware())
    dp.callback_query.middleware(ErrorLoggingMiddleware())

    # Регистрируем обработчики
    register_reg_handlers(dp)
    register_book_handlers(dp)
    register_ticket_handlers(dp)

    logger.info("Обработчики зарегистрированы")

    # Блокируем все автоматические Telegram уведомления
    from utils.telegram_filter import block_all_telegram_logging

    block_all_telegram_logging()

    # Регистрируем готовность bot компонента
    from utils.system_status import register_component_startup

    register_component_startup("bot")

    # Создаем файл-индикатор для healthcheck
    try:
        with open("/app/data/bot_initialized", "w") as f:
            f.write("1")
        logger.info("Файл инициализации создан")
    except Exception as e:
        logger.error(f"Не удалось создать файл инициализации: {e}")

    # Запускаем polling с обработкой сетевых ошибок
    try:
        logger.info("Бот успешно запущен и ожидает сообщений...")

        while True:
            try:
                await dp.start_polling(bot)
                break  # Выходим из цикла при нормальном завершении
            except (
                TelegramNetworkError,
                TelegramServerError,
                ConnectionError,
            ) as net_error:
                error_type = type(net_error).__name__
                error_msg = str(net_error)

                # Логируем ошибку - уведомление отправится через TelegramLogHandler
                logger.error(
                    f"Сетевая ошибка polling (попытка переподключения): {error_type}: {error_msg}"
                )

                # Ждем перед переподключением
                await asyncio.sleep(30)
                logger.info("Попытка переподключения к Telegram API...")

            except Exception as e:
                # Для других ошибок просто логируем и выходим
                logger.error(
                    f"Критическая ошибка polling: {type(e).__name__}: {str(e)}",
                    exc_info=True,
                )
                break

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
