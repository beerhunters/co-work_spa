"""
Celery задачи для email рассылок
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
from celery import Task

from celery_app import celery_app
from config import MOSCOW_TZ, EMAIL_BATCH_SIZE, EMAIL_BATCH_DELAY
from models.models import (
    EmailCampaign,
    EmailCampaignRecipient,
    User,
    DatabaseManager,
)
from routes.emails import get_users_by_segment
from utils.email_sender import (
    EmailSender,
    EmailPersonalizer,
    get_email_sender,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class CallbackTask(Task):
    """Базовая задача с коллбеками для отслеживания прогресса."""

    def on_success(self, retval, task_id, args, kwargs):
        """Вызывается при успешном завершении задачи."""
        logger.info(f"Email task {task_id} завершена успешно")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Вызывается при провале задачи."""
        logger.error(f"Email task {task_id} провалилась: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Вызывается при повторной попытке задачи."""
        logger.warning(f"Email task {task_id} повторная попытка: {exc}")


# ===================================
# Основная задача отправки кампании
# ===================================


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name='tasks.email_tasks.send_email_campaign_task',
    max_retries=3,
    default_retry_delay=120,  # 2 минуты между попытками
)
def send_email_campaign_task(self, campaign_id: int):
    """
    Celery задача для отправки email кампании.

    Загружает кампанию, получает список получателей,
    создает записи EmailCampaignRecipient с tracking tokens,
    и отправляет письма батчами.

    Args:
        campaign_id: ID кампании для отправки

    Returns:
        Dict с результатами: {
            'campaign_id': int,
            'sent_count': int,
            'failed_count': int,
            'status': str,
            'duration_seconds': float
        }
    """
    start_time = datetime.now()

    try:
        # Обновляем статус задачи
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 0,
                'status': 'Загрузка кампании...',
                'campaign_id': campaign_id,
            }
        )

        # Получаем event loop для async операций
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Запускаем async функцию отправки
        result = loop.run_until_complete(
            _send_email_campaign_async(self, campaign_id, start_time)
        )

        return result

    except ValueError as e:
        # Non-recoverable ошибки (кампания не найдена, неправильный статус и т.д.)
        # НЕ делаем retry, просто логируем и завершаем задачу
        error_msg = str(e)
        logger.warning(f"Non-recoverable ошибка для кампании {campaign_id}: {error_msg}")

        # Пытаемся обновить статус на failed если кампания существует
        def _mark_failed(session):
            campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign:
                campaign.status = "failed"
                session.commit()
                logger.info(f"Кампания {campaign_id} помечена как failed: {error_msg}")

        try:
            DatabaseManager.safe_execute(_mark_failed)
        except Exception:
            # Кампания не существует или другая ошибка БД - игнорируем
            pass

        # Завершаем задачу без retry
        return {
            'campaign_id': campaign_id,
            'sent_count': 0,
            'failed_count': 0,
            'status': 'failed',
            'error': error_msg,
            'duration_seconds': (datetime.now() - start_time).total_seconds()
        }

    except Exception as e:
        # Recoverable ошибки (сетевые проблемы, временные сбои и т.д.)
        logger.error(f"Recoverable ошибка в send_email_campaign_task для кампании {campaign_id}: {e}", exc_info=True)

        # Обновляем статус кампании на failed
        def _mark_failed(session):
            campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign:
                campaign.status = "failed"
                session.commit()

        try:
            DatabaseManager.safe_execute(_mark_failed)
        except Exception as db_error:
            logger.error(f"Не удалось обновить статус кампании на failed: {db_error}")

        # Делаем retry только для recoverable ошибок
        raise self.retry(exc=e)


async def _send_email_campaign_async(task: Task, campaign_id: int, start_time: datetime) -> Dict:
    """
    Асинхронная функция для отправки email кампании.

    Последовательность:
    1. Загружает кампанию из БД
    2. Получает список получателей на основе recipient_type
    3. Создает записи EmailCampaignRecipient с tracking tokens
    4. Определяет A/B варианты если включен A/B тест
    5. Отправляет письма батчами с персонализацией
    6. Обновляет статистику в БД
    """

    # 1. Загружаем кампанию
    def _load_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise ValueError(f"Кампания {campaign_id} не найдена")

        if campaign.status not in ["draft", "scheduled", "sending"]:
            raise ValueError(f"Кампания {campaign_id} в статусе {campaign.status}, отправка невозможна")

        # Обновляем статус на sending
        campaign.status = "sending"
        session.commit()

        return {
            "id": campaign.id,
            "name": campaign.name,
            "subject": campaign.subject,
            "html_content": campaign.html_content,
            "recipient_type": campaign.recipient_type,
            "recipient_ids": campaign.recipient_ids,
            "segment_type": campaign.segment_type,
            "segment_params": campaign.segment_params,
            "custom_emails": campaign.custom_emails,
            "is_ab_test": campaign.is_ab_test,
            "ab_test_percentage": campaign.ab_test_percentage,
            "ab_variant_b_subject": campaign.ab_variant_b_subject,
            "ab_variant_b_content": campaign.ab_variant_b_content,
        }

    campaign_data = DatabaseManager.safe_execute(_load_campaign)
    logger.info(f"Загружена кампания {campaign_id}: {campaign_data['name']}")

    # 2. Получаем список получателей
    def _get_recipients(session):
        if campaign_data["recipient_type"] == "custom":
            # Для custom emails создаем получателей из списка адресов
            custom_emails_str = campaign_data["custom_emails"]
            if not custom_emails_str:
                return []

            emails = [email.strip() for email in custom_emails_str.split(",") if email.strip()]
            return [
                {
                    "user_id": None,  # Нет user_id для custom emails
                    "email": email,
                    "full_name": "Получатель",  # Нет имени для custom emails
                    "username": "",
                    "phone": "",
                    "successful_bookings": 0,
                    "invited_count": 0,
                    "reg_date": None,
                    "first_join_time": None,
                }
                for email in emails
            ]

        elif campaign_data["recipient_type"] == "selected":
            recipient_ids = json.loads(campaign_data["recipient_ids"]) if campaign_data["recipient_ids"] else []
            users = session.query(User).filter(
                User.id.in_(recipient_ids),
                User.is_banned == False,
                User.email.isnot(None),
                User.email != ""
            ).all()

        elif campaign_data["recipient_type"] == "segment":
            segment_params = json.loads(campaign_data["segment_params"]) if campaign_data["segment_params"] else {}
            users = get_users_by_segment(session, campaign_data["segment_type"], segment_params)

        else:  # all
            users = get_users_by_segment(session, "all")

        # Для типов кроме custom возвращаем пользователей из базы
        if campaign_data["recipient_type"] != "custom":
            return [
                {
                    "user_id": u.id,
                    "email": u.email,
                    "full_name": u.full_name or "Пользователь",
                    "username": u.username or "",
                    "phone": u.phone or "",
                    "successful_bookings": u.successful_bookings or 0,
                    "invited_count": u.invited_count or 0,
                    "reg_date": u.reg_date,
                    "first_join_time": u.first_join_time,
                }
                for u in users
            ]

    recipients = DatabaseManager.safe_execute(_get_recipients)
    total_recipients = len(recipients)

    logger.info(f"Найдено {total_recipients} получателей для кампании {campaign_id}")

    if total_recipients == 0:
        logger.warning(f"Нет получателей для кампании {campaign_id}, завершаем")

        def _mark_sent_no_recipients(session):
            campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
            if campaign:
                campaign.status = "sent"
                campaign.sent_at = datetime.now(MOSCOW_TZ)
                session.commit()

        DatabaseManager.safe_execute(_mark_sent_no_recipients)

        return {
            "campaign_id": campaign_id,
            "sent_count": 0,
            "failed_count": 0,
            "status": "sent",
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
        }

    # Обновляем прогресс
    task.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': total_recipients,
            'status': f'Создание {total_recipients} записей получателей...',
            'campaign_id': campaign_id,
        }
    )

    # 3. Создаем записи EmailCampaignRecipient с tracking tokens
    def _create_recipients(session):
        from utils.email_sender import EmailSender

        recipients_records = []

        for idx, recipient in enumerate(recipients):
            # Определяем A/B вариант
            ab_variant = None
            if campaign_data["is_ab_test"]:
                # Распределяем получателей по A/B вариантам
                percentage = campaign_data["ab_test_percentage"] or 50
                ab_variant = "A" if (idx % 100) < percentage else "B"

            # Генерируем tracking token
            tracking_token = EmailSender.generate_tracking_token()

            recipient_record = EmailCampaignRecipient(
                campaign_id=campaign_id,
                user_id=recipient["user_id"],
                email=recipient["email"],
                full_name=recipient["full_name"],
                tracking_token=tracking_token,
                ab_variant=ab_variant,
                status="pending",
            )

            recipients_records.append(recipient_record)

        session.bulk_save_objects(recipients_records)
        session.commit()

        logger.info(f"Создано {len(recipients_records)} записей получателей для кампании {campaign_id}")

        # Загружаем созданные записи с их ID
        created_recipients = session.query(EmailCampaignRecipient).filter(
            EmailCampaignRecipient.campaign_id == campaign_id
        ).all()

        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "email": r.email,
                "full_name": r.full_name,
                "tracking_token": r.tracking_token,
                "ab_variant": r.ab_variant,
            }
            for r in created_recipients
        ]

    recipient_records = DatabaseManager.safe_execute(_create_recipients)

    # 4. Отправляем письма батчами
    email_sender = get_email_sender()
    sent_count = 0
    failed_count = 0

    # Обрабатываем получателей батчами
    batch_size = EMAIL_BATCH_SIZE  # Из config
    total_batches = (len(recipient_records) + batch_size - 1) // batch_size

    logger.info(f"Начинаем отправку {len(recipient_records)} писем батчами по {batch_size}")

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(recipient_records))
        batch = recipient_records[batch_start:batch_end]

        logger.info(f"Отправка батча {batch_idx + 1}/{total_batches} ({len(batch)} писем)")

        # Обновляем прогресс
        task.update_state(
            state='PROGRESS',
            meta={
                'current': sent_count + failed_count,
                'total': total_recipients,
                'status': f'Отправка батча {batch_idx + 1}/{total_batches}...',
                'campaign_id': campaign_id,
                'sent': sent_count,
                'failed': failed_count,
            }
        )

        # Отправляем каждое письмо в батче
        for recipient in batch:
            try:
                # Получаем пользователя для персонализации
                user_data = next(
                    (r for r in recipients if r["user_id"] == recipient["user_id"]),
                    None
                )

                if not user_data:
                    logger.warning(f"Не найдены данные для пользователя {recipient['user_id']}")
                    failed_count += 1
                    continue

                # Подготавливаем данные для персонализации
                personalization_data = EmailPersonalizer.prepare_user_data_from_dict(user_data)

                # Определяем тему и контент на основе A/B варианта
                subject = campaign_data["subject"]
                html_content = campaign_data["html_content"]

                if recipient["ab_variant"] == "B":
                    subject = campaign_data["ab_variant_b_subject"] or subject
                    html_content = campaign_data["ab_variant_b_content"] or html_content

                # Отправляем письмо
                result = await email_sender.send_email(
                    to_email=recipient["email"],
                    subject=subject,
                    html_content=html_content,
                    tracking_token=recipient["tracking_token"],
                    personalization_data=personalization_data,
                )

                # Обновляем статус получателя
                def _update_recipient_status(session):
                    db_recipient = session.query(EmailCampaignRecipient).filter(
                        EmailCampaignRecipient.id == recipient["id"]
                    ).first()

                    if db_recipient:
                        if result["success"]:
                            db_recipient.status = "sent"
                            db_recipient.sent_at = datetime.now(MOSCOW_TZ)
                        else:
                            db_recipient.status = "failed"
                            db_recipient.error_message = result.get("error", "Unknown error")

                        session.commit()

                DatabaseManager.safe_execute(_update_recipient_status)

                if result["success"]:
                    sent_count += 1
                    logger.debug(f"Письмо отправлено: {recipient['email']}")
                else:
                    failed_count += 1
                    logger.warning(f"Не удалось отправить письмо на {recipient['email']}: {result.get('error')}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка отправки письма на {recipient['email']}: {e}", exc_info=True)

                # Обновляем статус на failed
                def _update_failed(session):
                    db_recipient = session.query(EmailCampaignRecipient).filter(
                        EmailCampaignRecipient.id == recipient["id"]
                    ).first()
                    if db_recipient:
                        db_recipient.status = "failed"
                        db_recipient.error_message = str(e)[:500]
                        session.commit()

                try:
                    DatabaseManager.safe_execute(_update_failed)
                except Exception as db_error:
                    logger.error(f"Ошибка обновления статуса получателя: {db_error}")

        # Задержка между батчами (для соблюдения rate limits)
        if batch_idx < total_batches - 1:
            logger.debug(f"Пауза {EMAIL_BATCH_DELAY}с между батчами")
            await asyncio.sleep(EMAIL_BATCH_DELAY)

    # 5. Обновляем финальную статистику кампании
    def _finalize_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if campaign:
            campaign.status = "sent"
            campaign.sent_count = sent_count
            campaign.failed_count = failed_count
            campaign.delivered_count = sent_count  # Будет обновлено позже на основе bounce events
            campaign.sent_at = datetime.now(MOSCOW_TZ)
            session.commit()

    DatabaseManager.safe_execute(_finalize_campaign)

    duration = (datetime.now() - start_time).total_seconds()

    logger.info(
        f"Кампания {campaign_id} завершена: "
        f"отправлено={sent_count}, провалено={failed_count}, "
        f"время={duration:.2f}с"
    )

    return {
        "campaign_id": campaign_id,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "status": "sent",
        "duration_seconds": duration,
    }


# ===================================
# Утилиты для EmailPersonalizer
# ===================================


# Расширяем EmailPersonalizer для работы с dict вместо ORM объектов
def prepare_user_data_from_dict(user_dict: Dict) -> Dict:
    """
    Подготавливает данные пользователя для персонализации из словаря.

    Args:
        user_dict: Словарь с данными пользователя

    Returns:
        Dict с данными для подстановки в шаблон
    """
    full_name = user_dict.get("full_name") or ""
    name_parts = full_name.split()
    first_name = name_parts[0] if name_parts else "Пользователь"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

    reg_date = user_dict.get("reg_date")
    first_join_time = user_dict.get("first_join_time")
    successful_bookings = user_dict.get("successful_bookings", 0)

    # Преобразуем first_join_time в timezone-aware datetime если нужно
    is_new = False
    if first_join_time:
        # Если это naive datetime (без timezone), добавляем MOSCOW_TZ
        if first_join_time.tzinfo is None:
            first_join_time_aware = MOSCOW_TZ.localize(first_join_time)
        else:
            first_join_time_aware = first_join_time

        # Теперь можем безопасно вычитать
        is_new = (datetime.now(MOSCOW_TZ) - first_join_time_aware).days <= 7

    return {
        # Основные данные
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name or "Уважаемый пользователь",
        "email": user_dict.get("email", ""),
        "phone": user_dict.get("phone", ""),
        "username": user_dict.get("username", ""),

        # Статистика
        "successful_bookings": successful_bookings,
        "invited_count": user_dict.get("invited_count", 0),

        # Статус
        "is_vip": successful_bookings >= 10,
        "is_new": is_new,

        # Даты
        "reg_date": reg_date.strftime("%d.%m.%Y") if reg_date else "",
        "first_join_date": first_join_time.strftime("%d.%m.%Y") if first_join_time else "",
    }


# Добавляем метод в EmailPersonalizer
EmailPersonalizer.prepare_user_data_from_dict = staticmethod(prepare_user_data_from_dict)


# ===================================
# Задача для отложенной отправки
# ===================================


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name='tasks.email_tasks.check_scheduled_campaigns_task',
    max_retries=3,
)
def check_scheduled_campaigns_task(self):
    """
    Периодическая задача для проверки и запуска запланированных кампаний.

    Запускается по расписанию (например, каждые 5 минут).
    Находит кампании со статусом "scheduled" и временем отправки <= now,
    и запускает для них задачу send_email_campaign_task.
    """

    def _find_scheduled(session):
        now = datetime.now(MOSCOW_TZ)

        scheduled_campaigns = session.query(EmailCampaign).filter(
            EmailCampaign.status == "scheduled",
            EmailCampaign.scheduled_at <= now
        ).all()

        return [c.id for c in scheduled_campaigns]

    try:
        campaign_ids = DatabaseManager.safe_execute(_find_scheduled)

        if campaign_ids:
            logger.info(f"Найдено {len(campaign_ids)} запланированных кампаний для отправки")

            for campaign_id in campaign_ids:
                # Запускаем задачу отправки для каждой кампании
                send_email_campaign_task.delay(campaign_id)
                logger.info(f"Запущена отправка запланированной кампании {campaign_id}")

            return {"scheduled_campaigns_count": len(campaign_ids), "campaign_ids": campaign_ids}
        else:
            logger.debug("Нет запланированных кампаний для отправки")
            return {"scheduled_campaigns_count": 0, "campaign_ids": []}

    except Exception as e:
        logger.error(f"Ошибка в check_scheduled_campaigns_task: {e}", exc_info=True)
        raise self.retry(exc=e)
