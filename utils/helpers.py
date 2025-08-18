import re
from datetime import datetime
from typing import Optional

from config import MOSCOW_TZ
from utils.logger import get_logger

logger = get_logger(__name__)


def format_phone_for_rubitime(phone: str) -> str:
    """
    Форматирует номер телефона для Rubitime API
    Возвращает номер в формате +7XXXXXXXXXX или пустую строку если номер некорректный
    """
    if not phone:
        return ""

    # Убираем все символы кроме цифр
    digits = re.sub(r"[^0-9]", "", phone)

    if not digits:
        return ""

    # Обрабатываем различные форматы
    if digits.startswith("8") and len(digits) == 11:
        # 8XXXXXXXXXX -> +7XXXXXXXXXX
        digits = "7" + digits[1:]
    elif digits.startswith("7") and len(digits) == 11:
        # 7XXXXXXXXXX -> +7XXXXXXXXXX
        pass
    elif len(digits) == 10:
        # XXXXXXXXXX -> +7XXXXXXXXXX
        digits = "7" + digits
    else:
        # Неподдерживаемый формат
        logger.warning(f"Неподдерживаемый формат телефона: {phone}")
        return ""

    # Проверяем финальную длину
    if len(digits) != 11 or not digits.startswith("7"):
        logger.warning(f"Некорректный телефон после обработки: {digits}")
        return ""

    return "+" + digits


def format_booking_notification(user, tariff, booking_data) -> str:
    """
    Форматирует уведомление о новом бронировании для админа

    Args:
        user: объект User или словарь с данными пользователя
        tariff: объект Tariff или словарь с данными тарифа
        booking_data: словарь с данными бронирования
    """
    tariff_emojis = {
        "coworking": "🏢",
        "meeting": "🤝",
        "переговорная": "🤝",
        "коворкинг": "🏢",
    }

    # Безопасное получение данных пользователя
    if hasattr(user, "full_name"):
        user_name = user.full_name or "Не указано"
        user_phone = user.phone or "Не указано"
        user_username = f"@{user.username}" if user.username else "Не указано"
        telegram_id = user.telegram_id
    else:
        # Если user - это словарь
        user_name = user.get("full_name") or "Не указано"
        user_phone = user.get("phone") or "Не указано"
        user_username = (
            f"@{user.get('username')}" if user.get("username") else "Не указано"
        )
        telegram_id = user.get("telegram_id", "Неизвестно")

    # Безопасное получение данных тарифа
    if hasattr(tariff, "name"):
        tariff_name = tariff.name
        tariff_purpose = tariff.purpose or ""
        tariff_price = tariff.price
    else:
        # Если tariff - это словарь
        tariff_name = tariff.get("name", "Неизвестно")
        tariff_purpose = tariff.get("purpose", "")
        tariff_price = tariff.get("price", 0)

    purpose = tariff_purpose.lower() if tariff_purpose else ""
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    # Форматирование даты и времени
    if visit_time:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            # Если visit_date - строка
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)

        if hasattr(visit_time, "strftime"):
            time_str = visit_time.strftime("%H:%M")
        else:
            # Если visit_time - строка
            try:
                time_obj = datetime.strptime(str(visit_time), "%H:%M:%S").time()
                time_str = time_obj.strftime("%H:%M")
            except:
                time_str = str(visit_time)

        datetime_str = f"{date_str} в {time_str}"
    else:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            try:
                date_obj = datetime.strptime(str(visit_date), "%Y-%m-%d").date()
                date_str = date_obj.strftime("%d.%m.%Y")
            except:
                date_str = str(visit_date)
        datetime_str = f"{date_str} (весь день)"

    # Информация о промокоде
    discount_info = ""
    promocode_name = booking_data.get("promocode_name")
    if promocode_name:
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    # Информация о длительности
    duration_info = ""
    duration = booking_data.get("duration")
    if duration:
        duration_info = f"\n⏱ <b>Длительность:</b> {duration} час(ов)"

    # Сумма
    amount = booking_data.get("amount", 0)

    message = f"""🎯 <b>НОВАЯ БРОНЬ!</b> {tariff_emoji}

👤 <b>Клиент:</b> {user_name}
📱 <b>Телефон:</b> {user_phone}
💬 <b>Telegram:</b> {user_username}
🆔 <b>ID:</b> {telegram_id}

📋 <b>Тариф:</b> {tariff_name}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}{discount_info}

💰 <b>Сумма:</b> {amount:.0f} ₽
✅ <b>Статус:</b> Оплачено, ожидает подтверждения"""

    return message


def format_payment_notification(user, booking_data, status="SUCCESS") -> str:
    """Форматирует уведомление о платеже для администратора."""
    status_emojis = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "PENDING": "⏳",
        "CANCELLED": "🚫",
    }

    status_emoji = status_emojis.get(status, "❓")

    status_texts = {
        "SUCCESS": "ПЛАТЕЖ УСПЕШЕН",
        "FAILED": "ПЛАТЕЖ ОТКЛОНЕН",
        "PENDING": "ПЛАТЕЖ В ОЖИДАНИИ",
        "CANCELLED": "ПЛАТЕЖ ОТМЕНЕН",
    }

    status_text = status_texts.get(status, "НЕИЗВЕСТНЫЙ СТАТУС")

    # Правильное форматирование даты
    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    if visit_date:
        if hasattr(visit_date, "strftime"):
            date_str = visit_date.strftime("%d.%m.%Y")
        else:
            try:
                if isinstance(visit_date, str):
                    date_obj = datetime.strptime(visit_date, "%Y-%m-%d").date()
                    date_str = date_obj.strftime("%d.%m.%Y")
                else:
                    date_str = str(visit_date)
            except:
                date_str = "Неизвестно"
    else:
        date_str = "Неизвестно"

    # Добавляем время если есть
    if visit_time:
        if hasattr(visit_time, "strftime"):
            time_str = f" в {visit_time.strftime('%H:%M')}"
        else:
            try:
                if isinstance(visit_time, str):
                    time_obj = datetime.strptime(visit_time, "%H:%M:%S").time()
                    time_str = f" в {time_obj.strftime('%H:%M')}"
                else:
                    time_str = ""
            except:
                time_str = ""
    else:
        time_str = ""

    full_date_str = date_str + time_str

    # Добавляем информацию о длительности
    duration = booking_data.get("duration")
    duration_str = f" ({duration}ч)" if duration else ""

    message = f"""💳 <b>{status_text}</b> {status_emoji}

👤 <b>Клиент:</b> {user.get('full_name') or 'Не указано'}
📞 <b>Телефон:</b> {user.get('phone') or 'Не указано'}

💰 <b>Детали платежа:</b>
├ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽
├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
├ <b>Дата брони:</b> {full_date_str}{duration_str}
└ <b>Payment ID:</b> <code>{booking_data.get('payment_id', 'Неизвестно')}</code>

⏰ <i>Время: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def format_user_booking_notification(user, booking_data, confirmed: bool) -> str:
    """Форматирует уведомление о бронировании для пользователя."""
    tariff_emojis = {
        "опенспейс": "🏢",
        "переговорная": "🏛",
        "meeting": "🏛",
        "openspace": "🏢",
        "coworking": "🏢",
    }

    purpose = booking_data.get("tariff_purpose", "").lower()
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    if isinstance(visit_date, str):
        visit_date = datetime.fromisoformat(visit_date).date()

    if visit_time and isinstance(visit_time, str):
        visit_time = datetime.strptime(visit_time, "%H:%M:%S").time()

    if visit_time:
        datetime_str = (
            f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
        )
    else:
        datetime_str = f"{visit_date.strftime('%d.%m.%Y')} (весь день)"

    discount_info = ""
    if booking_data.get("promocode_name"):
        promocode_name = booking_data.get("promocode_name", "Неизвестный")
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    duration_info = ""
    if booking_data.get("duration"):
        duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"

    status_text = "Бронь подтверждена ✅" if confirmed else "Ожидайте подтверждения ⏳"
    status_instruction = (
        "\n\n💡 <b>Что дальше:</b> Ждем вас в назначенное время!"
        if confirmed
        else "\n\n💡 <b>Что дальше:</b> Администратор рассмотрит заявку и свяжется с вами."
    )

    message = f"""🎉 <b>Ваша бронь создана!</b> {tariff_emoji}

📋 <b>Детали брони:</b>
├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
├ <b>Дата и время:</b> {datetime_str}{duration_info}
└ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽{discount_info}

📌 <b>Статус:</b> {status_text}{status_instruction}

⏰ <i>Время создания: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""

    return message


def validate_phone_number(phone: str) -> tuple[bool, str]:
    """
    Валидация номера телефона.

    Returns:
        tuple: (is_valid, formatted_phone)
    """
    if not phone:
        return False, ""

    # Удаляем все кроме цифр и плюса
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Проверяем различные форматы
    if re.match(r"^(\+7|8|7)\d{10}$", cleaned):
        # Приводим к формату +7
        if cleaned.startswith("8"):
            formatted = "+7" + cleaned[1:]
        elif cleaned.startswith("7"):
            formatted = "+" + cleaned
        else:
            formatted = cleaned
        return True, formatted

    return False, phone


def validate_email(email: str) -> bool:
    """Валидация email адреса."""
    if not email:
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip().lower()))


def format_datetime_moscow(dt: datetime) -> str:
    """Форматирует datetime в московский часовой пояс."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MOSCOW_TZ)
    else:
        dt = dt.astimezone(MOSCOW_TZ)

    return dt.strftime("%d.%m.%Y %H:%M:%S")


def parse_duration_string(duration_str: str) -> Optional[int]:
    """Парсит строку длительности в часы."""
    if not duration_str:
        return None

    # Ищем числа в строке
    numbers = re.findall(r"\d+", duration_str)
    if numbers:
        return int(numbers[0])

    return None


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Обрезает текст до указанной длины."""
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def safe_int(value, default: int = 0) -> int:
    """Безопасное преобразование в int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value, default: float = 0.0) -> float:
    """Безопасное преобразование в float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
