import asyncio
import os
from datetime import date, time
from typing import Optional, Dict, Any, List

import aiohttp

from utils.logger import get_logger

logger = get_logger(__name__)


class BotAPIClient:
    """Клиент для взаимодействия с API из телеграм бота"""

    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://web:8000")
        self.api_token = None
        self.session = None
        self._auth_lock = asyncio.Lock()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Инициализация сессии и авторизация"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            await self._authenticate()

    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _authenticate(self):
        """Авторизация в API"""
        async with self._auth_lock:
            if self.api_token:
                return

            admin_login = os.getenv("ADMIN_LOGIN", "admin")
            admin_password = os.getenv("ADMIN_PASSWORD", "admin123")

            try:
                async with self.session.post(
                    f"{self.base_url}/login",
                    json={"login": admin_login, "password": admin_password},
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.api_token = data["access_token"]
                        logger.info("Успешная авторизация в API")
                    else:
                        logger.error(f"Ошибка авторизации: {resp.status}")
                        raise Exception("Failed to authenticate with API")
            except Exception as e:
                logger.error(f"Ошибка при авторизации: {e}")
                raise

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Выполнение запроса к API с автоматической переавторизацией"""
        if not self.session:
            await self.start()

        headers = kwargs.pop("headers", {})
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        url = f"{self.base_url}{endpoint}"

        for attempt in range(3):
            try:
                async with self.session.request(
                    method, url, headers=headers, **kwargs
                ) as resp:
                    if resp.status == 401 and attempt < 2:
                        # Токен истек, переавторизуемся
                        self.api_token = None
                        await self._authenticate()
                        headers["Authorization"] = f"Bearer {self.api_token}"
                        continue

                    if resp.status >= 400:
                        error_text = await resp.text()
                        logger.error(f"API error {resp.status}: {error_text}")
                        return {"error": error_text, "status": resp.status}

                    return await resp.json()

            except Exception as e:
                logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt == 2:
                    raise
                await asyncio.sleep(1)

    # === User методы ===

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получить пользователя по Telegram ID"""
        result = await self._make_request("GET", f"/users/telegram/{telegram_id}")
        if "error" in result:
            return None
        return result

    async def create_user(self, user_data: Dict) -> Dict:
        """Создать нового пользователя"""
        return await self._make_request("POST", "/users", json=user_data)

    async def update_user(self, user_id: int, user_data: Dict) -> Dict:
        """Обновить данные пользователя"""
        return await self._make_request("PUT", f"/users/{user_id}", json=user_data)

    # async def check_and_add_user(
    #     self,
    #     telegram_id: int,
    #     username: Optional[str] = None,
    #     language_code: str = "ru",
    #     referrer_id: Optional[int] = None,
    # ) -> Dict:
    #     """Проверка и добавление пользователя"""
    #     user_data = {
    #         "telegram_id": telegram_id,
    #         "username": username,
    #         "language_code": language_code,
    #         "referrer_id": referrer_id,
    #     }
    #     return await self._make_request("POST", "/users/check_and_add", json=user_data)

    async def check_and_add_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        language_code: str = "ru",
        referrer_id: Optional[int] = None,
    ) -> Dict:
        """
        Проверяет и добавляет пользователя в БД при первом обращении.

        Args:
            telegram_id: Telegram ID пользователя
            username: Username пользователя
            language_code: Код языка
            referrer_id: Telegram ID реферера

        Returns:
            Dict с информацией о пользователе и статусе операции
        """
        # Формируем параметры, исключая None значения
        params = {
            "telegram_id": telegram_id,
            "language_code": language_code,
        }

        if username:
            params["username"] = username

        if referrer_id is not None:
            params["referrer_id"] = referrer_id

        result = await self._make_request("POST", "/users/check_and_add", params=params)
        return result or {"user": None, "is_new": False, "is_complete": False}

    # === Tariff методы ===

    async def get_active_tariffs(self) -> List[Dict]:
        """Получить активные тарифы"""
        result = await self._make_request("GET", "/tariffs/active")
        if isinstance(result, list):
            return result
        return []

    async def get_tariff(self, tariff_id: int) -> Optional[Dict]:
        """Получить тариф по ID"""
        result = await self._make_request("GET", f"/tariffs/{tariff_id}")
        if "error" in result:
            return None
        return result

    # === Promocode методы ===

    async def get_promocode_by_name(self, name: str) -> Optional[Dict]:
        """Получить промокод по имени"""
        result = await self._make_request("GET", f"/promocodes/by_name/{name}")
        if "error" in result:
            return None
        return result

    async def use_promocode(self, promocode_id: int) -> Dict:
        """Использовать промокод"""
        return await self._make_request("POST", f"/promocodes/{promocode_id}/use")

    # === Booking методы ===

    async def create_booking(self, booking_data: Dict) -> Dict:
        """Создать бронирование"""
        # Преобразуем date и time в строки для JSON
        if "visit_date" in booking_data and isinstance(
            booking_data["visit_date"], date
        ):
            booking_data["visit_date"] = booking_data["visit_date"].isoformat()
        if "visit_time" in booking_data and isinstance(
            booking_data["visit_time"], time
        ):
            booking_data["visit_time"] = booking_data["visit_time"].isoformat()

        return await self._make_request("POST", "/bookings", json=booking_data)

    async def update_booking_payment(self, booking_id: int, payment_data: Dict) -> Dict:
        """Обновить статус оплаты бронирования"""
        return await self._make_request(
            "PUT", f"/bookings/{booking_id}/payment", json=payment_data
        )

    async def confirm_booking(self, booking_id: int) -> Dict:
        """Подтвердить бронирование"""
        return await self._make_request("PUT", f"/bookings/{booking_id}/confirm")

    # === Ticket методы ===

    async def create_ticket(self, ticket_data: Dict) -> Dict:
        """Создать тикет"""
        return await self._make_request("POST", "/tickets", json=ticket_data)

    async def get_user_tickets(
        self, telegram_id: int, status: Optional[str] = None
    ) -> List[Dict]:
        """Получить тикеты пользователя по Telegram ID"""
        params = {}
        if status:
            params["status"] = status

        result = await self._make_request(
            "GET", f"/users/telegram/{telegram_id}/tickets", params=params
        )

        if isinstance(result, list):
            return result
        return []

    async def update_ticket_status(
        self, ticket_id: int, status: str, comment: Optional[str] = None
    ) -> Dict:
        """Обновить статус тикета"""
        status_data = {"status": status}
        if comment:
            status_data["comment"] = comment

        return await self._make_request(
            "PUT", f"/tickets/{ticket_id}/status", json=status_data
        )

    async def get_tickets_stats(self) -> Dict:
        """Получить статистику по тикетам"""
        return await self._make_request("GET", "/tickets/stats")

    # === Payment методы ===

    async def create_payment(self, payment_data: Dict) -> Dict:
        """Создать платеж"""
        return await self._make_request("POST", "/payments/create", json=payment_data)

    async def check_payment_status(self, payment_id: str) -> Dict:
        """Проверить статус платежа"""
        return await self._make_request("GET", f"/payments/{payment_id}/status")

    async def cancel_payment(self, payment_id: str) -> Dict:
        """Отменить платеж"""
        return await self._make_request("POST", f"/payments/{payment_id}/cancel")

    # === Notification методы ===

    async def create_notification(self, notification_data: Dict) -> Dict:
        """Создать уведомление в системе"""
        return await self._make_request(
            "POST", "/notifications/create", json=notification_data
        )

    async def send_notification(
        self, user_id: int, message: str, target_url: Optional[str] = None
    ) -> Dict:
        """Создать уведомление для пользователя (для админки)"""
        notification_data = {
            "user_id": user_id,
            "message": message,
            "target_url": target_url,
        }
        return await self._make_request(
            "POST", "/notifications/create", json=notification_data
        )

    # === Rubitime методы ===

    async def create_rubitime_record(self, rubitime_params: Dict) -> Optional[str]:
        """Создать запись в Rubitime"""
        result = await self._make_request(
            "POST", "/rubitime/create_record", json=rubitime_params
        )
        if "error" in result:
            return None
        return result.get("rubitime_id")


# Глобальный экземпляр клиента
_api_client: Optional[BotAPIClient] = None


async def get_api_client() -> BotAPIClient:
    """Получить или создать экземпляр API клиента"""
    global _api_client
    if _api_client is None:
        _api_client = BotAPIClient()
        await _api_client.start()
    return _api_client


async def close_api_client():
    """Закрыть API клиента"""
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None
