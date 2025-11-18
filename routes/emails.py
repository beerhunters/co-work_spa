"""
API эндпоинты для управления email кампаниями
"""

from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import Response, RedirectResponse
from sqlalchemy import func, desc, Integer
from sqlalchemy.orm import Session
import json

from models.models import (
    EmailCampaign,
    EmailCampaignRecipient,
    EmailTemplate,
    EmailTracking,
    User,
    DatabaseManager,
    Permission,
)
from dependencies import verify_token_with_permissions, CachedAdmin
from schemas.email_schemas import (
    EmailCampaignCreate,
    EmailCampaignUpdate,
    EmailCampaignResponse,
    EmailCampaignListResponse,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    EmailSendRequest,
    EmailTestRequest,
    EmailRecipientResponse,
    EmailCampaignAnalytics,
    EmailSegmentPreview,
    PaginatedEmailCampaigns,
)
from utils.email_sender import EmailSender, EmailPersonalizer, get_email_sender
from utils.logger import get_logger
from config import MOSCOW_TZ

logger = get_logger(__name__)
router = APIRouter(prefix="/emails", tags=["emails"])


# ===================================
# Утилиты для сегментации
# ===================================


def get_users_by_segment(session: Session, segment_type: str, segment_params: Optional[Dict] = None) -> List[User]:
    """
    Получение пользователей по типу сегмента.

    Поддерживаемые сегменты:
    - all: все пользователи
    - active: пользователи с успешными бронированиями
    - new_users: зарегистрированы за последние N дней
    - vip: пользователи с N+ успешными бронированиями
    - inactive: нет бронирований
    """
    from datetime import timedelta

    params = segment_params or {}

    # Базовый запрос - исключаем забаненных и пользователей без email
    query = session.query(User).filter(
        User.is_banned == False,
        User.email.isnot(None),
        User.email != ""
    )

    if segment_type == "all":
        pass  # Все пользователи с email

    elif segment_type == "active":
        # Пользователи с хотя бы одним успешным бронированием
        query = query.filter(User.successful_bookings > 0)

    elif segment_type == "new_users":
        days = params.get("days", 7)
        cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=days)
        query = query.filter(User.reg_date >= cutoff_date)

    elif segment_type == "vip":
        min_bookings = params.get("min_bookings", 10)
        query = query.filter(User.successful_bookings >= min_bookings)

    elif segment_type == "inactive":
        # Нет бронирований
        query = query.filter(User.successful_bookings == 0)

    else:
        raise ValueError(f"Неизвестный тип сегмента: {segment_type}")

    return query.all()


def get_users_by_ids(session: Session, user_ids: List[int]) -> List[User]:
    """Получение пользователей по списку ID с валидацией email"""
    return session.query(User).filter(
        User.id.in_(user_ids),
        User.is_banned == False,
        User.email.isnot(None),
        User.email != ""
    ).all()


# ===================================
# Email кампании - CRUD
# ===================================


@router.get("", response_model=PaginatedEmailCampaigns)
async def get_campaigns(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    search: Optional[str] = Query(None, description="Поиск по названию/теме"),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение списка email кампаний с фильтрацией и пагинацией."""

    def _get_campaigns(session):
        query = session.query(EmailCampaign)

        # Фильтры
        if status:
            query = query.filter(EmailCampaign.status == status)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (EmailCampaign.name.like(search_pattern)) |
                (EmailCampaign.subject.like(search_pattern))
            )

        # Подсчет общего количества
        total = query.count()

        # Получение кампаний
        campaigns = query.order_by(desc(EmailCampaign.created_at)).offset(offset).limit(limit).all()

        items = [
            EmailCampaignListResponse(
                id=c.id,
                name=c.name,
                subject=c.subject,
                status=c.status,
                recipient_type=c.recipient_type,
                total_count=c.total_count,
                sent_count=c.sent_count,
                opened_count=c.opened_count,
                clicked_count=c.clicked_count,
                created_at=c.created_at,
                sent_at=c.sent_at,
            )
            for c in campaigns
        ]

        return {"items": items, "total": total, "limit": limit, "offset": offset}

    try:
        return DatabaseManager.safe_execute(_get_campaigns)
    except Exception as e:
        logger.error(f"Ошибка получения кампаний: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения кампаний")


@router.get("/{campaign_id}", response_model=EmailCampaignResponse)
async def get_campaign(
    campaign_id: int,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение детальной информации о кампании."""

    def _get_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")

        return EmailCampaignResponse(
            id=campaign.id,
            name=campaign.name,
            subject=campaign.subject,
            html_content=campaign.html_content,
            unlayer_design=campaign.unlayer_design,
            recipient_type=campaign.recipient_type,
            recipient_ids=campaign.recipient_ids,
            segment_type=campaign.segment_type,
            segment_params=campaign.segment_params,
            status=campaign.status,
            scheduled_at=campaign.scheduled_at,
            total_count=campaign.total_count,
            sent_count=campaign.sent_count,
            delivered_count=campaign.delivered_count,
            opened_count=campaign.opened_count,
            clicked_count=campaign.clicked_count,
            failed_count=campaign.failed_count,
            bounced_count=campaign.bounced_count,
            is_ab_test=campaign.is_ab_test,
            ab_test_percentage=campaign.ab_test_percentage,
            ab_variant_b_subject=campaign.ab_variant_b_subject,
            ab_variant_b_content=campaign.ab_variant_b_content,
            created_at=campaign.created_at,
            sent_at=campaign.sent_at,
            created_by=campaign.created_by,
        )

    try:
        return DatabaseManager.safe_execute(_get_campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения кампании")


@router.post("", response_model=EmailCampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: EmailCampaignCreate,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.CREATE_EMAIL_CAMPAIGNS])),
):
    """Создание новой email кампании (черновик)."""

    def _create_campaign(session):
        # Валидация получателей
        if campaign_data.recipient_type == "selected":
            if not campaign_data.recipient_ids or len(campaign_data.recipient_ids) == 0:
                raise HTTPException(status_code=400, detail="Для типа 'selected' необходимо указать recipient_ids")

            # Проверяем что пользователи существуют и имеют email
            users = get_users_by_ids(session, campaign_data.recipient_ids)
            if len(users) == 0:
                raise HTTPException(status_code=400, detail="Не найдено пользователей с валидными email адресами")

        elif campaign_data.recipient_type == "segment":
            if not campaign_data.segment_type:
                raise HTTPException(status_code=400, detail="Для типа 'segment' необходимо указать segment_type")

            # Проверяем что сегмент возвращает пользователей
            segment_params = json.loads(campaign_data.segment_params) if campaign_data.segment_params else {}
            users = get_users_by_segment(session, campaign_data.segment_type, segment_params)
            if len(users) == 0:
                raise HTTPException(status_code=400, detail="Сегмент не содержит пользователей с email")

        elif campaign_data.recipient_type == "custom":
            if not campaign_data.custom_emails or len(campaign_data.custom_emails) == 0:
                raise HTTPException(status_code=400, detail="Для типа 'custom' необходимо указать custom_emails")

            # Для custom emails users будет пустым список, т.к. получатели не из базы
            users = []

        else:  # all
            users = get_users_by_segment(session, "all")
            if len(users) == 0:
                raise HTTPException(status_code=400, detail="Нет пользователей с email адресами")

        # Создаем кампанию
        # Для custom emails сохраняем как строку через запятую
        custom_emails_str = None
        if campaign_data.custom_emails:
            custom_emails_str = ",".join(campaign_data.custom_emails)

        # Подсчет получателей: либо users из базы, либо custom emails
        total_count = len(campaign_data.custom_emails) if campaign_data.recipient_type == "custom" else len(users)

        campaign = EmailCampaign(
            name=campaign_data.name,
            subject=campaign_data.subject,
            html_content=campaign_data.html_content,
            unlayer_design=campaign_data.unlayer_design,
            recipient_type=campaign_data.recipient_type,
            recipient_ids=json.dumps(campaign_data.recipient_ids) if campaign_data.recipient_ids else None,
            segment_type=campaign_data.segment_type,
            segment_params=json.dumps(campaign_data.segment_params) if campaign_data.segment_params else None,
            custom_emails=custom_emails_str,
            is_ab_test=campaign_data.is_ab_test,
            ab_test_percentage=campaign_data.ab_test_percentage,
            ab_variant_b_subject=campaign_data.ab_variant_b_subject,
            ab_variant_b_content=campaign_data.ab_variant_b_content,
            status="draft",
            total_count=total_count,
            created_by=current_admin.login,
            created_at=datetime.now(MOSCOW_TZ),
        )

        session.add(campaign)
        session.commit()
        session.refresh(campaign)

        logger.info(f"Создана email кампания {campaign.id} '{campaign.name}' администратором {current_admin.login}")

        return EmailCampaignResponse.from_orm(campaign)

    try:
        return DatabaseManager.safe_execute(_create_campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания кампании: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка создания кампании")


@router.put("/{campaign_id}", response_model=EmailCampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: EmailCampaignUpdate,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_EMAIL_CAMPAIGNS])),
):
    """Обновление email кампании (только для черновиков)."""

    def _update_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")

        # Можно редактировать только черновики
        if campaign.status not in ["draft", "scheduled"]:
            raise HTTPException(status_code=400, detail="Можно редактировать только черновики или запланированные кампании")

        # Обновляем поля
        update_data = campaign_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(campaign, field, value)

        campaign.updated_at = datetime.now(MOSCOW_TZ)
        session.commit()
        session.refresh(campaign)

        logger.info(f"Обновлена email кампания {campaign_id}")

        return EmailCampaignResponse.from_orm(campaign)

    try:
        return DatabaseManager.safe_execute(_update_campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка обновления кампании")


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: int,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.DELETE_EMAIL_CAMPAIGNS])),
):
    """Удаление email кампании (только черновиков)."""

    def _delete_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")

        # Можно удалять только черновики
        if campaign.status not in ["draft"]:
            raise HTTPException(status_code=400, detail="Можно удалять только черновики")

        session.delete(campaign)
        session.commit()

        logger.info(f"Удалена email кампания {campaign_id}")

        return {"success": True, "message": "Кампания удалена"}

    try:
        return DatabaseManager.safe_execute(_delete_campaign)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка удаления кампании")


@router.post("/clear-history")
async def clear_campaigns_history(
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу: 'sent', 'failed', 'all'"),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.DELETE_EMAIL_CAMPAIGNS])),
):
    """
    Массовое удаление кампаний (очистка истории).

    По умолчанию удаляет только отправленные (sent) и провалившиеся (failed) кампании.
    Не удаляет черновики, запланированные и активные рассылки.
    """

    def _clear_history(session):
        query = session.query(EmailCampaign)

        # Определяем какие кампании удалять
        if status_filter == "all":
            # Удаляем все кроме активных (sending)
            query = query.filter(EmailCampaign.status.in_(["draft", "scheduled", "sent", "failed"]))
        elif status_filter == "failed":
            # Только провалившиеся
            query = query.filter(EmailCampaign.status == "failed")
        else:  # По умолчанию 'sent' и 'failed'
            # Только отправленные и провалившиеся
            query = query.filter(EmailCampaign.status.in_(["sent", "failed"]))

        campaigns = query.all()
        count = len(campaigns)

        if count == 0:
            return {"success": True, "deleted_count": 0, "message": "Нет кампаний для удаления"}

        # Удаляем кампании (cascade удалит связанные записи)
        for campaign in campaigns:
            session.delete(campaign)

        session.commit()

        logger.info(f"Очищена история email кампаний: удалено {count} кампаний администратором {current_admin.username}")

        return {
            "success": True,
            "deleted_count": count,
            "message": f"Удалено кампаний: {count}"
        }

    try:
        return DatabaseManager.safe_execute(_clear_history)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка очистки истории кампаний: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка очистки истории")


# ===================================
# Отправка и планирование
# ===================================


@router.post("/{campaign_id}/send")
async def send_campaign(
    campaign_id: int,
    send_request: EmailSendRequest,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.SEND_EMAIL_CAMPAIGNS])),
):
    """
    Отправка или планирование email кампании.
    Создает фоновую задачу через Celery.
    """

    def _prepare_send(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")

        # Проверка статуса
        if campaign.status not in ["draft", "scheduled"]:
            raise HTTPException(status_code=400, detail="Кампания уже отправлена или отправляется")

        # Получение списка получателей
        if campaign.recipient_type == "custom":
            # Для custom emails парсим список адресов
            if not campaign.custom_emails:
                raise HTTPException(status_code=400, detail="Не указаны email адреса для отправки")

            emails = [email.strip() for email in campaign.custom_emails.split(",") if email.strip()]
            if len(emails) == 0:
                raise HTTPException(status_code=400, detail="Нет получателей для отправки")

            # Для custom emails users будет пустым, но считаем количество
            users = []
            recipients_count = len(emails)

        elif campaign.recipient_type == "selected":
            recipient_ids = json.loads(campaign.recipient_ids) if campaign.recipient_ids else []
            users = get_users_by_ids(session, recipient_ids)
            recipients_count = len(users)

            if recipients_count == 0:
                raise HTTPException(status_code=400, detail="Нет получателей для отправки")

        elif campaign.recipient_type == "segment":
            segment_params = json.loads(campaign.segment_params) if campaign.segment_params else {}
            users = get_users_by_segment(session, campaign.segment_type, segment_params)
            recipients_count = len(users)

            if recipients_count == 0:
                raise HTTPException(status_code=400, detail="Нет получателей для отправки")

        else:  # all
            users = get_users_by_segment(session, "all")
            recipients_count = len(users)

            if recipients_count == 0:
                raise HTTPException(status_code=400, detail="Нет получателей для отправки")

        # Обновляем статус
        if send_request.send_now:
            campaign.status = "sending"
            campaign.scheduled_at = None
        else:
            campaign.status = "scheduled"
            campaign.scheduled_at = send_request.scheduled_at

        campaign.total_count = recipients_count
        session.commit()

        return {"campaign": campaign, "users": users, "recipients_count": recipients_count}

    try:
        result = DatabaseManager.safe_execute(_prepare_send)
        campaign = result["campaign"]
        users = result["users"]
        recipients_count = result["recipients_count"]

        if send_request.send_now:
            # Запускаем фоновую задачу отправки
            from tasks.email_tasks import send_email_campaign_task

            task = send_email_campaign_task.delay(campaign_id)

            logger.info(f"Запущена отправка email кампании {campaign_id}, task_id={task.id}")

            return {
                "success": True,
                "message": f"Отправка кампании запущена. Будет отправлено {recipients_count} писем.",
                "task_id": task.id,
                "recipients_count": recipients_count,
            }
        else:
            logger.info(f"Email кампания {campaign_id} запланирована на {send_request.scheduled_at}")

            return {
                "success": True,
                "message": f"Кампания запланирована на {send_request.scheduled_at.strftime('%d.%m.%Y %H:%M')}",
                "scheduled_at": send_request.scheduled_at,
                "recipients_count": recipients_count,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка отправки кампании")


@router.post("/{campaign_id}/test")
async def send_test_email(
    campaign_id: int,
    test_request: EmailTestRequest,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_EMAIL_TEMPLATES])),
):
    """Отправка тестового письма на указанный email."""

    def _get_campaign(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")
        return campaign

    try:
        campaign = DatabaseManager.safe_execute(_get_campaign)

        # Отправляем тестовое письмо
        email_sender = get_email_sender()

        result = await email_sender.send_email(
            to_email=test_request.test_email,
            subject=f"[ТЕСТ] {campaign.subject}",
            html_content=campaign.html_content,
            tracking_token=None,  # Без трекинга для теста
            personalization_data={
                "first_name": "Тестовое Имя",
                "email": test_request.test_email,
                "full_name": "Тестовое Имя Фамилия",
            }
        )

        if result["success"]:
            logger.info(f"Отправлено тестовое письмо для кампании {campaign_id} на {test_request.test_email}")
            return {"success": True, "message": f"Тестовое письмо отправлено на {test_request.test_email}"}
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка отправки: {result['error']}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки тестового письма: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка отправки тестового письма")


# ===================================
# Трекинг открытий и кликов
# ===================================


@router.get("/track/{tracking_token}/open.png")
async def track_open(tracking_token: str):
    """
    Tracking pixel для отслеживания открытий писем.
    Возвращает 1x1 прозрачный PNG.
    """

    def _track_open(session):
        # Находим получателя по tracking token
        recipient = session.query(EmailCampaignRecipient).filter(
            EmailCampaignRecipient.tracking_token == tracking_token
        ).first()

        if recipient and not recipient.opened_at:
            # Первое открытие
            recipient.opened_at = datetime.now(MOSCOW_TZ)
            recipient.status = "opened"

            # Обновляем счетчик в кампании
            campaign = session.query(EmailCampaign).filter(
                EmailCampaign.id == recipient.campaign_id
            ).first()
            if campaign:
                campaign.opened_count += 1

            # Записываем событие трекинга
            tracking_event = EmailTracking(
                campaign_id=recipient.campaign_id,
                recipient_id=recipient.id,
                event_type="open",
                created_at=datetime.now(MOSCOW_TZ),
            )
            session.add(tracking_event)

            session.commit()

            logger.info(f"Зафиксировано открытие письма: campaign={recipient.campaign_id}, recipient={recipient.id}")

    try:
        DatabaseManager.safe_execute(_track_open)
    except Exception as e:
        logger.error(f"Ошибка трекинга открытия для токена {tracking_token}: {e}")

    # Всегда возвращаем tracking pixel, даже при ошибках
    pixel_bytes = EmailSender.generate_tracking_pixel()
    return Response(content=pixel_bytes, media_type="image/png")


@router.get("/track/{tracking_token}/click")
async def track_click(tracking_token: str, url: str = Query(...)):
    """
    Трекинг кликов по ссылкам в письме.
    Редиректит на оригинальный URL после записи клика.
    """

    def _track_click(session):
        recipient = session.query(EmailCampaignRecipient).filter(
            EmailCampaignRecipient.tracking_token == tracking_token
        ).first()

        if recipient:
            # Обновляем статистику получателя
            if not recipient.first_click_at:
                recipient.first_click_at = datetime.now(MOSCOW_TZ)

                # Обновляем счетчик уникальных кликов в кампании
                campaign = session.query(EmailCampaign).filter(
                    EmailCampaign.id == recipient.campaign_id
                ).first()
                if campaign:
                    campaign.clicked_count += 1

            recipient.clicks_count += 1

            # Записываем событие трекинга
            tracking_event = EmailTracking(
                campaign_id=recipient.campaign_id,
                recipient_id=recipient.id,
                event_type="click",
                link_url=url,
                created_at=datetime.now(MOSCOW_TZ),
            )
            session.add(tracking_event)

            session.commit()

            logger.info(f"Зафиксирован клик: campaign={recipient.campaign_id}, recipient={recipient.id}, url={url}")

    try:
        DatabaseManager.safe_execute(_track_click)
    except Exception as e:
        logger.error(f"Ошибка трекинга клика для токена {tracking_token}: {e}")

    # Редиректим на оригинальный URL
    return RedirectResponse(url=url, status_code=302)


# ===================================
# Аналитика и статистика
# ===================================


@router.get("/{campaign_id}/analytics", response_model=EmailCampaignAnalytics)
async def get_campaign_analytics(
    campaign_id: int,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение детальной аналитики по кампании."""

    def _get_analytics(session):
        campaign = session.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Кампания не найдена")

        # Расчет метрик
        delivery_rate = (campaign.delivered_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0
        open_rate = (campaign.opened_count / campaign.delivered_count * 100) if campaign.delivered_count > 0 else 0
        click_rate = (campaign.clicked_count / campaign.delivered_count * 100) if campaign.delivered_count > 0 else 0
        bounce_rate = (campaign.bounced_count / campaign.sent_count * 100) if campaign.sent_count > 0 else 0

        # Топ кликнутых ссылок
        top_links_query = session.query(
            EmailTracking.link_url,
            func.count(EmailTracking.id).label("clicks")
        ).filter(
            EmailTracking.campaign_id == campaign_id,
            EmailTracking.event_type == "click",
            EmailTracking.link_url.isnot(None)
        ).group_by(EmailTracking.link_url).order_by(desc("clicks")).limit(10).all()

        top_links = [{"url": link, "clicks": clicks} for link, clicks in top_links_query]

        # Среднее время до открытия (в минутах)
        avg_time_query = session.query(
            func.avg(
                func.julianday(EmailCampaignRecipient.opened_at) -
                func.julianday(EmailCampaignRecipient.sent_at)
            ) * 24 * 60  # Конвертируем дни в минуты
        ).filter(
            EmailCampaignRecipient.campaign_id == campaign_id,
            EmailCampaignRecipient.opened_at.isnot(None),
            EmailCampaignRecipient.sent_at.isnot(None)
        ).scalar()

        avg_time_to_open = round(avg_time_query, 2) if avg_time_query else None

        # Пиковый час открытий
        peak_hour_query = session.query(
            func.cast(func.strftime('%H', EmailCampaignRecipient.opened_at), Integer).label('hour'),
            func.count(EmailCampaignRecipient.id).label('opens')
        ).filter(
            EmailCampaignRecipient.campaign_id == campaign_id,
            EmailCampaignRecipient.opened_at.isnot(None)
        ).group_by('hour').order_by(desc('opens')).first()

        peak_open_hour = peak_hour_query[0] if peak_hour_query else None

        return EmailCampaignAnalytics(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_recipients=campaign.total_count,
            sent=campaign.sent_count,
            delivered=campaign.delivered_count,
            failed=campaign.failed_count,
            bounced=campaign.bounced_count,
            opened=campaign.opened_count,
            clicked=campaign.clicked_count,
            delivery_rate=round(delivery_rate, 2),
            open_rate=round(open_rate, 2),
            click_rate=round(click_rate, 2),
            bounce_rate=round(bounce_rate, 2),
            avg_time_to_open=avg_time_to_open,
            peak_open_hour=peak_open_hour,
            top_links=top_links,
        )

    try:
        return DatabaseManager.safe_execute(_get_analytics)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения аналитики для кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения аналитики")


@router.get("/{campaign_id}/recipients", response_model=List[EmailRecipientResponse])
async def get_campaign_recipients(
    campaign_id: int,
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение списка получателей кампании с их статистикой."""

    def _get_recipients(session):
        query = session.query(EmailCampaignRecipient).filter(
            EmailCampaignRecipient.campaign_id == campaign_id
        )

        if status:
            query = query.filter(EmailCampaignRecipient.status == status)

        recipients = query.order_by(desc(EmailCampaignRecipient.sent_at)).offset(offset).limit(limit).all()

        return [
            EmailRecipientResponse(
                id=r.id,
                campaign_id=r.campaign_id,
                user_id=r.user_id,
                email=r.email,
                full_name=r.full_name,
                status=r.status,
                error_message=r.error_message,
                sent_at=r.sent_at,
                opened_at=r.opened_at,
                first_click_at=r.first_click_at,
                clicks_count=r.clicks_count,
                ab_variant=r.ab_variant,
            )
            for r in recipients
        ]

    try:
        return DatabaseManager.safe_execute(_get_recipients)
    except Exception as e:
        logger.error(f"Ошибка получения получателей для кампании {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения получателей")


# ===================================
# Email шаблоны
# ===================================


@router.get("/templates", response_model=List[EmailTemplateResponse])
async def get_templates(
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение списка email шаблонов."""

    def _get_templates(session):
        query = session.query(EmailTemplate)

        if category:
            query = query.filter(EmailTemplate.category == category)

        if is_active is not None:
            query = query.filter(EmailTemplate.is_active == is_active)

        templates = query.order_by(desc(EmailTemplate.created_at)).all()

        return [EmailTemplateResponse.from_orm(t) for t in templates]

    try:
        return DatabaseManager.safe_execute(_get_templates)
    except Exception as e:
        logger.error(f"Ошибка получения шаблонов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения шаблонов")


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_template(
    template_id: int,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_EMAIL_CAMPAIGNS])),
):
    """Получение email шаблона по ID."""

    def _get_template(session):
        template = session.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        return EmailTemplateResponse.from_orm(template)

    try:
        return DatabaseManager.safe_execute(_get_template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения шаблона {template_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка получения шаблона")


@router.post("/templates", response_model=EmailTemplateResponse, status_code=201)
async def create_template(
    template_data: EmailTemplateCreate,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_EMAIL_TEMPLATES])),
):
    """Создание нового email шаблона."""

    def _create_template(session):
        template = EmailTemplate(
            name=template_data.name,
            description=template_data.description,
            category=template_data.category,
            unlayer_design=template_data.unlayer_design,
            html_content=template_data.html_content,
            thumbnail_url=template_data.thumbnail_url,
            created_by=current_admin.login,
            created_at=datetime.now(MOSCOW_TZ),
            updated_at=datetime.now(MOSCOW_TZ),
        )

        session.add(template)
        session.commit()
        session.refresh(template)

        logger.info(f"Создан email шаблон {template.id} '{template.name}' администратором {current_admin.login}")

        return EmailTemplateResponse.from_orm(template)

    try:
        return DatabaseManager.safe_execute(_create_template)
    except Exception as e:
        logger.error(f"Ошибка создания шаблона: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка создания шаблона")


@router.put("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    template_id: int,
    template_data: EmailTemplateUpdate,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_EMAIL_TEMPLATES])),
):
    """Обновление email шаблона."""

    def _update_template(session):
        template = session.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        update_data = template_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)

        template.updated_at = datetime.now(MOSCOW_TZ)
        session.commit()
        session.refresh(template)

        logger.info(f"Обновлен email шаблон {template_id}")

        return EmailTemplateResponse.from_orm(template)

    try:
        return DatabaseManager.safe_execute(_update_template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления шаблона {template_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка обновления шаблона")


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_EMAIL_TEMPLATES])),
):
    """Удаление email шаблона."""

    def _delete_template(session):
        template = session.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Шаблон не найден")

        session.delete(template)
        session.commit()

        logger.info(f"Удален email шаблон {template_id}")

        return {"success": True, "message": "Шаблон удален"}

    try:
        return DatabaseManager.safe_execute(_delete_template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления шаблона {template_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка удаления шаблона")


# ===================================
# Утилиты
# ===================================


@router.post("/segments/preview", response_model=EmailSegmentPreview)
async def preview_segment(
    segment_type: str = Body(...),
    segment_params: Optional[Dict] = Body(None),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_USERS])),
):
    """Предпросмотр сегмента: сколько пользователей попадет в рассылку."""

    def _preview_segment(session):
        try:
            users = get_users_by_segment(session, segment_type, segment_params)
            count = len(users)

            return EmailSegmentPreview(
                segment_type=segment_type,
                segment_params=segment_params,
                estimated_count=count,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        return DatabaseManager.safe_execute(_preview_segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка предпросмотра сегмента {segment_type}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка предпросмотра сегмента")


@router.post("/templates/seed")
async def seed_email_templates(
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_EMAIL_TEMPLATES])),
):
    """Создание готовых email шаблонов в базе данных."""

    try:
        from utils.seed_email_templates import EMAIL_TEMPLATES

        def _seed_operation(session):
            created_count = 0
            updated_count = 0

            for template_data in EMAIL_TEMPLATES:
                # Проверяем, существует ли шаблон с таким именем
                existing_template = session.query(EmailTemplate).filter(
                    EmailTemplate.name == template_data["name"]
                ).first()

                if existing_template:
                    # Обновляем существующий шаблон
                    existing_template.description = template_data["description"]
                    existing_template.subject = template_data["subject"]
                    existing_template.html_content = template_data["html_content"]
                    existing_template.category = template_data["category"]
                    existing_template.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.info(f"Updated template: {template_data['name']}")
                else:
                    # Создаем новый шаблон
                    new_template = EmailTemplate(
                        name=template_data["name"],
                        description=template_data["description"],
                        subject=template_data["subject"],
                        html_content=template_data["html_content"],
                        unlayer_design=None,
                        category=template_data["category"],
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(new_template)
                    created_count += 1
                    logger.info(f"Created template: {template_data['name']}")

            session.commit()
            return created_count, updated_count

        created, updated = DatabaseManager.safe_execute(_seed_operation)

        logger.info(f"Email templates seeding completed. Created: {created}, Updated: {updated}")

        return {
            "success": True,
            "message": "Email templates seeded successfully",
            "created": created,
            "updated": updated,
            "total": created + updated
        }

    except Exception as e:
        logger.error(f"Error seeding email templates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка создания шаблонов: {str(e)}")
