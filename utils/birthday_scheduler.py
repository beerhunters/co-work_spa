import asyncio
from datetime import datetime, date, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from models.models import DatabaseManager, User, MOSCOW_TZ
from utils.logger import get_logger
from utils.bot_instance import get_bot
from config import ADMIN_TELEGRAM_ID

logger = get_logger(__name__)


async def check_and_send_birthday_reminders():
    """
    Ежедневная проверка дней рождения и отправка напоминаний.
    Запускается в 10:00 каждый день.

    Логика:
    1. Находим пользователей с ДР через 2 дня -> напоминание админу
    2. Находим пользователей с ДР сегодня -> поздравление пользователю
    """
    logger.info("Запуск проверки дней рождения...")

    def _get_birthday_users(session):
        now = datetime.now(MOSCOW_TZ)
        today = now.date()
        in_two_days = today + timedelta(days=2)

        users_with_birthdays = (
            session.query(User)
            .filter(User.birth_date.isnot(None))
            .all()
        )

        admin_reminders = []
        user_congratulations = []

        for user in users_with_birthdays:
            if not user.birth_date:
                continue

            # Парсим формат DD.MM или DD.MM.YYYY
            try:
                parts = str(user.birth_date).split('.')
                if len(parts) == 2:
                    day, month = int(parts[0]), int(parts[1])
                    birth_year = None
                elif len(parts) == 3:
                    day, month, birth_year = int(parts[0]), int(parts[1]), int(parts[2])
                else:
                    raise ValueError("Invalid format")
            except (ValueError, AttributeError):
                logger.warning(f"Неверный формат birth_date для user_id={user.id}: {user.birth_date}")
                continue

            # Создаем дату ДР в текущем году
            try:
                birthday_this_year = date(today.year, month, day)
            except ValueError:
                # Обработка 29 февраля в невисокосные годы
                if month == 2 and day == 29:
                    birthday_this_year = date(today.year, 2, 28)
                else:
                    logger.warning(f"Неверная дата для user_id={user.id}: {day}.{month}")
                    continue

            # Вычисляем возраст если год указан
            age = None
            if birth_year:
                age = today.year - birth_year
                # Корректируем возраст если ДР еще не наступил в этом году
                if birthday_this_year > today:
                    age -= 1

            # ДР сегодня
            if birthday_this_year == today:
                user_congratulations.append({
                    'user_id': user.id,
                    'telegram_id': user.telegram_id,
                    'full_name': user.full_name or "Пользователь",
                    'username': user.username,
                    'birth_date_str': user.birth_date,
                    'age': age,
                })

            # ДР через 2 дня
            elif birthday_this_year == in_two_days:
                age_in_2_days = age
                if birth_year and age is not None:
                    # Возраст через 2 дня - это age + 1 (так как ДР наступит)
                    age_in_2_days = today.year - birth_year
                    if birthday_this_year >= today:
                        age_in_2_days = today.year - birth_year

                admin_reminders.append({
                    'user_id': user.id,
                    'telegram_id': user.telegram_id,
                    'full_name': user.full_name or "Пользователь",
                    'username': user.username,
                    'birth_date_str': user.birth_date,
                    'birthday_date': birthday_this_year,
                    'age': age_in_2_days,
                })

        return {
            'admin_reminders': admin_reminders,
            'user_congratulations': user_congratulations,
        }

    try:
        result = DatabaseManager.safe_execute(_get_birthday_users)
        admin_reminders = result['admin_reminders']
        user_congratulations = result['user_congratulations']

        if not admin_reminders and not user_congratulations:
            logger.info("Нет дней рождения для обработки сегодня.")
            return

        logger.info(
            f"Найдено: {len(admin_reminders)} напоминаний админу, "
            f"{len(user_congratulations)} поздравлений пользователям."
        )

        bot = get_bot()

        # 1. Напоминания администратору за 2 дня
        for reminder in admin_reminders:
            try:
                message = (
                    f"🎂 Напоминание о дне рождения\n\n"
                    f"👤 Пользователь: {reminder['full_name']} (ID: {reminder['user_id']})\n"
                )

                if reminder['username']:
                    message += f"📱 TG: @{reminder['username']}\n"

                message += f"📅 День рождения: {reminder['birth_date_str']}\n"

                if reminder.get('age'):
                    message += f"🎉 Исполнится: {reminder['age']} лет\n"

                message += (
                    f"⏰ Через 2 дня\n\n"
                    f"💡 Не забудьте подготовить поздравление!"
                )

                await bot.send_message(ADMIN_TELEGRAM_ID, message)
                logger.info(f"Отправлено напоминание админу о ДР user_id={reminder['user_id']}")
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Ошибка отправки напоминания админу о user_id={reminder['user_id']}: {e}")

        # 2. Поздравления пользователям
        for congrats in user_congratulations:
            try:
                message = (
                    f"🎉🎂 С Днем Рождения!\n\n"
                    f"Уважаемый(ая) {congrats['full_name']}!\n\n"
                    f"Поздравляем Вас с Днем Рождения!\n\n"
                    f"Желаем крепкого здоровья, счастья, успехов и благополучия!\n"
                    f"Пусть все Ваши мечты сбываются!\n\n"
                    f"С наилучшими пожеланиями,\n"
                    f"Команда коворкинга 🏢"
                )

                await bot.send_message(congrats['telegram_id'], message)
                logger.info(f"Отправлено поздравление пользователю {congrats['telegram_id']}")
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Ошибка отправки поздравления {congrats['telegram_id']}: {e}")

        logger.info(f"Рассылка завершена. Админ: {len(admin_reminders)}, Пользователи: {len(user_congratulations)}")

    except Exception as e:
        logger.error(f"Ошибка при проверке и отправке поздравлений с ДР: {e}")


def start_birthday_scheduler():
    """Запускает планировщик для дней рождения."""
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)

    scheduler.add_job(
        check_and_send_birthday_reminders,
        "cron",
        hour=10,
        minute=0,
        id="birthday_reminders",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Планировщик дней рождения запущен: проверка в 10:00 ежедневно")

    return scheduler
