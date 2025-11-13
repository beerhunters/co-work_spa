"""
Система управления банами IP адресов для защиты от сканеров и ботов
Использует Redis для хранения забаненных IP и счетчиков подозрительной активности
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import redis.asyncio as redis

from config import REDIS_URL
from utils.logger import get_logger

logger = get_logger(__name__)

# Настройки системы банов
MAX_SUSPICIOUS_REQUESTS = 5  # Количество подозрительных запросов до бана
BAN_DURATION = 86400  # Время бана в секундах (24 часа)
TRACKING_WINDOW = 3600  # Окно отслеживания в секундах (1 час)

# Whitelist IP адресов, которые никогда не банятся
WHITELIST_IPS = [
    '127.0.0.1',
    'localhost',
    '::1',
]

# Whitelist подсетей (Docker networks и т.д.)
WHITELIST_PREFIXES = [
    '172.',  # Docker default network
    '10.',   # Private network
    '192.168.',  # Private network
]


class IPBanManager:
    """Менеджер для управления банами IP адресов"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._redis_available = False

        # Префиксы ключей в Redis
        self.BAN_KEY_PREFIX = "ip_ban:"
        self.SUSPICIOUS_KEY_PREFIX = "ip_suspicious:"

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Получает подключение к Redis"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # Проверяем подключение
                await self._redis.ping()
                self._redis_available = True
                logger.info("IPBanManager: подключение к Redis установлено")
            except Exception as e:
                logger.error(f"IPBanManager: не удалось подключиться к Redis: {e}")
                self._redis_available = False
                self._redis = None

        return self._redis

    def _is_whitelisted(self, ip: str) -> bool:
        """Проверяет, находится ли IP в whitelist"""
        if ip in WHITELIST_IPS:
            return True

        for prefix in WHITELIST_PREFIXES:
            if ip.startswith(prefix):
                return True

        return False

    async def is_banned(self, ip: str) -> bool:
        """
        Проверяет, забанен ли IP адрес

        Args:
            ip: IP адрес для проверки

        Returns:
            True если IP забанен, иначе False
        """
        if self._is_whitelisted(ip):
            return False

        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            return False  # Если Redis недоступен, не баним

        try:
            key = f"{self.BAN_KEY_PREFIX}{ip}"
            exists = await redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Ошибка проверки бана для {ip}: {e}")
            return False

    async def get_ban_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о бане IP адреса

        Args:
            ip: IP адрес

        Returns:
            Dict с информацией о бане или None если IP не забанен
        """
        if self._is_whitelisted(ip):
            return None

        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            return None

        try:
            key = f"{self.BAN_KEY_PREFIX}{ip}"
            data = await redis_client.get(key)

            if data:
                ban_info = json.loads(data)
                # Получаем TTL для вычисления времени разбана
                ttl = await redis_client.ttl(key)
                if ttl > 0:
                    ban_info["unbanned_at"] = (datetime.now() + timedelta(seconds=ttl)).isoformat()
                    ban_info["seconds_remaining"] = ttl

                return ban_info

            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о бане для {ip}: {e}")
            return None

    async def ban_ip(self, ip: str, reason: str = "Suspicious activity", duration: int = BAN_DURATION,
                     manual: bool = False, admin: str = None) -> bool:
        """
        Банит IP адрес

        Args:
            ip: IP адрес для бана
            reason: Причина бана
            duration: Длительность бана в секундах
            manual: Был ли бан выполнен вручную
            admin: Логин администратора (для ручного бана)

        Returns:
            True если бан успешен, иначе False
        """
        if self._is_whitelisted(ip):
            logger.warning(f"Попытка забанить whitelisted IP: {ip}")
            return False

        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            logger.error(f"Не удалось забанить {ip}: Redis недоступен")
            return False

        try:
            key = f"{self.BAN_KEY_PREFIX}{ip}"

            ban_info = {
                "ip": ip,
                "reason": reason,
                "banned_at": datetime.now().isoformat(),
                "duration": duration,
                "manual": manual,
                "admin": admin
            }

            # Сохраняем с TTL
            await redis_client.setex(key, duration, json.dumps(ban_info))

            # Очищаем счетчик подозрительных запросов
            suspicious_key = f"{self.SUSPICIOUS_KEY_PREFIX}{ip}"
            await redis_client.delete(suspicious_key)

            logger.warning(
                f"IP {ip} забанен на {duration}s. "
                f"Причина: {reason}. "
                f"{'Ручной бан' if manual else 'Автоматический бан'}"
                f"{f' администратором {admin}' if admin else ''}"
            )

            return True
        except Exception as e:
            logger.error(f"Ошибка бана IP {ip}: {e}")
            return False

    async def unban_ip(self, ip: str, admin: str = None) -> bool:
        """
        Разбанивает IP адрес

        Args:
            ip: IP адрес для разбана
            admin: Логин администратора

        Returns:
            True если разбан успешен, иначе False
        """
        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            logger.error(f"Не удалось разбанить {ip}: Redis недоступен")
            return False

        try:
            key = f"{self.BAN_KEY_PREFIX}{ip}"
            result = await redis_client.delete(key)

            # Очищаем счетчик подозрительных запросов
            suspicious_key = f"{self.SUSPICIOUS_KEY_PREFIX}{ip}"
            await redis_client.delete(suspicious_key)

            if result:
                logger.info(f"IP {ip} разбанен{f' администратором {admin}' if admin else ''}")
                return True
            else:
                logger.info(f"IP {ip} не был забанен")
                return False
        except Exception as e:
            logger.error(f"Ошибка разбана IP {ip}: {e}")
            return False

    async def track_suspicious_request(self, ip: str, reason: str = "Unknown API error") -> bool:
        """
        Отслеживает подозрительный запрос от IP

        Увеличивает счетчик подозрительных запросов.
        Если счетчик превышает порог, автоматически банит IP.

        Args:
            ip: IP адрес
            reason: Причина подозрения

        Returns:
            True если IP был забанен, иначе False
        """
        if self._is_whitelisted(ip):
            return False

        # Проверяем, не забанен ли уже
        if await self.is_banned(ip):
            return False

        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            return False

        try:
            key = f"{self.SUSPICIOUS_KEY_PREFIX}{ip}"

            # Увеличиваем счетчик
            count = await redis_client.incr(key)

            # Устанавливаем TTL при первом инкременте
            if count == 1:
                await redis_client.expire(key, TRACKING_WINDOW)

            logger.info(f"Подозрительный запрос от {ip}: {reason}. Счетчик: {count}/{MAX_SUSPICIOUS_REQUESTS}")

            # Если превышен порог, баним
            if count >= MAX_SUSPICIOUS_REQUESTS:
                logger.warning(f"IP {ip} превысил порог подозрительных запросов ({count}). Выполняется автобан.")
                await self.ban_ip(
                    ip=ip,
                    reason=f"Auto-ban: {count} suspicious requests ({reason})",
                    duration=BAN_DURATION,
                    manual=False
                )
                return True

            return False
        except Exception as e:
            logger.error(f"Ошибка отслеживания подозрительного запроса от {ip}: {e}")
            return False

    async def get_banned_ips(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получает список всех забаненных IP адресов

        Args:
            limit: Максимальное количество IP для возврата

        Returns:
            Список словарей с информацией о банах
        """
        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            return []

        try:
            pattern = f"{self.BAN_KEY_PREFIX}*"
            banned_ips = []

            # Используем SCAN для получения ключей
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)

                for key in keys:
                    if len(banned_ips) >= limit:
                        break

                    try:
                        data = await redis_client.get(key)
                        if data:
                            ban_info = json.loads(data)

                            # Добавляем TTL
                            ttl = await redis_client.ttl(key)
                            if ttl > 0:
                                ban_info["seconds_remaining"] = ttl
                                ban_info["unbanned_at"] = (datetime.now() + timedelta(seconds=ttl)).isoformat()

                            banned_ips.append(ban_info)
                    except Exception as e:
                        logger.error(f"Ошибка получения данных для ключа {key}: {e}")

                if cursor == 0 or len(banned_ips) >= limit:
                    break

            return banned_ips
        except Exception as e:
            logger.error(f"Ошибка получения списка забаненных IP: {e}")
            return []

    async def get_stats(self) -> Dict[str, Any]:
        """
        Получает статистику системы банов

        Returns:
            Dict со статистикой
        """
        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            return {
                "redis_available": False,
                "total_banned": 0,
                "total_tracked": 0
            }

        try:
            # Считаем забаненные IP
            ban_pattern = f"{self.BAN_KEY_PREFIX}*"
            banned_count = 0
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=ban_pattern, count=100)
                banned_count += len(keys)
                if cursor == 0:
                    break

            # Считаем отслеживаемые IP
            suspicious_pattern = f"{self.SUSPICIOUS_KEY_PREFIX}*"
            tracked_count = 0
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=suspicious_pattern, count=100)
                tracked_count += len(keys)
                if cursor == 0:
                    break

            return {
                "redis_available": True,
                "total_banned": banned_count,
                "total_tracked": tracked_count,
                "ban_duration": BAN_DURATION,
                "tracking_window": TRACKING_WINDOW,
                "max_suspicious_requests": MAX_SUSPICIOUS_REQUESTS
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {
                "redis_available": False,
                "error": str(e)
            }

    async def close(self):
        """Закрывает подключение к Redis"""
        if self._redis:
            try:
                await self._redis.close()
                logger.info("IPBanManager: подключение к Redis закрыто")
            except Exception as e:
                logger.error(f"Ошибка закрытия подключения к Redis: {e}")


# Глобальный экземпляр менеджера
_ip_ban_manager = IPBanManager()


def get_ip_ban_manager() -> IPBanManager:
    """Получает глобальный экземпляр IPBanManager"""
    return _ip_ban_manager
