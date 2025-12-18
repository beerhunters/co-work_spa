import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import DatabaseManager, Office, OfficeTenantReminder, User, Admin, ReminderType
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID, MOSCOW_TZ

logger = get_logger(__name__)

async def check_and_send_office_reminders():
    """
    Ежедневная проверка офисов и отправка напоминаний.
    Проверяет дату окончания аренды и отправляет напоминания за N дней.
    """
    logger.info("Запуск проверки напоминаний по офисам...")

    def _get_offices_requiring_reminders(session):
        now = datetime.now(MOSCOW_TZ)

        # Получаем активные офисы с датой окончания аренды
        offices = session.query(Office).filter(
            Office.is_active == True,
            Office.rental_end_date.isnot(None)
        ).all()

        reminders_to_send = []

        for office in offices:
            # Используем next_payment_date с fallback на rental_end_date
            payment_date = office.next_payment_date or office.rental_end_date
            if not payment_date:
                logger.warning(
                    f"Office {office.id} ({office.office_number}) has neither "
                    f"next_payment_date nor rental_end_date"
                )
                continue

            # Добавляем timezone если отсутствует (SQLite не хранит timezone)
            if payment_date.tzinfo is None:
                payment_date = payment_date.replace(tzinfo=MOSCOW_TZ)

            # Логировать если используется fallback
            if office.next_payment_date is None:
                logger.warning(
                    f"Office {office.id} ({office.office_number}) missing "
                    f"next_payment_date, using rental_end_date as fallback"
                )

            # Вычисляем количество дней до следующего платежа
            days_until_payment = (payment_date - now).days

            # Проверяем админ-напоминания
            if office.admin_reminder_enabled:
                should_send = False

                if office.admin_reminder_type == ReminderType.days_before:
                    # Напоминание за N дней до следующего платежа
                    should_send = days_until_payment == office.admin_reminder_days
                elif office.admin_reminder_type == ReminderType.specific_datetime:
                    # Напоминание в конкретную дату/время (проверяем с точностью до дня)
                    if office.admin_reminder_datetime:
                        reminder_datetime = office.admin_reminder_datetime
                        if reminder_datetime.tzinfo is None:
                            reminder_datetime = reminder_datetime.replace(tzinfo=MOSCOW_TZ)
                        should_send = reminder_datetime.date() == now.date()

                if should_send:
                    reminders_to_send.append({
                        'type': 'admin',
                        'office': office,
                        'days_until_payment': days_until_payment,
                        'payment_date': payment_date,
                        'is_monthly': office.payment_type == 'monthly'
                    })

            # Проверяем напоминания постояльцам
            if office.tenant_reminder_enabled:
                should_send = False

                if office.tenant_reminder_type == ReminderType.days_before:
                    # Напоминание за N дней до следующего платежа
                    should_send = days_until_payment == office.tenant_reminder_days
                elif office.tenant_reminder_type == ReminderType.specific_datetime:
                    # Напоминание в конкретную дату/время (проверяем с точностью до дня)
                    if office.tenant_reminder_datetime:
                        reminder_datetime = office.tenant_reminder_datetime
                        if reminder_datetime.tzinfo is None:
                            reminder_datetime = reminder_datetime.replace(tzinfo=MOSCOW_TZ)
                        should_send = reminder_datetime.date() == now.date()

                if should_send:
                    # Получаем постояльцев с включенными напоминаниями
                    tenant_reminders = session.query(OfficeTenantReminder).filter(
                        OfficeTenantReminder.office_id == office.id,
                        OfficeTenantReminder.is_enabled == True
                    ).all()

                    for tr in tenant_reminders:
                        reminders_to_send.append({
                            'type': 'tenant',
                            'office': office,
                            'user': tr.user,
                            'days_until_payment': days_until_payment,
                            'payment_date': payment_date,
                            'is_monthly': office.payment_type == 'monthly'
                        })

        return reminders_to_send

    # Получаем список напоминаний для отправки
    reminders = DatabaseManager.safe_execute(_get_offices_requiring_reminders)

    if not reminders:
        logger.info("Нет напоминаний для отправки.")
        return

    logger.info(f"Найдено {len(reminders)} напоминаний для отправки.")

    # Отправляем напоминания через Telegram бота
    bot = get_bot()

    for reminder in reminders:
        try:
            if reminder['type'] == 'admin':
                office = reminder['office']
                payment_date = reminder['payment_date']
                is_monthly = reminder.get('is_monthly', False)
                payment_type_str = "очередного платежа" if is_monthly else "окончания аренды"

                message = (
                    f"🔔 Напоминание о {payment_type_str}\n\n"
                    f"Офис: {office.office_number} (этаж {office.floor})\n"
                    f"Сумма: {office.price_per_month} ₽\n"
                    f"Дата платежа: {payment_date.strftime('%d.%m.%Y')}\n"
                    f"Осталось дней: {reminder['days_until_payment']}\n\n"
                    f"Не забудьте выставить счет!"
                )
                await bot.send_message(ADMIN_TELEGRAM_ID, message)
                logger.info(f"Отправлено напоминание админу для офиса {office.office_number}")

            elif reminder['type'] == 'tenant':
                office = reminder['office']
                user = reminder['user']
                payment_date = reminder['payment_date']
                is_monthly = reminder.get('is_monthly', False)
                payment_type_str = "очередного платежа" if is_monthly else "окончания аренды"

                message = (
                    f"🔔 Напоминание о {payment_type_str}\n\n"
                    f"Офис: {office.office_number} (этаж {office.floor})\n"
                    f"Дата платежа: {payment_date.strftime('%d.%m.%Y')}\n"
                    f"Сумма: {office.price_per_month} ₽\n"
                    f"Осталось дней: {reminder['days_until_payment']}\n\n"
                    f"Пожалуйста, не забудьте внести оплату."
                )
                await bot.send_message(user.telegram_id, message)
                logger.info(f"Отправлено напоминание пользователю {user.telegram_id} для офиса {office.office_number}")

            # Небольшая пауза между отправками
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")

    logger.info(f"Отправка напоминаний завершена. Всего отправлено: {len(reminders)}")


def start_office_reminder_scheduler():
    """Запускает планировщик напоминаний по офисам."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Запускать каждый день в 10:00
    scheduler.add_job(
        check_and_send_office_reminders,
        'cron',
        hour=10,
        minute=0,
        id='office_reminders',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик напоминаний по офисам запущен (ежедневно в 10:00)")

    return scheduler
