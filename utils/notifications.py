"""
Утилиты для отправки уведомлений пользователям.

Этот модуль содержит функции для отправки различных типов уведомлений
через Telegram бота, включая уведомления о бронированиях, платежах и других событиях.
"""
from dependencies import get_bot
from utils.logger import get_logger

logger = get_logger(__name__)


async def send_booking_update_notification(
    user_telegram_id: int, booking_data: dict, tariff_data: dict
) -> None:
    """
    Отправляет пользователю уведомление об изменении брони.

    Args:
        user_telegram_id: Telegram ID пользователя
        booking_data: Данные бронирования (visit_date, visit_time, duration, amount)
        tariff_data: Данные тарифа (name)
    """
    try:
        bot = get_bot()

        # Форматирование даты
        visit_date = booking_data.get("visit_date")
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            date_str = str(visit_date)

        # Форматирование времени (если есть)
        time_str = ""
        visit_time = booking_data.get("visit_time")
        if visit_time:
            if hasattr(visit_time, "strftime"):
                time_str = f"\n🕐 <b>Время:</b> {visit_time.strftime('%H:%M')}"
            else:
                time_str = f"\n🕐 <b>Время:</b> {visit_time}"

        # Длительность (если есть)
        duration_str = ""
        duration = booking_data.get("duration")
        if duration:
            duration_str = f"\n⏱ <b>Длительность:</b> {duration} ч."

        message_text = f"""
📝 <b>Ваше бронирование изменено</b>

📋 <b>Тариф:</b> {tariff_data.get('name', 'Неизвестно')}
📅 <b>Дата:</b> {date_str}{time_str}{duration_str}

💰 <b>Сумма:</b> {booking_data.get('amount', 0):.0f} ₽

ℹ️ Изменения внесены администратором.
"""

        await bot.send_message(
            chat_id=user_telegram_id, text=message_text, parse_mode="HTML"
        )

        logger.info(
            f"Уведомление об изменении брони отправлено пользователю {user_telegram_id}"
        )

    except Exception as e:
        logger.error(
            f"Ошибка отправки уведомления об изменении брони пользователю {user_telegram_id}: {e}"
        )
