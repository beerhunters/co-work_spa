import aiohttp
from typing import Optional, Dict, Any
from yookassa import Payment, Refund, Configuration

from config import (
    RUBITIME_API_KEY,
    RUBITIME_BASE_URL,
    RUBITIME_BRANCH_ID,
    RUBITIME_COOPERATOR_ID,
    YOKASSA_ACCOUNT_ID,
    get_yokassa_secret_key,  # Lazy loading функция
)
from utils.logger import get_logger

logger = get_logger(__name__)

# Настройка YooKassa (lazy initialization)
def _init_yookassa():
    """Ленивая инициализация YooKassa конфигурации"""
    yokassa_secret = get_yokassa_secret_key()
    if YOKASSA_ACCOUNT_ID and yokassa_secret:
        Configuration.account_id = YOKASSA_ACCOUNT_ID
        Configuration.secret_key = yokassa_secret
        return True
    return False


async def rubitime(method: str, extra_params: dict) -> Optional[str]:
    """
    Функция для работы с Rubitime API согласно их документации
    """
    if not RUBITIME_API_KEY:
        logger.warning("RUBITIME_API_KEY не настроен")
        return None

    try:
        if method == "create_record":
            url = f"{RUBITIME_BASE_URL}create-record"

            # Проверяем обязательные поля
            required_fields = ["service_id", "date", "phone", "name"]
            for field in required_fields:
                if field not in extra_params or not extra_params[field]:
                    logger.error(f"Rubitime: отсутствует обязательное поле {field}")
                    return None

            # Формируем параметры согласно документации Rubitime
            params = {
                "rk": RUBITIME_API_KEY,
                "branch_id": RUBITIME_BRANCH_ID,
                "cooperator_id": RUBITIME_COOPERATOR_ID,
                "service_id": int(extra_params["service_id"]),
                "status": 0,
                "record": extra_params["date"],  # ДАТА ЗАПИСИ
                "name": extra_params["name"],
                "phone": extra_params["phone"],
                "comment": extra_params.get("comment", ""),
                "source": extra_params.get("source", "Telegram Bot"),
            }

            # Добавляем email если передан
            if extra_params.get("email"):
                params["email"] = extra_params["email"]
                logger.info(
                    f"Email добавлен в запрос Rubitime: {extra_params['email']}"
                )

            # Добавляем duration только если он есть
            if extra_params.get("duration") is not None:
                params["duration"] = int(extra_params["duration"])

            logger.info(f"Отправляем запрос в Rubitime: {url}")
            logger.info(f"Параметры: {params}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params) as response:
                    response_text = await response.text()
                    logger.info(f"Ответ Rubitime ({response.status}): {response_text}")

                    if response.status == 200:
                        try:
                            data = await response.json()
                            if (
                                data.get("status") == "success"
                                or data.get("status") == "ok"
                            ):
                                # Ищем ID в ответе
                                record_id = None
                                data_section = data.get("data")

                                if isinstance(data_section, dict):
                                    record_id = data_section.get("id")
                                elif (
                                    isinstance(data_section, list)
                                    and len(data_section) > 0
                                ):
                                    if isinstance(data_section[0], dict):
                                        record_id = data_section[0].get("id")
                                    else:
                                        record_id = data_section[0]
                                elif data.get("id"):
                                    record_id = data.get("id")

                                logger.info(
                                    f"Успешно создана запись Rubitime с ID: {record_id}"
                                )
                                return str(record_id) if record_id else None
                            else:
                                error_msg = data.get("message", "Неизвестная ошибка")
                                logger.warning(f"Ошибка Rubitime: {error_msg}")
                                return None
                        except Exception as e:
                            logger.error(f"Ошибка парсинга ответа Rubitime: {e}")
                            return None
                    else:
                        logger.warning(
                            f"Rubitime вернул статус {response.status}: {response_text}"
                        )
                        return None

    except Exception as e:
        logger.error(f"Ошибка запроса к Rubitime: {e}")
        return None


async def create_yookassa_payment(payment_data: Dict[str, Any]) -> Dict[str, Any]:
    """Создание платежа через YooKassa."""
    try:
        # Инициализируем YooKassa при первом вызове
        if not _init_yookassa():
            raise Exception("YooKassa не настроена")

        payment = Payment.create(
            {
                "amount": {
                    "value": f"{payment_data.get('amount', 0):.2f}",
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": payment_data.get(
                        "return_url", "https://t.me/your_bot"
                    ),
                },
                "capture": True,
                "description": payment_data.get("description", "Оплата бронирования"),
            }
        )

        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status,
        }

    except Exception as e:
        logger.error(f"Ошибка создания платежа YooKassa: {e}")
        raise


async def check_yookassa_payment_status(payment_id: str) -> Dict[str, Any]:
    """Проверка статуса платежа YooKassa."""
    try:
        payment = Payment.find_one(payment_id)
        return {"status": payment.status}
    except Exception as e:
        logger.error(f"Ошибка проверки платежа YooKassa: {e}")
        raise


async def cancel_yookassa_payment(payment_id: str) -> Dict[str, Any]:
    """Отмена платежа YooKassa."""
    try:
        payment = Payment.find_one(payment_id)
        refund = Refund.create({"payment_id": payment_id, "amount": payment.amount})
        return {"status": refund.status}
    except Exception as e:
        logger.error(f"Ошибка отмены платежа YooKassa: {e}")
        raise


async def send_telegram_notification(
    bot, chat_id: int, message: str, parse_mode: str = "HTML"
):
    """Отправка уведомления через Telegram бота."""
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        logger.info(f"Уведомление отправлено в чат {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления в чат {chat_id}: {e}")
        return False


async def send_telegram_photo(
    bot, chat_id: int, photo, caption: str = None, parse_mode: str = "HTML"
):
    """Отправка фото через Telegram бота."""
    try:
        await bot.send_photo(
            chat_id=chat_id, photo=photo, caption=caption, parse_mode=parse_mode
        )
        logger.info(f"Фото отправлено в чат {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки фото в чат {chat_id}: {e}")
        return False
