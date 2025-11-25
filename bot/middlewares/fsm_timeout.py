"""
FSM Timeout Middleware - автоматическая очистка состояний FSM при бездействии.

Этот middleware отслеживает время последней активности пользователя в FSM
и автоматически очищает состояние если прошло более 5 минут.
"""
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.utils.localization import get_text
from utils.logger import get_logger

logger = get_logger(__name__)


class FSMTimeoutMiddleware(BaseMiddleware):
    """
    Middleware для автоматической очистки FSM состояний при таймауте.

    Особенности:
    - Таймаут: 5 минут (300 секунд)
    - Исключение для Booking.STATUS_PAYMENT (может ждать дольше для оплаты)
    - Отправляет понятное сообщение пользователю при таймауте
    - Логирует таймауты для аналитики
    """

    # Таймаут в секундах (5 минут)
    TIMEOUT_SECONDS = 300

    # Состояния, которые могут ждать дольше (например, оплата)
    EXCLUDED_STATES = ["Booking:STATUS_PAYMENT"]

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        """
        Обрабатывает входящее событие и проверяет таймаут FSM.

        Args:
            handler: Следующий обработчик в цепочке
            event: Событие (Message или CallbackQuery)
            data: Дополнительные данные (включая state)

        Returns:
            Результат выполнения handler
        """
        state: FSMContext = data.get("state")

        if not state:
            # Нет FSM контекста, пропускаем
            return await handler(event, data)

        # Получаем текущее состояние FSM
        current_state = await state.get_state()

        if not current_state:
            # Пользователь не находится ни в каком FSM состоянии
            # Обновляем timestamp и продолжаем
            await self._update_timestamp(state)
            return await handler(event, data)

        # Проверяем исключённые состояния
        if current_state in self.EXCLUDED_STATES:
            # Это состояние может ждать дольше, пропускаем проверку таймаута
            await self._update_timestamp(state)
            return await handler(event, data)

        # Получаем данные FSM
        fsm_data = await state.get_data()
        last_activity = fsm_data.get("_last_activity")

        if last_activity:
            # Проверяем таймаут
            try:
                last_activity_time = datetime.fromisoformat(last_activity)
                time_passed = datetime.now() - last_activity_time

                if time_passed > timedelta(seconds=self.TIMEOUT_SECONDS):
                    # Таймаут! Очищаем состояние
                    await self._handle_timeout(event, state, current_state, time_passed)
                    # Возвращаем None чтобы не выполнять handler
                    return None

            except (ValueError, TypeError) as e:
                # Ошибка парсинга даты, логируем и обновляем timestamp
                logger.warning(f"Ошибка парсинга last_activity timestamp: {e}")
                await self._update_timestamp(state)
        else:
            # Первая активность в этом состоянии, устанавливаем timestamp
            await self._update_timestamp(state)

        # Обновляем timestamp перед выполнением handler
        await self._update_timestamp(state)

        # Продолжаем выполнение handler
        return await handler(event, data)

    async def _update_timestamp(self, state: FSMContext) -> None:
        """
        Обновляет timestamp последней активности в FSM данных.

        Args:
            state: FSM контекст
        """
        try:
            await state.update_data(_last_activity=datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Ошибка обновления timestamp в FSM: {e}")

    async def _handle_timeout(
        self,
        event: Message | CallbackQuery,
        state: FSMContext,
        current_state: str,
        time_passed: timedelta
    ) -> None:
        """
        Обрабатывает таймаут FSM состояния.

        Args:
            event: Событие (Message или CallbackQuery)
            state: FSM контекст
            current_state: Текущее состояние FSM
            time_passed: Сколько времени прошло
        """
        user_id = event.from_user.id
        language_code = event.from_user.language_code or "ru"

        # Логируем таймаут для аналитики
        logger.info(
            f"FSM timeout для пользователя {user_id}",
            extra={
                "user_id": user_id,
                "state": current_state,
                "time_passed_seconds": time_passed.total_seconds(),
                "timeout_threshold": self.TIMEOUT_SECONDS,
            }
        )

        # Получаем данные FSM перед очисткой для логирования
        fsm_data = await state.get_data()
        logger.debug(f"FSM data перед очисткой: {fsm_data}")

        # Очищаем состояние
        await state.clear()

        # Определяем тип сообщения в зависимости от состояния
        if current_state.startswith("Booking"):
            # Таймаут при бронировании
            message_text = get_text(language_code, "fsm.timeout_booking")
        elif current_state.startswith("Registration"):
            # Таймаут при регистрации
            message_text = get_text(language_code, "fsm.timeout_registration")
        elif current_state.startswith("TicketForm"):
            # Таймаут при создании тикета
            message_text = get_text(language_code, "fsm.timeout_ticket")
        else:
            # Общий таймаут
            message_text = get_text(language_code, "fsm.timeout_message")

        # Отправляем сообщение пользователю
        try:
            if isinstance(event, Message):
                await event.answer(message_text)
            elif isinstance(event, CallbackQuery):
                # Для callback query отвечаем через alert и отправляем новое сообщение
                await event.answer(
                    get_text(language_code, "fsm.timeout_alert"),
                    show_alert=True
                )
                await event.message.answer(message_text)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения о таймауте: {e}")
