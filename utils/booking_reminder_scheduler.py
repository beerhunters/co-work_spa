import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import DatabaseManager, Booking, User, Tariff, MOSCOW_TZ
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID

logger = get_logger(__name__)


async def check_and_send_daily_tariff_notifications():
    """
    Проверяет дневные бронирования (Тестовый день, Опенспейс на день) и отправляет уведомления.
    Запускается один раз в день в конце рабочего дня (20:00).
    """
    logger.info("Проверка дневных бронирований...")

    def _get_daily_bookings(session):
        today = datetime.now(MOSCOW_TZ).date()

        # Находим бронирования на сегодня с дневными тарифами
        bookings = session.query(Booking).join(Booking.tariff).filter(
            Booking.visit_date == today,
            Booking.confirmed == True,
            Booking.paid == True,
            Booking.notification_sent == False,
            # Дневные тарифы: Тестовый день или Опенспейс на день
            (Tariff.name.like('%Тестовый день%') | Tariff.name.like('%Опенспейс на день%'))
        ).all()

        daily_list = []
        for booking in bookings:
            daily_list.append({
                'booking_id': booking.id,
                'user_id': booking.user_id,
                'user_telegram_id': booking.user.telegram_id if booking.user else None,
                'user_name': booking.user.full_name if booking.user else 'Неизвестно',
                'tariff_name': booking.tariff.name if booking.tariff else 'Неизвестно',
                'visit_date': booking.visit_date,
            })

        return daily_list

    try:
        daily_bookings = DatabaseManager.safe_execute(_get_daily_bookings)

        if not daily_bookings:
            logger.info("Нет дневных бронирований для уведомления.")
            return

        logger.info(f"Найдено {len(daily_bookings)} дневных бронирований.")

        bot = get_bot()
        if not bot:
            logger.warning("Бот недоступен, уведомления не отправлены.")
            return

        for booking_data in daily_bookings:
            try:
                # Уведомление администратору о завершении дневного тарифа
                admin_message = (
                    f"📅 Завершён дневной тариф\n\n"
                    f"👤 Пользователь: {booking_data['user_name']} (ID: {booking_data['user_id']})\n"
                    f"📋 Тариф: {booking_data['tariff_name']}\n"
                    f"📅 Дата: {booking_data['visit_date'].strftime('%d.%m.%Y')}\n\n"
                    f"Рабочий день завершён."
                )
                await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
                logger.info(f"Уведомление администратору отправлено: booking_id={booking_data['booking_id']}")

                await asyncio.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Ошибка отправки уведомления для booking_id={booking_data['booking_id']}: {e}")

        logger.info(f"Рассылка завершена. Всего: {len(daily_bookings)}")

        # Отмечаем уведомления как отправленные
        def _mark_notifications_sent(session):
            for booking_data in daily_bookings:
                booking = session.query(Booking).filter_by(id=booking_data['booking_id']).first()
                if booking:
                    booking.notification_sent = True
            session.commit()
            logger.info(f"Отмечено {len(daily_bookings)} бронирований как уведомленные.")

        DatabaseManager.safe_execute(_mark_notifications_sent)

    except Exception as e:
        logger.error(f"Ошибка при проверке дневных бронирований: {e}")


def start_booking_reminder_scheduler():
    """Запускает планировщик напоминаний о дневных бронированиях."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Проверка дневных тарифов - один раз в день в 20:00
    # Почасовые бронирования теперь обрабатываются через Celery delayed tasks
    scheduler.add_job(
        check_and_send_daily_tariff_notifications,
        "cron",
        hour=20,
        minute=0,
        id="daily_tariff_notifications",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("📅 Планировщик напоминаний о бронированиях запущен")
    logger.info("   - Дневные тарифы: ежедневно в 20:00")
    logger.info("   - Почасовые бронирования: обрабатываются через Celery delayed tasks")

    return scheduler
