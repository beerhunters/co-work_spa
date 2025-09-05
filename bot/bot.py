"""
Главный файл бота с поддержкой работы через API
"""

import asyncio
import os
import traceback
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict
import hashlib

import pytz
from aiogram import Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, CallbackQuery, Message, Update
from aiogram.exceptions import TelegramNetworkError, TelegramServerError

from bot.hndlrs.booking_hndlr import register_book_handlers
from bot.hndlrs.registration_hndlr import register_reg_handlers
from bot.hndlrs.ticket_hndlr import register_ticket_handlers
from utils.api_client import get_api_client, close_api_client
from utils.bot_instance import get_bot
from utils.logger import get_logger

logger = get_logger(__name__)
LOGS_CHAT_ID = os.getenv("FOR_LOGS")

# Система дедупликации ошибок
error_cache = {}
ERROR_CACHE_TTL = 300  # 5 минут
NETWORK_ERROR_COOLDOWN = 60  # 1 минута для сетевых ошибок


def should_send_error(error_type: str, error_msg: str, is_network_error: bool = False) -> bool:
    """
    Проверяет, нужно ли отправлять уведомление об ошибке.
    Предотвращает спам одинаковыми ошибками.
    """
    now = datetime.now()
    
    # Создаем хэш ошибки для дедупликации
    error_hash = hashlib.md5(f"{error_type}:{error_msg}".encode()).hexdigest()
    
    # Проверяем кэш на наличие такой ошибки
    if error_hash in error_cache:
        last_sent, count = error_cache[error_hash]
        
        # Определяем период охлаждения
        cooldown = NETWORK_ERROR_COOLDOWN if is_network_error else ERROR_CACHE_TTL
        
        # Если прошло недостаточно времени - не отправляем
        if now - last_sent < timedelta(seconds=cooldown):
            error_cache[error_hash] = (last_sent, count + 1)
            return False
    
    # Обновляем кэш и разрешаем отправку
    error_cache[error_hash] = (now, 1)
    
    # Очистка старых записей из кэша
    cleanup_error_cache()
    
    return True


def cleanup_error_cache():
    """Очищает старые записи из кэша ошибок"""
    now = datetime.now()
    expired_keys = []
    
    for error_hash, (last_sent, count) in error_cache.items():
        if now - last_sent > timedelta(seconds=ERROR_CACHE_TTL):
            expired_keys.append(error_hash)
    
    for key in expired_keys:
        del error_cache[key]


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

            # Проверяем, является ли это сетевой ошибкой
            is_network_error = isinstance(e, (TelegramNetworkError, TelegramServerError, ConnectionError))
            
            # Проверяем, нужно ли отправлять уведомление
            error_type = type(e).__name__
            error_msg = str(e)
            
            if should_send_error(error_type, error_msg, is_network_error):
                # Добавляем информацию о повторах, если есть
                error_hash = hashlib.md5(f"{error_type}:{error_msg}".encode()).hexdigest()
                repeat_count = error_cache.get(error_hash, (None, 1))[1]
                
                if repeat_count > 1:
                    error_message += f"\n🔄 <b>Повторов:</b> {repeat_count}"
                
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
            else:
                # Логируем, что ошибка была подавлена
                logger.debug(f"Уведомление об ошибке {error_type} подавлено (дедупликация)")

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

    # Запускаем polling с обработкой сетевых ошибок
    try:
        logger.info("Бот успешно запущен и ожидает сообщений...")
        
        while True:
            try:
                await dp.start_polling(bot)
                break  # Выходим из цикла при нормальном завершении
            except (TelegramNetworkError, TelegramServerError, ConnectionError) as net_error:
                error_type = type(net_error).__name__
                error_msg = str(net_error)
                
                # Используем дедупликацию для сетевых ошибок
                if should_send_error(error_type, error_msg, is_network_error=True):
                    moscow_tz = pytz.timezone("Europe/Moscow")
                    error_time = datetime.now(moscow_tz).strftime("%Y-%m-%d %H:%M:%S")
                    
                    network_error_message = (
                        f"🔴 🧪 <b>DEV ERROR</b>\n\n"
                        f"📍 <b>Модуль:</b> dispatcher\n"
                        f"⚙️ <b>Функция:</b> start_polling\n"
                        f"📄 <b>Строка:</b> polling loop\n"
                        f"🕐 <b>Время:</b> {error_time}\n\n"
                        f"💬 <b>Сообщение:</b>\n{error_msg}\n\n"
                        f"🔄 <b>Попытка переподключения через 30 секунд...</b>"
                    )
                    
                    if LOGS_CHAT_ID:
                        try:
                            await bot.send_message(
                                chat_id=LOGS_CHAT_ID,
                                text=network_error_message,
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass  # Игнорируем ошибки отправки уведомлений
                
                logger.error(f"Сетевая ошибка polling: {error_type}: {error_msg}")
                
                # Ждем перед переподключением
                await asyncio.sleep(30)
                logger.info("Попытка переподключения...")
                
            except Exception as e:
                # Для других ошибок просто логируем и выходим
                logger.error(f"Критическая ошибка polling: {type(e).__name__}: {str(e)}", exc_info=True)
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
