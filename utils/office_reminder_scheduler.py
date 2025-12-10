import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import DatabaseManager, Office, OfficeTenantReminder, User, Admin
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID, MOSCOW_TZ

logger = get_logger(__name__)

async def check_and_send_office_reminders():
    """
    Ежедневная проверка офисов и отправка напоминаний.
    Проверяет дату платежа и отправляет напоминания за N дней.
    """
    logger.info("Запуск проверки напоминаний по офисам...")

    def _get_offices_requiring_reminders(session):
        today = datetime.now(MOSCOW_TZ)
        current_day = today.day

        offices = session.query(Office).filter(
            Office.is_active == True,
            Office.payment_day.isnot(None)
        ).all()

        reminders_to_send = []

        for office in offices:
            days_until_payment = office.payment_day - current_day

            # Корректируем для случаев перехода через месяц
            if days_until_payment < 0:
                # Платеж в следующем месяце
                next_month = today.replace(day=1) + timedelta(days=32)
                next_month = next_month.replace(day=office.payment_day)
                days_until_payment = (next_month - today).days

            # Проверяем админ-напоминания
            if office.admin_reminder_enabled and days_until_payment == office.admin_reminder_days:
                reminders_to_send.append({
                    'type': 'admin',
                    'office': office,
                    'days_until': days_until_payment
                })

            # Проверяем напоминания постояльцам
            if office.tenant_reminder_enabled and days_until_payment == office.tenant_reminder_days:
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
                        'days_until': days_until_payment
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
                message = (
                    f"🔔 Напоминание о платеже за офис\n\n"
                    f"Офис: {office.office_number} (этаж {office.floor})\n"
                    f"Сумма: {office.price_per_month} ₽\n"
                    f"Дата платежа: {office.payment_day} число\n"
                    f"Осталось дней: {reminder['days_until']}\n\n"
                    f"Не забудьте выставить счет!"
                )
                await bot.send_message(ADMIN_TELEGRAM_ID, message)
                logger.info(f"Отправлено напоминание админу для офиса {office.office_number}")

            elif reminder['type'] == 'tenant':
                office = reminder['office']
                user = reminder['user']
                message = (
                    f"🔔 Напоминание об оплате офиса\n\n"
                    f"Офис: {office.office_number} (этаж {office.floor})\n"
                    f"Дата платежа: {office.payment_day} число\n"
                    f"Сумма: {office.price_per_month} ₽\n"
                    f"Осталось дней: {reminder['days_until']}\n\n"
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
