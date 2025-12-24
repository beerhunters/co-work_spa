"""
Celery tasks for booking notifications.
"""
import asyncio
from datetime import datetime
from typing import Dict, Optional

from celery import Task

from celery_app import celery_app
from config import MOSCOW_TZ, ADMIN_TELEGRAM_ID
from models.models import Booking, User, Tariff, DatabaseManager
from utils.logger import get_logger
from dependencies import get_bot

logger = get_logger(__name__)


class BookingTask(Task):
    """Base task for booking operations with callbacks."""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Booking task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Booking task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Booking task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=BookingTask,
    name='tasks.booking_tasks.send_booking_expiration_notification',
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def send_booking_expiration_notification(self, booking_id: int, is_daily_tariff: bool = False):
    """
    Celery task for sending booking expiration notification.

    Args:
        booking_id: ID of the booking that has expired
        is_daily_tariff: True for daily tariffs (Тестовый день, Опенспейс на день)

    Returns:
        Dict with result: {
            'status': 'success'|'failed',
            'booking_id': int,
            'notifications_sent': int
        }
    """
    try:
        logger.info(f"Отправка уведомления о завершении бронирования #{booking_id}")

        # Fetch booking details from database
        def _get_booking_details(session):
            booking = session.query(Booking).filter_by(id=booking_id).first()
            if not booking:
                logger.warning(f"Booking #{booking_id} not found")
                return None

            # Check if notification already sent
            if booking.notification_sent:
                logger.info(f"Notification for booking #{booking_id} already sent, skipping")
                return None

            user = booking.user
            tariff = booking.tariff

            if not user or not tariff:
                logger.warning(f"Booking #{booking_id} missing user or tariff data")
                return None

            return {
                'booking_id': booking.id,
                'user_id': user.id,
                'user_telegram_id': user.telegram_id,
                'user_name': user.full_name or 'Неизвестно',
                'user_username': user.username or None,
                'tariff_name': tariff.name,
                'visit_date': booking.visit_date,
                'visit_time': booking.visit_time,
                'duration': booking.duration
            }

        booking_data = DatabaseManager.safe_execute(_get_booking_details)

        if not booking_data:
            return {
                'status': 'skipped',
                'booking_id': booking_id,
                'notifications_sent': 0
            }

        # Get or create event loop for async operations
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Send notifications
        result = loop.run_until_complete(
            _send_notifications_async(booking_data, is_daily_tariff)
        )

        # Mark notification as sent in database
        def _mark_notification_sent(session):
            booking = session.query(Booking).filter_by(id=booking_id).first()
            if booking:
                booking.notification_sent = True
                session.commit()
                logger.info(f"Marked booking #{booking_id} notification as sent")

        DatabaseManager.safe_execute(_mark_notification_sent)

        return {
            'status': 'success',
            'booking_id': booking_id,
            'notifications_sent': result['sent_count']
        }

    except Exception as e:
        logger.error(f"Error sending booking expiration notification for #{booking_id}: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _send_notifications_async(booking_data: Dict, is_daily_tariff: bool = False) -> Dict:
    """
    Send notifications to user and admin about booking expiration.

    Args:
        booking_data: Dict with booking details
        is_daily_tariff: True for daily tariffs

    Returns:
        Dict with sent_count
    """
    bot = get_bot()
    if not bot:
        logger.error("Bot not available for sending notifications")
        raise RuntimeError("Bot not available")

    sent_count = 0

    # Формируем строку с username если есть
    username_str = f" (@{booking_data['user_username']})" if booking_data['user_username'] else ""

    if is_daily_tariff:
        # Дневные тарифы - уведомление только администратору
        try:
            admin_message = (
                f"🔔 День аренды истёк\n\n"
                f"👤 Пользователь: {booking_data['user_name']}{username_str} (ID: {booking_data['user_id']})\n"
                f"📋 Тариф: {booking_data['tariff_name']}\n"
                f"📅 Дата: {booking_data['visit_date'].strftime('%d.%m.%Y')}\n\n"
                f"⚠️ Необходимо отключить пропуск"
            )
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
            sent_count += 1
            logger.info(f"Уведомление администратору о дневном тарифе отправлено (booking #{booking_data['booking_id']})")
        except Exception as e:
            logger.error(f"Failed to send daily tariff notification to admin: {e}")
    else:
        # Почасовые тарифы - уведомление пользователю и администратору
        from datetime import datetime, timedelta
        visit_datetime_naive = datetime.combine(
            booking_data['visit_date'],
            booking_data['visit_time']
        )
        visit_datetime = MOSCOW_TZ.localize(visit_datetime_naive)
        end_datetime = visit_datetime + timedelta(hours=booking_data['duration'])
        end_time = end_datetime.time()

        # Send notification to user
        if booking_data['user_telegram_id']:
            try:
                user_message = (
                    f"⏰ Время вашего бронирования истекло\n\n"
                    f"📋 Тариф: {booking_data['tariff_name']}\n"
                    f"📅 Дата: {booking_data['visit_date'].strftime('%d.%m.%Y')}\n"
                    f"🕐 Время: {booking_data['visit_time'].strftime('%H:%M')} - "
                    f"{end_time.strftime('%H:%M')}\n"
                    f"⏱ Длительность: {booking_data['duration']} ч.\n\n"
                    f"Спасибо за посещение!"
                )
                await bot.send_message(booking_data['user_telegram_id'], user_message)
                sent_count += 1
                logger.info(f"Уведомление пользователю {booking_data['user_telegram_id']} отправлено")
            except Exception as e:
                logger.error(f"Failed to send notification to user {booking_data['user_telegram_id']}: {e}")

        # Send notification to admin
        try:
            admin_message = (
                f"⏰ Истекло время бронирования\n\n"
                f"👤 Пользователь: {booking_data['user_name']}{username_str} (ID: {booking_data['user_id']})\n"
                f"📋 Тариф: {booking_data['tariff_name']}\n"
                f"📅 Дата: {booking_data['visit_date'].strftime('%d.%m.%Y')}\n"
                f"🕐 Время: {booking_data['visit_time'].strftime('%H:%M')} - "
                f"{end_time.strftime('%H:%M')}\n"
                f"⏱ Длительность: {booking_data['duration']} ч."
            )
            await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
            sent_count += 1
            logger.info(f"Уведомление администратору отправлено")
        except Exception as e:
            logger.error(f"Failed to send notification to admin: {e}")

    return {'sent_count': sent_count}


@celery_app.task(
    bind=True,
    base=BookingTask,
    name='tasks.booking_tasks.send_rental_reminder',
    max_retries=3,
    default_retry_delay=300  # 5 minutes
)
def send_rental_reminder(self, booking_id: int):
    """
    Celery task for sending rental expiration reminder.

    Args:
        booking_id: ID of the booking

    Returns:
        Dict with result
    """
    try:
        logger.info(f"Отправка напоминания о завершении аренды для бронирования #{booking_id}")

        # Fetch booking details from database
        def _get_booking_details(session):
            booking = session.query(Booking).filter_by(id=booking_id).first()
            if not booking:
                logger.warning(f"Booking #{booking_id} not found")
                return None

            # Check if reminder already sent
            if booking.reminder_sent:
                logger.info(f"Reminder for booking #{booking_id} already sent, skipping")
                return None

            user = booking.user
            tariff = booking.tariff

            if not user or not tariff:
                logger.warning(f"Booking #{booking_id} missing user or tariff data")
                return None

            return {
                'booking_id': booking.id,
                'user_id': user.id,
                'user_telegram_id': user.telegram_id,
                'user_name': user.full_name or 'Неизвестно',
                'user_username': user.username or None,
                'tariff_name': tariff.name,
                'visit_date': booking.visit_date,
                'duration': booking.duration,
                'reminder_days': booking.reminder_days
            }

        booking_data = DatabaseManager.safe_execute(_get_booking_details)

        if not booking_data:
            return {
                'status': 'skipped',
                'booking_id': booking_id,
                'notifications_sent': 0
            }

        # Get or create event loop for async operations
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Send notifications
        result = loop.run_until_complete(
            _send_rental_reminder_async(booking_data)
        )

        # Mark reminder as sent in database
        def _mark_reminder_sent(session):
            booking = session.query(Booking).filter_by(id=booking_id).first()
            if booking:
                booking.reminder_sent = True
                session.commit()
                logger.info(f"Marked booking #{booking_id} reminder as sent")

        DatabaseManager.safe_execute(_mark_reminder_sent)

        return {
            'status': 'success',
            'booking_id': booking_id,
            'notifications_sent': result['sent_count']
        }

    except Exception as e:
        logger.error(f"Error sending rental reminder for #{booking_id}: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _send_rental_reminder_async(booking_data: Dict) -> Dict:
    """
    Send rental expiration reminder to user and admin.

    Args:
        booking_data: Dict with booking details

    Returns:
        Dict with sent_count
    """
    bot = get_bot()
    if not bot:
        logger.error("Bot not available for sending rental reminders")
        raise RuntimeError("Bot not available")

    sent_count = 0

    # Формируем строку с username если есть
    username_str = f" (@{booking_data['user_username']})" if booking_data['user_username'] else ""

    # Вычисляем дату окончания аренды
    from dateutil.relativedelta import relativedelta
    end_date = booking_data['visit_date'] + relativedelta(months=booking_data['duration'] or 1)
    days_left = booking_data['reminder_days']

    # Уведомление пользователю
    if booking_data['user_telegram_id']:
        try:
            user_message = (
                f"⏰ Напоминание о завершении аренды\n\n"
                f"📋 Тариф: {booking_data['tariff_name']}\n"
                f"📅 Дата окончания: {end_date.strftime('%d.%m.%Y')}\n"
                f"⏳ Осталось дней: {days_left}\n\n"
                f"Пожалуйста, не забудьте продлить аренду или освободить место."
            )
            await bot.send_message(booking_data['user_telegram_id'], user_message)
            sent_count += 1
            logger.info(f"Напоминание отправлено пользователю {booking_data['user_telegram_id']}")
        except Exception as e:
            logger.error(f"Failed to send reminder to user {booking_data['user_telegram_id']}: {e}")

    # Уведомление администратору
    try:
        admin_message = (
            f"⏰ Напоминание о завершении аренды\n\n"
            f"👤 Пользователь: {booking_data['user_name']}{username_str} (ID: {booking_data['user_id']})\n"
            f"📋 Тариф: {booking_data['tariff_name']}\n"
            f"📅 Дата окончания: {end_date.strftime('%d.%m.%Y')}\n"
            f"⏳ Осталось дней: {days_left}"
        )
        await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
        sent_count += 1
        logger.info(f"Напоминание отправлено администратору")
    except Exception as e:
        logger.error(f"Failed to send reminder to admin: {e}")

    return {'sent_count': sent_count}
