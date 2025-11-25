"""
Утилиты для отправки email через SMTP и трекинга взаимодействий
"""

import asyncio
import uuid
import re
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Dict, Optional, List
from io import BytesIO
from datetime import datetime

import aiosmtplib
from jinja2 import Template
from PIL import Image

from config import (
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
    SMTP_USERNAME,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_TIMEOUT,
    SMTP_MAX_RETRIES,
    EMAIL_TRACKING_DOMAIN,
    MOSCOW_TZ,
    get_smtp_password,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class EmailSender:
    """Класс для отправки email с поддержкой трекинга и персонализации"""

    def __init__(self):
        """Инициализация email отправителя"""
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = get_smtp_password()  # Получаем из секретов или переменных окружения
        self.from_email = SMTP_FROM_EMAIL or SMTP_USERNAME
        self.from_name = SMTP_FROM_NAME
        self.use_ssl = SMTP_USE_SSL
        self.use_tls = SMTP_USE_TLS
        self.timeout = SMTP_TIMEOUT
        self.max_retries = SMTP_MAX_RETRIES

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        tracking_token: Optional[str] = None,
        personalization_data: Optional[Dict] = None,
    ) -> Dict[str, any]:
        """
        Отправляет email с трекингом и персонализацией

        Args:
            to_email: Email получателя
            subject: Тема письма
            html_content: HTML контент письма
            tracking_token: UUID токен для трекинга
            personalization_data: Данные для персонализации (замена переменных)

        Returns:
            Dict с результатом отправки: {'success': bool, 'error': str|None}
        """

        try:
            # Персонализация темы и контента
            if personalization_data:
                subject = self._personalize_text(subject, personalization_data)
                html_content = self._personalize_text(html_content, personalization_data)

            # Добавляем трекинг в HTML
            if tracking_token:
                html_content = self._add_tracking_to_html(html_content, tracking_token)

            # Создаем сообщение
            message = MIMEMultipart("alternative")
            message["From"] = formataddr((self.from_name, self.from_email))
            message["To"] = to_email
            message["Subject"] = subject

            # Добавляем HTML часть
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)

            # Отправка с повторными попытками
            for attempt in range(self.max_retries):
                try:
                    await self._send_smtp(message, to_email)
                    logger.info(f"Email успешно отправлен: {to_email}")
                    return {"success": True, "error": None}

                except Exception as e:
                    logger.warning(f"Попытка {attempt + 1}/{self.max_retries} не удалась для {to_email}: {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        raise

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ошибка отправки email на {to_email}: {error_msg}", exc_info=True)
            return {"success": False, "error": error_msg}

    async def _send_smtp(self, message: MIMEMultipart, to_email: str):
        """Отправляет сообщение через SMTP"""

        # Настройка SSL/TLS контекста
        if self.use_ssl or self.use_tls:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE  # Для Яндекс может потребоваться
        else:
            ssl_context = None

        # Создаем SMTP клиент
        if self.use_ssl:
            # SSL на порту 465 - implicit TLS с самого начала
            smtp = aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=True,  # Использовать implicit TLS
                tls_context=ssl_context,
                timeout=self.timeout,
            )
        else:
            # STARTTLS на порту 587 или обычный SMTP
            smtp = aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=False,  # Не использовать implicit TLS
                timeout=self.timeout,
            )

        try:
            await smtp.connect()

            # Для STARTTLS явно вызываем starttls() перед аутентификацией
            if self.use_tls and not self.use_ssl:
                await smtp.starttls(tls_context=ssl_context)

            # Аутентификация
            if self.smtp_username and self.smtp_password:
                await smtp.login(self.smtp_username, self.smtp_password)

            # Отправка
            await smtp.send_message(message)

        finally:
            try:
                await smtp.quit()
            except Exception:
                pass  # Игнорируем ошибки при закрытии соединения

    def _personalize_text(self, text: str, data: Dict) -> str:
        """
        Заменяет переменные в тексте на значения из data

        Поддерживает:
        - {{variable}} - простая замена
        - {% if condition %}...{% endif %} - условия (упрощенная версия)

        Args:
            text: Текст с переменными
            data: Словарь с данными для подстановки

        Returns:
            Текст с замененными переменными
        """

        try:
            # Используем Jinja2 для продвинутой персонализации
            template = Template(text)
            return template.render(**data)

        except Exception as e:
            logger.warning(f"Ошибка персонализации текста: {e}")
            # В случае ошибки просто заменяем базовые переменные
            for key, value in data.items():
                text = text.replace(f"{{{{{key}}}}}", str(value))
            return text

    def _add_tracking_to_html(self, html_content: str, tracking_token: str) -> str:
        """
        Добавляет трекинг в HTML контент

        - Добавляет tracking pixel для отслеживания открытий
        - Заменяет ссылки на tracked links для отслеживания кликов

        Args:
            html_content: Исходный HTML
            tracking_token: UUID токен для трекинга

        Returns:
            HTML с добавленным трекингом
        """

        # 1. Добавляем tracking pixel в конец body
        # EMAIL_TRACKING_DOMAIN может содержать /api, поэтому убираем дубликаты
        base_url = EMAIL_TRACKING_DOMAIN.rstrip('/')
        # Убираем /api если он уже есть в конце
        if base_url.endswith('/api'):
            base_url = base_url[:-4]

        tracking_pixel_url = f"{base_url}/api/emails/track/{tracking_token}/open.png"
        tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" alt="" />'

        # Вставляем перед закрывающим </body> или в конец
        if "</body>" in html_content:
            html_content = html_content.replace("</body>", f"{tracking_pixel}</body>")
        else:
            html_content += tracking_pixel

        # 2. Заменяем все ссылки на tracked links
        def replace_link(match):
            original_url = match.group(1)
            # Пропускаем уже tracked ссылки и tracking pixel
            if "track/" in original_url or "open.png" in original_url:
                return match.group(0)

            # Создаем tracked URL
            tracked_url = f"{base_url}/api/emails/track/{tracking_token}/click?url={original_url}"
            return f'href="{tracked_url}"'

        # Ищем все href="..." и заменяем
        html_content = re.sub(r'href="([^"]+)"', replace_link, html_content)

        return html_content

    @staticmethod
    def generate_tracking_token() -> str:
        """Генерирует уникальный tracking token (UUID)"""
        return str(uuid.uuid4())

    @staticmethod
    def generate_tracking_pixel() -> bytes:
        """
        Генерирует 1x1 прозрачный PNG для трекинга открытий

        Returns:
            bytes: PNG изображение
        """
        # Создаем 1x1 прозрачное изображение
        img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))

        # Сохраняем в BytesIO
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue()


class EmailPersonalizer:
    """Класс для подготовки данных персонализации"""

    @staticmethod
    def prepare_user_data(user) -> Dict[str, any]:
        """
        Подготавливает данные пользователя для персонализации

        Args:
            user: Объект User из БД

        Returns:
            Dict с данными для подстановки в шаблон
        """

        # Разбиваем full_name на части
        full_name = user.full_name or ""
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else "Пользователь"
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        return {
            # Основные данные
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name or "Уважаемый пользователь",
            "email": user.email or "",
            "phone": user.phone or "",
            "username": user.username or "",

            # Статистика
            "successful_bookings": user.successful_bookings or 0,
            "invited_count": user.invited_count or 0,

            # Статус
            "is_vip": user.successful_bookings >= 10,  # VIP если 10+ бронирований
            "is_new": (datetime.now(MOSCOW_TZ) - user.first_join_time).days <= 7,  # Новый если < 7 дней

            # Даты
            "reg_date": user.reg_date.strftime("%d.%m.%Y") if user.reg_date else "",
            "first_join_date": user.first_join_time.strftime("%d.%m.%Y"),
        }


class EmailValidator:
    """Класс для валидации email адресов"""

    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    )

    @classmethod
    def is_valid_email(cls, email: str) -> bool:
        """Проверяет валидность email адреса"""
        if not email or not isinstance(email, str):
            return False
        return bool(cls.EMAIL_REGEX.match(email.strip()))

    @classmethod
    def filter_valid_emails(cls, emails: List[str]) -> List[str]:
        """Фильтрует список, оставляя только валидные email"""
        return [email for email in emails if cls.is_valid_email(email)]


# Глобальный экземпляр отправителя
_email_sender = None


def get_email_sender() -> EmailSender:
    """Получить глобальный экземпляр EmailSender (Singleton)"""
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender
