import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import DatabaseManager, UserOpenspaceRental, User, RentalType, MOSCOW_TZ
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID

logger = get_logger(__name__)


async def deactivate_expired_one_day_rentals():
    """
    Ежедневная деактивация истекших однодневных аренд опенспейса.
    Запускается в 00:05 каждый день.
    """
    logger.info("Запуск деактивации истекших однодневных аренд опенспейса...")

    def _deactivate_expired_rentals(session):
        now = datetime.now(MOSCOW_TZ)

        # Находим все активные однодневные аренды с истекшим end_date
        expired_rentals = session.query(UserOpenspaceRental).filter(
            UserOpenspaceRental.is_active == True,
            UserOpenspaceRental.rental_type == RentalType.ONE_DAY,
            UserOpenspaceRental.end_date < now
        ).all()

        deactivated_count = 0
        for rental in expired_rentals:
            rental.is_active = False
            rental.deactivated_at = now
            rental.updated_at = now
            deactivated_count += 1
            logger.debug(f"Деактивирована однодневная аренда rental_id={rental.id} для user_id={rental.user_id}")

        session.commit()
        return deactivated_count

    try:
        count = DatabaseManager.safe_execute(_deactivate_expired_rentals)

        if count > 0:
            logger.info(f"Деактивировано однодневных аренд: {count}")

            # Отправляем уведомление администратору
            try:
                bot = get_bot()
                if bot:
                    message = (
                        f"🔄 Автоматическая деактивация аренд опенспейса\n\n"
                        f"Деактивировано однодневных аренд: {count}\n"
                        f"Дата: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}"
                    )
                    await bot.send_message(ADMIN_TELEGRAM_ID, message)
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление администратору: {e}")
        else:
            logger.info("Нет истекших однодневных аренд для деактивации.")

    except Exception as e:
        logger.error(f"Ошибка при деактивации истекших аренд: {e}")


async def check_and_send_openspace_reminders():
    """
    Ежедневная проверка аренд опенспейса и отправка напоминаний о платежах.
    Запускается в 10:00 каждый день.
    """
    logger.info("Запуск проверки напоминаний по аренде опенспейса...")

    def _get_rentals_requiring_reminders(session):
        now = datetime.now(MOSCOW_TZ)

        # Находим все активные месячные аренды с датой следующего платежа
        rentals = session.query(UserOpenspaceRental).filter(
            UserOpenspaceRental.is_active == True,
            UserOpenspaceRental.rental_type.in_([RentalType.MONTHLY_FIXED, RentalType.MONTHLY_FLOATING]),
            UserOpenspaceRental.next_payment_date.isnot(None)
        ).all()

        reminders_to_send = []

        for rental in rentals:
            if not rental.next_payment_date:
                continue

            # Вычисляем количество дней до следующего платежа
            # SQLite не хранит timezone, поэтому добавляем его если отсутствует
            next_payment = rental.next_payment_date
            if next_payment.tzinfo is None:
                next_payment = next_payment.replace(tzinfo=MOSCOW_TZ)

            days_until_payment = (next_payment - now).days

            # Проверяем админ-напоминания
            if rental.admin_reminder_enabled and days_until_payment == rental.admin_reminder_days:
                reminders_to_send.append({
                    'type': 'admin',
                    'rental': rental,
                    'user': rental.user,
                    'days_until': days_until_payment
                })

            # Проверяем напоминания пользователю
            if rental.tenant_reminder_enabled and days_until_payment == rental.tenant_reminder_days:
                reminders_to_send.append({
                    'type': 'tenant',
                    'rental': rental,
                    'user': rental.user,
                    'days_until': days_until_payment
                })

        return reminders_to_send

    try:
        # Получаем список напоминаний для отправки
        reminders = DatabaseManager.safe_execute(_get_rentals_requiring_reminders)

        if not reminders:
            logger.info("Нет напоминаний по аренде опенспейса для отправки.")
            return

        logger.info(f"Найдено {len(reminders)} напоминаний по аренде опенспейса для отправки.")

        # Отправляем напоминания через Telegram бота
        bot = get_bot()

        for reminder in reminders:
            try:
                rental = reminder['rental']
                user = reminder['user']
                days_until = reminder['days_until']

                # Определяем название типа аренды
                rental_type_label = {
                    RentalType.MONTHLY_FIXED: "Фикс месяц",
                    RentalType.MONTHLY_FLOATING: "Нефикс месяц"
                }.get(rental.rental_type, rental.rental_type.value)

                if reminder['type'] == 'admin':
                    message = (
                        f"🔔 Напоминание о платеже за опенспейс\n\n"
                        f"👤 Пользователь: {user.full_name or 'Нет имени'} (ID: {user.id})\n"
                        f"📋 Тип: {rental_type_label}\n"
                        f"💰 Сумма: {rental.price} ₽\n"
                        f"📅 Дата платежа: {rental.next_payment_date.strftime('%d.%m.%Y')}\n"
                        f"⏰ Осталось дней: {days_until}\n"
                    )

                    if rental.workplace_number:
                        message += f"🪑 Место: {rental.workplace_number}\n"

                    message += "\n✅ Не забудьте записать платеж!"

                    await bot.send_message(ADMIN_TELEGRAM_ID, message)
                    logger.info(f"Отправлено напоминание админу для rental_id={rental.id}")

                elif reminder['type'] == 'tenant':
                    message = (
                        f"🔔 Напоминание об оплате опенспейса\n\n"
                        f"📋 Тип аренды: {rental_type_label}\n"
                        f"💰 Сумма: {rental.price} ₽\n"
                        f"📅 Дата платежа: {rental.next_payment_date.strftime('%d.%m.%Y')}\n"
                        f"⏰ Осталось дней: {days_until}\n"
                    )

                    if rental.workplace_number:
                        message += f"🪑 Ваше место: {rental.workplace_number}\n"

                    message += "\n💳 Пожалуйста, не забудьте внести оплату."

                    await bot.send_message(user.telegram_id, message)
                    logger.info(f"Отправлено напоминание пользователю {user.telegram_id} для rental_id={rental.id}")

                # Небольшая пауза между отправками
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Ошибка отправки напоминания для rental_id={rental.id}: {e}")

        logger.info(f"Отправка напоминаний по опенспейсу завершена. Всего отправлено: {len(reminders)}")

    except Exception as e:
        logger.error(f"Ошибка при проверке и отправке напоминаний по опенспейсу: {e}")


def start_openspace_scheduler():
    """Запускает планировщик для опенспейса."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Деактивация истекших однодневных аренд - каждый день в 00:05
    scheduler.add_job(
        deactivate_expired_one_day_rentals,
        'cron',
        hour=0,
        minute=5,
        id='deactivate_openspace_one_day',
        replace_existing=True
    )

    # Проверка и отправка напоминаний - каждый день в 10:00
    scheduler.add_job(
        check_and_send_openspace_reminders,
        'cron',
        hour=10,
        minute=0,
        id='openspace_reminders',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик опенспейса запущен:")
    logger.info("  - Деактивация однодневных аренд: ежедневно в 00:05")
    logger.info("  - Напоминания о платежах: ежедневно в 10:00")

    return scheduler
