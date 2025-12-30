from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio

from models.models import DatabaseManager, OfficeSubscription, User, Permission, MOSCOW_TZ
from schemas.office_subscription_schemas import (
    OfficeSubscriptionCreate,
    OfficeSubscriptionUpdate,
    OfficeSubscriptionResponse,
    NotifySubscribersRequest
)
from dependencies import verify_token_with_permissions, CachedAdmin
from utils.logger import get_logger
from utils.bot_instance import get_bot

router = APIRouter(prefix="/office-subscriptions", tags=["Office Subscriptions"])
logger = get_logger(__name__)


@router.get("/", response_model=List[OfficeSubscriptionResponse])
async def get_all_subscriptions(
    office_size: Optional[int] = None,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_OFFICE_SUBSCRIPTIONS]))
):
    """
    Получить все подписки на офисы.

    Args:
        office_size: Фильтр по размеру офиса (1, 2, 4, 6). Если None - все подписки.
    """
    def _get_subscriptions(session: Session):
        query = session.query(OfficeSubscription).order_by(OfficeSubscription.created_at.desc())

        # Фильтрация по размеру офиса
        if office_size == 1:
            query = query.filter(OfficeSubscription.office_1 == True)
        elif office_size == 2:
            query = query.filter(OfficeSubscription.office_2 == True)
        elif office_size == 4:
            query = query.filter(OfficeSubscription.office_4 == True)
        elif office_size == 6:
            query = query.filter(OfficeSubscription.office_6 == True)
        elif office_size is not None:
            raise ValueError(f"Invalid office_size: {office_size}. Must be 1, 2, 4, or 6.")

        return query.all()

    try:
        subscriptions = DatabaseManager.safe_execute(_get_subscriptions)
        return subscriptions
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching subscriptions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка получения подписок")


@router.get("/{subscription_id}", response_model=OfficeSubscriptionResponse)
async def get_subscription(
    subscription_id: int,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_OFFICE_SUBSCRIPTIONS]))
):
    """Получить подписку по ID."""
    def _get_subscription(session: Session):
        subscription = session.query(OfficeSubscription).filter(OfficeSubscription.id == subscription_id).first()
        if not subscription:
            raise ValueError("Подписка не найдена")
        return subscription

    try:
        subscription = DatabaseManager.safe_execute(_get_subscription)
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching subscription {subscription_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка получения подписки")


@router.post("/user/{telegram_id}", response_model=OfficeSubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription_for_user(
    telegram_id: int,
    subscription_data: OfficeSubscriptionCreate
):
    """
    Создать подписку для пользователя (вызывается из бота).

    Проверяет, что выбран хотя бы один размер офиса.
    """
    if not subscription_data.has_selection():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо выбрать хотя бы один размер офиса"
        )

    def _create_subscription(session: Session):
        # Находим пользователя
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        # Проверяем, нет ли уже подписки
        existing = session.query(OfficeSubscription).filter(
            OfficeSubscription.user_id == user.id
        ).first()

        if existing:
            raise ValueError("У пользователя уже есть активная подписка")

        # Создаем подписку
        subscription = OfficeSubscription(
            user_id=user.id,
            telegram_id=user.telegram_id,
            full_name=user.full_name,
            username=user.username,
            office_1=subscription_data.office_1,
            office_2=subscription_data.office_2,
            office_4=subscription_data.office_4,
            office_6=subscription_data.office_6
        )

        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return subscription

    try:
        subscription = DatabaseManager.safe_execute(_create_subscription)
        logger.info(f"Created office subscription for telegram_id={telegram_id}")
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating subscription for telegram_id={telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка создания подписки"
        )


@router.get("/user/{telegram_id}", response_model=OfficeSubscriptionResponse)
async def get_user_subscription(telegram_id: int):
    """Получить подписку пользователя по telegram_id."""
    def _get_subscription(session: Session):
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        subscription = session.query(OfficeSubscription).filter(
            OfficeSubscription.user_id == user.id
        ).first()

        if not subscription:
            raise ValueError("Подписка не найдена")

        return subscription

    try:
        subscription = DatabaseManager.safe_execute(_get_subscription)
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching subscription for telegram_id={telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения подписки"
        )


@router.delete("/user/{telegram_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_subscription(telegram_id: int):
    """Удалить подписку пользователя по telegram_id (вызывается из бота)."""
    def _delete_subscription(session: Session):
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        subscription = session.query(OfficeSubscription).filter(
            OfficeSubscription.user_id == user.id
        ).first()

        if not subscription:
            raise ValueError("Подписка не найдена")

        session.delete(subscription)
        session.commit()
        return True

    try:
        DatabaseManager.safe_execute(_delete_subscription)
        logger.info(f"Deleted office subscription for telegram_id={telegram_id}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting subscription for telegram_id={telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка удаления подписки"
        )


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_OFFICE_SUBSCRIPTIONS]))
):
    """Удалить подписку (администратор)."""
    def _delete_subscription(session: Session):
        subscription = session.query(OfficeSubscription).filter(OfficeSubscription.id == subscription_id).first()
        if not subscription:
            raise ValueError("Подписка не найдена")

        session.delete(subscription)
        session.commit()
        return True

    try:
        DatabaseManager.safe_execute(_delete_subscription)
        logger.info(f"Admin {current_admin.login} deleted subscription {subscription_id}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting subscription {subscription_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Ошибка удаления подписки")


@router.post("/notify", status_code=status.HTTP_200_OK)
async def notify_subscribers(
    request: NotifySubscribersRequest,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.SEND_TELEGRAM_NEWSLETTERS]))
):
    """
    Отправить уведомление подписчикам.

    Args:
        request: Содержит message (текст) и office_size (фильтр, опционально)
    """
    def _get_subscribers(session: Session):
        query = session.query(OfficeSubscription)

        # Фильтрация по размеру офиса
        if request.office_size == 1:
            query = query.filter(OfficeSubscription.office_1 == True)
        elif request.office_size == 2:
            query = query.filter(OfficeSubscription.office_2 == True)
        elif request.office_size == 4:
            query = query.filter(OfficeSubscription.office_4 == True)
        elif request.office_size == 6:
            query = query.filter(OfficeSubscription.office_6 == True)
        elif request.office_size is not None:
            raise ValueError(f"Invalid office_size: {request.office_size}")

        return query.all()

    try:
        subscriptions = DatabaseManager.safe_execute(_get_subscribers)

        if not subscriptions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Нет подписчиков с указанным фильтром"
            )

        bot = get_bot()
        success_count = 0
        fail_count = 0

        # Отправка уведомлений с rate limiting
        for subscription in subscriptions:
            try:
                await bot.send_message(subscription.telegram_id, request.message)
                success_count += 1
                await asyncio.sleep(0.05)  # 50ms между сообщениями
            except Exception as e:
                logger.error(f"Failed to send notification to {subscription.telegram_id}: {e}")
                fail_count += 1

        logger.info(
            f"Admin {current_admin.login} sent notifications: "
            f"{success_count} successful, {fail_count} failed "
            f"(filter: office_size={request.office_size})"
        )

        return {
            "success": True,
            "sent": success_count,
            "failed": fail_count,
            "total_subscribers": len(subscriptions)
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отправки уведомлений"
        )
