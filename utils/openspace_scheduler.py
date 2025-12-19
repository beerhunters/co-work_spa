import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import (
    DatabaseManager,
    UserOpenspaceRental,
    User,
    RentalType,
    MOSCOW_TZ,
)
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
        expired_rentals = (
            session.query(UserOpenspaceRental)
            .filter(
                UserOpenspaceRental.is_active == True,
                UserOpenspaceRental.rental_type == RentalType.ONE_DAY,
                UserOpenspaceRental.end_date < now,
            )
            .all()
        )

        deactivated_list = []
        for rental in expired_rentals:
            rental.is_active = False
            rental.deactivated_at = now
            rental.updated_at = now

            # Собираем информацию о пользователе
            user_info = {
                "rental_id": rental.id,
                "user_id": rental.user_id,
                "user_name": rental.user.full_name if rental.user else "Неизвестно",
                "user_username": rental.user.username if rental.user else None,
                "price": rental.price,
                "start_date": rental.start_date,
            }
            deactivated_list.append(user_info)
            logger.debug(
                f"Деактивирована однодневная аренда rental_id={rental.id} для user_id={rental.user_id}"
            )

        session.commit()
        return deactivated_list

    try:
        deactivated_rentals = DatabaseManager.safe_execute(_deactivate_expired_rentals)

        if deactivated_rentals:
            logger.info(f"Деактивировано однодневных аренд: {len(deactivated_rentals)}")

            # Отправляем уведомление администратору
            try:
                bot = get_bot()
                if bot:
                    message = f"🔄 Автоматическая деактивация аренд опенспейса\n\n"
                    message += f"Завершено однодневных посещений: {len(deactivated_rentals)}\n\n"

                    # Добавляем информацию о каждом пользователе
                    for info in deactivated_rentals:
                        message += f"👤 {info['user_name']} (ID: {info['user_id']})\n"
                        if info["user_username"]:
                            message += f"   📱 TG: @{info['user_username']}\n"
                        message += f"   Цена: {info['price']} ₽\n"
                        message += (
                            f"   Дата: {info['start_date'].strftime('%d.%m.%Y')}\n\n"
                        )

                    message += f"Дата завершения: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}"

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
        today = now.date()  # ИСПОЛЬЗУЕМ ТОЛЬКО ДАТУ

        # Находим все активные месячные аренды с датой следующего платежа
        rentals = (
            session.query(UserOpenspaceRental)
            .filter(
                UserOpenspaceRental.is_active == True,
                UserOpenspaceRental.rental_type.in_(
                    [RentalType.MONTHLY_FIXED, RentalType.MONTHLY_FLOATING]
                ),
                UserOpenspaceRental.next_payment_date.isnot(None),
            )
            .all()
        )

        reminders_to_send = []

        for rental in rentals:
            if not rental.next_payment_date:
                continue

            # Вычисляем количество дней до следующего платежа
            # SQLite не хранит timezone, поэтому добавляем его если отсутствует
            next_payment = rental.next_payment_date
            if next_payment.tzinfo is None:
                next_payment = next_payment.replace(tzinfo=MOSCOW_TZ)

            # !!! ИСПРАВЛЕНИЕ ДАТ: Считаем разницу строго по календарным дням
            days_until_payment = (next_payment.date() - today).days

            # !!! ИСПРАВЛЕНИЕ ДАННЫХ: Сохраняем значения в словарь, чтобы не зависеть от сессии
            rental_type_label = {
                RentalType.MONTHLY_FIXED: "Фикс месяц",
                RentalType.MONTHLY_FLOATING: "Нефикс месяц",
            }.get(rental.rental_type, str(rental.rental_type))

            # Безопасно получаем данные пользователя
            u_full_name = rental.user.full_name if rental.user else "Неизвестно"
            u_username = rental.user.username if rental.user else None
            u_telegram_id = rental.user.telegram_id if rental.user else None
            u_id = rental.user.id if rental.user else None

            # Общие данные
            common_data = {
                "rental_id": rental.id,
                "price": rental.price,
                "next_payment_date": next_payment,
                "days_until": days_until_payment,
                "rental_type_label": rental_type_label,
                "workplace_number": rental.workplace_number,
                "user_full_name": u_full_name,
                "user_username": u_username,
                "user_id": u_id,
                "telegram_id": u_telegram_id,
            }

            # Проверяем админ-напоминания
            if (
                rental.admin_reminder_enabled
                and days_until_payment == rental.admin_reminder_days
            ):
                reminders_to_send.append({"type": "admin", **common_data})

            # Проверяем напоминания пользователю
            if (
                rental.tenant_reminder_enabled
                and days_until_payment == rental.tenant_reminder_days
            ):
                if u_telegram_id:  # Проверяем, есть ли кому слать
                    reminders_to_send.append({"type": "tenant", **common_data})

        return reminders_to_send

    try:
        # Получаем список напоминаний для отправки
        reminders = DatabaseManager.safe_execute(_get_rentals_requiring_reminders)

        if not reminders:
            logger.info("Нет напоминаний по аренде опенспейса для отправки.")
            return

        logger.info(
            f"Найдено {len(reminders)} напоминаний по аренде опенспейса для отправки."
        )

        # Отправляем напоминания через Telegram бота
        bot = get_bot()

        for reminder in reminders:
            try:
                days_until = reminder["days_until"]
                payment_date_str = reminder["next_payment_date"].strftime("%d.%m.%Y")

                # Текст сообщения
                message_text = ""

                if reminder["type"] == "admin":
                    message_text = (
                        f"🔔 Напоминание о платеже за опенспейс\n\n"
                        f"👤 Пользователь: {reminder['user_full_name']} (ID: {reminder['user_id']})\n"
                    )
                    if reminder["user_username"]:
                        message_text += f"📱 TG: @{reminder['user_username']}\n"

                    message_text += (
                        f"📋 Тип: {reminder['rental_type_label']}\n"
                        f"💰 Сумма: {reminder['price']} ₽\n"
                        f"📅 Дата платежа: {payment_date_str}\n"
                        f"⏰ Осталось дней: {days_until}\n"
                    )
                    if reminder["workplace_number"]:
                        message_text += f"🪑 Место: {reminder['workplace_number']}\n"

                    message_text += "\n✅ Не забудьте записать платеж!"

                    await bot.send_message(ADMIN_TELEGRAM_ID, message_text)
                    logger.info(
                        f"Отправлено АДМИНУ (rental_id={reminder['rental_id']})"
                    )

                elif reminder["type"] == "tenant":
                    message_text = (
                        f"🔔 Напоминание об оплате опенспейса\n\n"
                        f"📋 Тип аренды: {reminder['rental_type_label']}\n"
                        f"💰 Сумма: {reminder['price']} ₽\n"
                        f"📅 Дата платежа: {payment_date_str}\n"
                        f"⏰ Осталось дней: {days_until}\n"
                    )
                    if reminder["workplace_number"]:
                        message_text += (
                            f"🪑 Ваше место: {reminder['workplace_number']}\n"
                        )

                    message_text += "\n💳 Пожалуйста, не забудьте внести оплату."

                    target_id = reminder["telegram_id"]
                    await bot.send_message(target_id, message_text)
                    logger.info(
                        f"Отправлено ПОЛЬЗОВАТЕЛЮ {target_id} (rental_id={reminder['rental_id']})"
                    )

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(
                    f"Ошибка отправки напоминания rental_id={reminder.get('rental_id')}: {e}"
                )

        logger.info(f"Рассылка завершена. Всего: {len(reminders)}")

    except Exception as e:
        logger.error(f"Ошибка при проверке и отправке напоминаний: {e}")


async def reset_payment_status_before_next_payment():
    """
    Ежедневная проверка аренд опенспейса и изменение статуса оплаты.
    За N дней до next_payment_date меняет payment_status с 'paid' на 'pending'.
    Запускается в 00:10 каждый день.
    """
    logger.info("Запуск проверки статусов оплаты для опенспейса...")

    def _reset_payment_statuses(session):
        now = datetime.now(MOSCOW_TZ)
        today = now.date()  # Исправление

        # Находим все активные месячные аренды со статусом 'paid'
        rentals = (
            session.query(UserOpenspaceRental)
            .filter(
                UserOpenspaceRental.is_active == True,
                UserOpenspaceRental.rental_type.in_(
                    [RentalType.MONTHLY_FIXED, RentalType.MONTHLY_FLOATING]
                ),
                UserOpenspaceRental.payment_status == "paid",
                UserOpenspaceRental.next_payment_date.isnot(None),
            )
            .all()
        )

        reset_list = []

        for rental in rentals:
            if not rental.next_payment_date:
                continue

            # Добавляем timezone если отсутствует
            next_payment = rental.next_payment_date
            if next_payment.tzinfo is None:
                next_payment = next_payment.replace(tzinfo=MOSCOW_TZ)

            # Исправленное вычисление дней (строго по датам)
            days_until_payment = (next_payment.date() - today).days

            # Используем admin_reminder_days или tenant_reminder_days как порог
            # Берем максимальное значение между ними
            threshold_days = max(
                rental.admin_reminder_days if rental.admin_reminder_enabled else 0,
                rental.tenant_reminder_days if rental.tenant_reminder_enabled else 0,
            )

            # Если threshold = 0, используем 5 дней по умолчанию
            if threshold_days == 0:
                threshold_days = 5

            # Если до платежа осталось threshold_days или меньше, меняем статус
            if days_until_payment <= threshold_days:
                logger.info(
                    f"Изменение статуса оплаты для rental_id={rental.id}: "
                    f"осталось {days_until_payment} дней до платежа (порог: {threshold_days})"
                )
                rental.payment_status = "pending"
                rental.updated_at = now

                # Определяем название типа аренды
                rental_type_label = {
                    RentalType.MONTHLY_FIXED: "Опенспейс на месяц(фикс)",
                    RentalType.MONTHLY_FLOATING: "Опенспейс на месяц",
                }.get(rental.rental_type, rental.rental_type.value)

                # Собираем информацию о пользователе
                user_info = {
                    "rental_id": rental.id,
                    "user_id": rental.user_id,
                    "user_name": rental.user.full_name if rental.user else "Неизвестно",
                    "user_username": rental.user.username if rental.user else None,
                    "rental_type": rental_type_label,
                    "price": rental.price,
                    "next_payment_date": next_payment,
                    "days_until_payment": days_until_payment,
                    "workplace_number": rental.workplace_number,
                }
                reset_list.append(user_info)

        session.commit()
        return reset_list

    try:
        reset_rentals = DatabaseManager.safe_execute(_reset_payment_statuses)

        if reset_rentals:
            logger.info(
                f"Изменен статус оплаты для {len(reset_rentals)} аренд опенспейса"
            )

            # Отправляем уведомление администратору
            try:
                bot = get_bot()
                if bot:
                    message = f"💳 Приближается срок оплаты опенспейса\n\n"
                    message += f"Статус изменен на 'Требуется оплата': {len(reset_rentals)}\n\n"

                    # Добавляем информацию о каждом пользователе
                    for info in reset_rentals:
                        message += f"👤 {info['user_name']} (ID: {info['user_id']})\n"
                        if info["user_username"]:
                            message += f"   📱 TG: @{info['user_username']}\n"
                        message += f"   Тип: {info['rental_type']}\n"
                        message += f"   Цена: {info['price']} ₽\n"
                        if info["workplace_number"]:
                            message += f"   Место: {info['workplace_number']}\n"
                        message += f"   Дата платежа: {info['next_payment_date'].strftime('%d.%m.%Y')}\n"
                        message += f"   Осталось дней: {info['days_until_payment']}\n\n"

                    message += f"Дата проверки: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')}"

                    await bot.send_message(ADMIN_TELEGRAM_ID, message)
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление администратору: {e}")
        else:
            logger.info("Нет аренд опенспейса, требующих изменения статуса оплаты.")

    except Exception as e:
        logger.error(f"Ошибка при изменении статусов оплаты: {e}")


def start_openspace_scheduler():
    """Запускает планировщик для опенспейса."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    # Деактивация истекших однодневных аренд - каждый день в 00:05
    scheduler.add_job(
        deactivate_expired_one_day_rentals,
        "cron",
        hour=0,
        minute=5,
        id="deactivate_openspace_one_day",
        replace_existing=True,
    )

    # Изменение статуса оплаты - каждый день в 00:10
    scheduler.add_job(
        reset_payment_status_before_next_payment,
        "cron",
        hour=0,
        minute=10,
        id="reset_openspace_payment_status",
        replace_existing=True,
    )

    # Проверка и отправка напоминаний - каждый день в 10:00
    scheduler.add_job(
        check_and_send_openspace_reminders,
        "cron",
        hour=10,
        minute=0,
        id="openspace_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Планировщик опенспейса запущен:")
    logger.info("  - Деактивация однодневных аренд: ежедневно в 00:05")
    logger.info("  - Изменение статуса оплаты: ежедневно в 00:10")
    logger.info("  - Напоминания о платежах: ежедневно в 10:00")

    return scheduler
