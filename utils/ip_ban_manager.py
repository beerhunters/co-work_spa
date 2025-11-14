"""
Система управления банами IP адресов для защиты от сканеров и ботов
Использует Redis для хранения забаненных IP и счетчиков подозрительной активности
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import redis.asyncio as redis

from config import REDIS_URL, ADMIN_TELEGRAM_ID
from utils.logger import get_logger
from utils.bot_instance import get_bot

logger = get_logger(__name__)

# Настройки системы банов
MAX_SUSPICIOUS_REQUESTS = 5  # Количество подозрительных запросов до бана
BAN_DURATION = 86400  # Время бана в секундах (24 часа) - по умолчанию
TRACKING_WINDOW = 3600  # Окно отслеживания в секундах (1 час)

# Предустановленные длительности банов (градации)
BAN_DURATIONS = {
    "hour": 3600,  # 1 час
    "day": 86400,  # 1 день (24 часа)
    "week": 604800,  # 1 неделя (7 дней)
    "month": 2592000,  # 1 месяц (30 дней)
    "permanent": 31536000,  # 1 год (~навсегда)
}

# Whitelist IP адресов, которые никогда не банятся
WHITELIST_IPS = ["127.0.0.1", "localhost", "::1", "185.115.98.132"]

# Whitelist подсетей (Docker networks и т.д.)
WHITELIST_PREFIXES = [
    "172.",  # Docker default network
    "10.",  # Private network
    "192.168.",  # Private network
]

# Настройки уведомлений в Telegram
TELEGRAM_NOTIFICATION_ENABLED = True  # Включить/выключить уведомления
TELEGRAM_NOTIFICATION_THROTTLE = (
    300  # Минимальный интервал между уведомлениями в секундах (5 минут)
)


class IPBanManager:
    """Менеджер для управления банами IP адресов"""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._redis_available = False

        # Префиксы ключей в Redis
        self.BAN_KEY_PREFIX = "ip_ban:"
        self.SUSPICIOUS_KEY_PREFIX = "ip_suspicious:"
        self.NOTIFICATION_KEY_PREFIX = "ip_ban_notification:"

    async def _get_redis(self) -> Optional[redis.Redis]:
        """Получает подключение к Redis"""
        if self._redis is None:
            try:
                self._redis = redis.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
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
                    ban_info["unbanned_at"] = (
                        datetime.now() + timedelta(seconds=ttl)
                    ).isoformat()
                    ban_info["seconds_remaining"] = ttl

                return ban_info

            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о бане для {ip}: {e}")
            return None

    async def ban_ip(
        self,
        ip: str,
        reason: str = "Suspicious activity",
        duration: int = None,
        duration_type: str = "day",
        manual: bool = False,
        admin: str = None,
    ) -> bool:
        """
        Банит IP адрес

        Args:
            ip: IP адрес для бана
            reason: Причина бана
            duration: Длительность бана в секундах (если None, используется duration_type)
            duration_type: Тип длительности ('hour', 'day', 'week', 'month', 'permanent')
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

        # Определяем длительность бана
        if duration is None:
            duration = BAN_DURATIONS.get(duration_type, BAN_DURATIONS["day"])

        try:
            key = f"{self.BAN_KEY_PREFIX}{ip}"

            ban_info = {
                "ip": ip,
                "reason": reason,
                "banned_at": datetime.now().isoformat(),
                "duration": duration,
                "duration_type": duration_type if duration is None else "custom",
                "manual": manual,
                "admin": admin,
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
                logger.info(
                    f"IP {ip} разбанен{f' администратором {admin}' if admin else ''}"
                )
                return True
            else:
                logger.info(f"IP {ip} не был забанен")
                return False
        except Exception as e:
            logger.error(f"Ошибка разбана IP {ip}: {e}")
            return False

    async def track_suspicious_request(
        self, ip: str, reason: str = "Unknown API error"
    ) -> bool:
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

            logger.info(
                f"Подозрительный запрос от {ip}: {reason}. Счетчик: {count}/{MAX_SUSPICIOUS_REQUESTS}"
            )

            # Если превышен порог, баним
            if count >= MAX_SUSPICIOUS_REQUESTS:
                logger.warning(
                    f"IP {ip} превысил порог подозрительных запросов ({count}). Выполняется автобан."
                )

                ban_reason = f"Auto-ban: {count} suspicious requests ({reason})"
                await self.ban_ip(
                    ip=ip, reason=ban_reason, duration=BAN_DURATION, manual=False
                )

                # Отправляем уведомление в Telegram
                await self._send_telegram_notification(ip, reason, count)

                return True

            return False
        except Exception as e:
            logger.error(f"Ошибка отслеживания подозрительного запроса от {ip}: {e}")
            return False

    async def _send_telegram_notification(
        self, ip: str, reason: str, count: int
    ) -> None:
        """
        Отправляет уведомление в Telegram об автобане IP с throttling

        Args:
            ip: Забаненный IP адрес
            reason: Причина бана
            count: Количество подозрительных запросов
        """
        if not TELEGRAM_NOTIFICATION_ENABLED:
            return

        if not ADMIN_TELEGRAM_ID:
            logger.warning("ADMIN_TELEGRAM_ID не установлен, уведомление не отправлено")
            return

        redis_client = await self._get_redis()
        if not redis_client or not self._redis_available:
            logger.warning("Redis недоступен, уведомление не отправлено")
            return

        try:
            # Проверяем, не отправляли ли мы уведомление недавно
            notification_key = f"{self.NOTIFICATION_KEY_PREFIX}last_sent"
            last_sent = await redis_client.get(notification_key)

            if last_sent:
                logger.debug(
                    f"Уведомление об автобане пропущено из-за throttling (последнее отправлено {last_sent})"
                )
                return

            # Отправляем уведомление
            bot = get_bot()
            message = (
                f"🚫 <b>Автоматический бан IP адреса</b>\n\n"
                f"<b>IP:</b> <code>{ip}</code>\n"
                f"<b>Причина:</b> {reason}\n"
                f"<b>Подозрительных запросов:</b> {count}\n"
                f"<b>Длительность:</b> {BAN_DURATION // 3600} часов\n"
                f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"IP адрес был автоматически заблокирован системой защиты."
            )

            # await bot.send_message(
            #     chat_id=ADMIN_TELEGRAM_ID, text=message, parse_mode="HTML"
            # )

            # Устанавливаем метку о последней отправке с TTL
            await redis_client.setex(
                notification_key,
                TELEGRAM_NOTIFICATION_THROTTLE,
                datetime.now().isoformat(),
            )

            logger.info(
                f"Telegram уведомление об автобане IP {ip} отправлено администратору"
            )

        except Exception as e:
            logger.error(
                f"Ошибка отправки Telegram уведомления об автобане IP {ip}: {e}"
            )

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
                                ban_info["unbanned_at"] = (
                                    datetime.now() + timedelta(seconds=ttl)
                                ).isoformat()

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
            return {"redis_available": False, "total_banned": 0, "total_tracked": 0}

        try:
            # Считаем забаненные IP
            ban_pattern = f"{self.BAN_KEY_PREFIX}*"
            banned_count = 0
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=ban_pattern, count=100
                )
                banned_count += len(keys)
                if cursor == 0:
                    break

            # Считаем отслеживаемые IP
            suspicious_pattern = f"{self.SUSPICIOUS_KEY_PREFIX}*"
            tracked_count = 0
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(
                    cursor, match=suspicious_pattern, count=100
                )
                tracked_count += len(keys)
                if cursor == 0:
                    break

            return {
                "redis_available": True,
                "total_banned": banned_count,
                "total_tracked": tracked_count,
                "ban_duration": BAN_DURATION,
                "tracking_window": TRACKING_WINDOW,
                "max_suspicious_requests": MAX_SUSPICIOUS_REQUESTS,
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"redis_available": False, "error": str(e)}

    async def export_to_nginx(
        self, output_path: str = "/app/config/banned_ips.conf"
    ) -> Dict[str, Any]:
        """
        Экспортирует забаненные IP в конфигурационный файл nginx

        Args:
            output_path: Путь к файлу конфигурации nginx

        Returns:
            Dict с результатом экспорта
        """
        try:
            # Получаем все забаненные IP
            banned_ips = await self.get_banned_ips(limit=1000)

            if not banned_ips:
                logger.info("Нет забаненных IP для экспорта")
                # Создаем пустой файл
                with open(output_path, "w") as f:
                    f.write("# No banned IPs\n")
                return {
                    "success": True,
                    "exported_count": 0,
                    "file_path": output_path,
                    "message": "No banned IPs to export",
                }

            # Генерируем nginx конфигурацию
            config_lines = [
                "# Автоматически сгенерированный список забаненных IP",
                f"# Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"# Всего забаненных IP: {len(banned_ips)}",
                "",
                "# Deny directives для забаненных IP адресов",
            ]

            for ban_info in banned_ips:
                ip = ban_info.get("ip")
                reason = ban_info.get("reason", "Unknown")
                if ip:
                    # Экранируем причину для комментария
                    safe_reason = reason.replace('"', '\\"').replace("\n", " ")
                    config_lines.append(f"deny {ip};  # {safe_reason}")

            config_lines.append("")  # Пустая строка в конце

            # Записываем в файл
            import os

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "w") as f:
                f.write("\n".join(config_lines))

            logger.info(
                f"Экспортировано {len(banned_ips)} забаненных IP в {output_path}"
            )

            return {
                "success": True,
                "exported_count": len(banned_ips),
                "file_path": output_path,
                "message": f"Successfully exported {len(banned_ips)} banned IPs",
            }

        except Exception as e:
            logger.error(f"Ошибка экспорта забаненных IP в nginx: {e}")
            return {
                "success": False,
                "exported_count": 0,
                "error": str(e),
                "message": "Failed to export banned IPs",
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
