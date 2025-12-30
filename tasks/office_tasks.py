"""Celery tasks for office reminder notifications."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from celery import Task
from celery_app import celery_app
from config import MOSCOW_TZ, ADMIN_TELEGRAM_ID
from models.models import (
    DatabaseManager,
    Office,
    OfficeTenantReminder,
    ReminderType,
)
from utils.logger import get_logger
from utils.bot_instance import get_bot

logger = get_logger(__name__)


class OfficeTask(Task):
    """Base task with callbacks."""

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"Office task {task_id} OK: {retval.get('message', 'N/A')}")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Office task {task_id} FAILED: {exc}")
        # Уведомление админу об ошибке
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _notify():
            try:
                bot = get_bot()
                await asyncio.wait_for(
                    bot.send_message(
                        ADMIN_TELEGRAM_ID,
                        f"🔴 Ошибка в напоминаниях офисов\n\nTask: {task_id}\n{str(exc)[:500]}"
                    ),
                    timeout=5.0
                )
            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")

        loop.run_until_complete(_notify())

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(f"Office task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=OfficeTask,
    name='tasks.office_tasks.send_office_reminders',
    max_retries=3,
    default_retry_delay=300
)
def send_office_reminders(self):
    """
    Periodic task: проверка офисов и отправка напоминаний.
    Запускается ежедневно в 10:00 МСК через Celery Beat.
    """
    try:
        logger.info("🏢 Проверка напоминаний офисов (Celery)")

        # Event loop setup
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_check_and_send_reminders_async())

        logger.info(
            f"✅ Отправлено: админу {result['admin_count']}, "
            f"постояльцам {result['tenant_count']}, "
            f"всего {result['reminders_sent']}"
        )

        return {
            'status': 'success',
            'reminders_sent': result['reminders_sent'],
            'admin_count': result['admin_count'],
            'tenant_count': result['tenant_count'],
            'message': f"Sent {result['reminders_sent']} reminders"
        }

    except Exception as e:
        logger.error(f"Error in office reminders: {e}", exc_info=True)
        raise self.retry(exc=e)


async def _check_and_send_reminders_async() -> Dict:
    """Логика из utils/office_reminder_scheduler.py"""

    def _get_offices_requiring_reminders(session):
        now = datetime.now(MOSCOW_TZ)
        today = now.date()

        offices = session.query(Office).filter(
            Office.is_active == True,
            Office.rental_end_date.isnot(None)
        ).all()

        reminders_to_send = []

        for office in offices:
            payment_date = office.next_payment_date or office.rental_end_date
            if not payment_date:
                continue

            if payment_date.tzinfo is None:
                payment_date = payment_date.replace(tzinfo=MOSCOW_TZ)

            days_until_payment = (payment_date.date() - today).days

            common_data = {
                "office_number": office.office_number,
                "floor": office.floor,
                "price": office.price_per_month,
                "days_until_payment": days_until_payment,
                "payment_date": payment_date,
                "is_monthly": office.payment_type == "monthly",
            }

            # Админ напоминания
            if office.admin_reminder_enabled:
                should_send = False

                if office.admin_reminder_type == ReminderType.days_before:
                    should_send = days_until_payment == office.admin_reminder_days
                elif office.admin_reminder_type == ReminderType.specific_datetime:
                    if office.admin_reminder_datetime:
                        dt = office.admin_reminder_datetime
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=MOSCOW_TZ)
                        should_send = dt.date() == today

                if should_send:
                    reminders_to_send.append({"type": "admin", **common_data})

            # Постояльцы напоминания
            if office.tenant_reminder_enabled:
                should_send = False

                if office.tenant_reminder_type == ReminderType.days_before:
                    should_send = days_until_payment == office.tenant_reminder_days
                elif office.tenant_reminder_type == ReminderType.specific_datetime:
                    if office.tenant_reminder_datetime:
                        dt = office.tenant_reminder_datetime
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=MOSCOW_TZ)
                        should_send = dt.date() == today

                if should_send:
                    tenant_reminders = session.query(OfficeTenantReminder).filter(
                        OfficeTenantReminder.office_id == office.id,
                        OfficeTenantReminder.is_enabled == True
                    ).all()

                    for tr in tenant_reminders:
                        if tr.user:
                            reminders_to_send.append({
                                "type": "tenant",
                                "telegram_id": tr.user.telegram_id,
                                **common_data,
                            })

        return reminders_to_send

    reminders = DatabaseManager.safe_execute(_get_offices_requiring_reminders)

    if not reminders:
        logger.info("Нет напоминаний")
        return {'reminders_sent': 0, 'admin_count': 0, 'tenant_count': 0}

    logger.info(f"Найдено {len(reminders)} напоминаний")

    # Отправка
    bot = get_bot()
    admin_count = 0
    tenant_count = 0
    sent_count = 0

    for reminder in reminders:
        try:
            payment_date = reminder["payment_date"]
            is_monthly = reminder.get("is_monthly", False)
            payment_type_str = "Очередной платеж" if is_monthly else "Окончание аренды"

            message = (
                f"🔔 Напоминание - {payment_type_str}\n\n"
                f"Офис: {reminder['office_number']} (этаж {reminder['floor']})\n"
                f"Дата: {payment_date.strftime('%d.%m.%Y')}\n"
                f"Сумма: {reminder['price']} ₽\n"
                f"Осталось дней: {reminder['days_until_payment']}\n\n"
            )

            if reminder["type"] == "admin":
                message += "Не забудьте выставить счет!"
                await asyncio.wait_for(
                    bot.send_message(ADMIN_TELEGRAM_ID, message),
                    timeout=5.0
                )
                admin_count += 1
                sent_count += 1
                logger.info(f"→ АДМИН: офис {reminder['office_number']}")

            elif reminder["type"] == "tenant":
                message += "Пожалуйста, не забудьте внести оплату."
                await asyncio.wait_for(
                    bot.send_message(reminder["telegram_id"], message),
                    timeout=5.0
                )
                tenant_count += 1
                sent_count += 1
                logger.info(f"→ ПОЛЬЗОВАТЕЛЬ: офис {reminder['office_number']}")

            await asyncio.sleep(0.5)

        except asyncio.TimeoutError:
            logger.error(f"Timeout: офис {reminder.get('office_number')}")
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

    return {
        'reminders_sent': sent_count,
        'admin_count': admin_count,
        'tenant_count': tenant_count
    }


@celery_app.task(
    bind=True,
    base=OfficeTask,
    name='tasks.office_tasks.send_office_reminder',
    max_retries=3,
    default_retry_delay=300
)
def send_office_reminder(self, office_id: int, reminder_type: str):
    """
    Индивидуальная задача для отправки напоминания по конкретному офису.

    Args:
        office_id: ID офиса
        reminder_type: Тип напоминания - 'admin' или 'tenant'

    Returns:
        Dict с результатом выполнения
    """
    from models.models import ScheduledTask, TaskStatus

    # Обновляем статус задачи в БД на "running"
    def _update_task_status_running(session):
        task = session.query(ScheduledTask).filter(
            ScheduledTask.celery_task_id == self.request.id
        ).first()
        if task:
            task.status = TaskStatus.RUNNING
            session.commit()
            logger.info(f"Task #{task.id} status updated to RUNNING")
        return task

    try:
        logger.info(f"🏢 Отправка {reminder_type} напоминания для офиса #{office_id}")

        # Обновляем статус на running
        DatabaseManager.safe_execute(_update_task_status_running)

        # Event loop setup
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_send_single_office_reminder_async(office_id, reminder_type))

        # Обновляем статус на completed
        def _update_task_status_completed(session):
            task = session.query(ScheduledTask).filter(
                ScheduledTask.celery_task_id == self.request.id
            ).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.executed_at = datetime.now(MOSCOW_TZ)
                task.result = result
                session.commit()
                logger.info(f"Task #{task.id} status updated to COMPLETED")

        DatabaseManager.safe_execute(_update_task_status_completed)

        return result

    except Exception as e:
        logger.error(f"Error sending {reminder_type} reminder for office #{office_id}: {e}", exc_info=True)

        # Обновляем статус на failed
        def _update_task_status_failed(session):
            task = session.query(ScheduledTask).filter(
                ScheduledTask.celery_task_id == self.request.id
            ).first()
            if task:
                task.status = TaskStatus.FAILED
                task.executed_at = datetime.now(MOSCOW_TZ)
                task.error_message = str(e)
                task.retry_count += 1
                session.commit()
                logger.info(f"Task #{task.id} status updated to FAILED")

        DatabaseManager.safe_execute(_update_task_status_failed)

        raise self.retry(exc=e)


async def _send_single_office_reminder_async(office_id: int, reminder_type: str) -> Dict:
    """Отправка напоминания по конкретному офису."""

    def _get_office_data(session):
        office = session.query(Office).filter(Office.id == office_id).first()
        if not office:
            logger.warning(f"Office #{office_id} not found")
            return None

        if not office.is_active:
            logger.info(f"Office #{office_id} is not active, skipping")
            return None

        payment_date = office.next_payment_date or office.rental_end_date
        if not payment_date:
            logger.warning(f"Office #{office_id} has no payment date")
            return None

        if payment_date.tzinfo is None:
            payment_date = payment_date.replace(tzinfo=MOSCOW_TZ)

        now = datetime.now(MOSCOW_TZ)
        days_until_payment = (payment_date.date() - now.date()).days

        office_data = {
            'office_number': office.office_number,
            'floor': office.floor,
            'price': office.price_per_month,
            'days_until_payment': days_until_payment,
            'payment_date': payment_date,
            'is_monthly': office.payment_type == "monthly",
        }

        # Получаем постояльцев для tenant напоминаний
        if reminder_type == 'tenant':
            tenant_reminders = session.query(OfficeTenantReminder).filter(
                OfficeTenantReminder.office_id == office.id,
                OfficeTenantReminder.is_enabled == True
            ).all()
            office_data['tenant_ids'] = [tr.user.telegram_id for tr in tenant_reminders if tr.user]

        return office_data

    office_data = DatabaseManager.safe_execute(_get_office_data)

    if not office_data:
        return {
            'status': 'skipped',
            'office_id': office_id,
            'reminder_type': reminder_type,
            'notifications_sent': 0,
            'message': 'Office not found or inactive'
        }

    bot = get_bot()
    sent_count = 0

    payment_date = office_data["payment_date"]
    is_monthly = office_data.get("is_monthly", False)
    payment_type_str = "очередного платежа" if is_monthly else "окончания аренды"

    message = (
        f"🔔 Напоминание - {payment_type_str}\n\n"
        f"Офис: {office_data['office_number']} (этаж {office_data['floor']})\n"
        f"Дата: {payment_date.strftime('%d.%m.%Y')}\n"
        f"Сумма: {office_data['price']} ₽\n"
        f"Осталось дней: {office_data['days_until_payment']}\n\n"
    )

    try:
        if reminder_type == 'admin':
            message += "Не забудьте выставить счет!"
            await asyncio.wait_for(
                bot.send_message(ADMIN_TELEGRAM_ID, message),
                timeout=5.0
            )
            sent_count += 1
            logger.info(f"→ АДМИН: офис {office_data['office_number']} (ID: {office_id})")

        elif reminder_type == 'tenant':
            tenant_ids = office_data.get('tenant_ids', [])
            message += "Пожалуйста, не забудьте внести оплату."

            for telegram_id in tenant_ids:
                try:
                    await asyncio.wait_for(
                        bot.send_message(telegram_id, message),
                        timeout=5.0
                    )
                    sent_count += 1
                    logger.info(f"→ ПОСТОЯЛЕЦ {telegram_id}: офис {office_data['office_number']}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending to tenant {telegram_id}: {e}")

    except asyncio.TimeoutError:
        logger.error(f"Timeout sending {reminder_type} reminder for office #{office_id}")
        return {
            'status': 'failed',
            'office_id': office_id,
            'reminder_type': reminder_type,
            'notifications_sent': sent_count,
            'message': 'Timeout error'
        }
    except Exception as e:
        logger.error(f"Error sending {reminder_type} reminder: {e}")
        return {
            'status': 'failed',
            'office_id': office_id,
            'reminder_type': reminder_type,
            'notifications_sent': sent_count,
            'message': str(e)
        }

    return {
        'status': 'success',
        'office_id': office_id,
        'reminder_type': reminder_type,
        'notifications_sent': sent_count,
        'message': f"Sent {sent_count} {reminder_type} reminders for office #{office_id}"
    }
