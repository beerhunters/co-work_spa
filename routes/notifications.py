# ================== routes/notifications.py ==================
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from models.models import Notification
from dependencies import get_db, verify_token
from config import MOSCOW_TZ
from schemas.notification_schemas import NotificationBase
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])
# router = APIRouter(tags=["notifications"])


@router.get("", response_model=List[NotificationBase])
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    status: Optional[str] = None,  # read, unread
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение всех уведомлений с пагинацией и фильтрацией."""
    query = db.query(Notification).order_by(Notification.created_at.desc())

    if status == "read":
        query = query.filter(Notification.is_read == True)
    elif status == "unread":
        query = query.filter(Notification.is_read == False)

    notifications = query.offset((page - 1) * per_page).limit(per_page).all()
    return notifications


@router.get("/check_new")
async def check_new_notifications(
    since_id: int = Query(0),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Проверка новых уведомлений с определенного ID."""
    query = db.query(Notification).order_by(Notification.created_at.desc())

    if since_id > 0:
        query = query.filter(Notification.id > since_id)

    notifications = query.limit(5).all()

    return {
        "has_new": len(notifications) > 0,
        "recent_notifications": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "message": n.message,
                "booking_id": n.booking_id,
                "ticket_id": n.ticket_id,
                "target_url": n.target_url,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


@router.post("/mark_read/{notification_id}")
async def mark_notification_read(
    notification_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Пометить уведомление как прочитанное."""
    notification = (
        db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    logger.info(f"Уведомление #{notification_id} помечено как прочитанное")
    return {"message": "Notification marked as read"}


@router.post("/mark_all_read")
async def mark_all_notifications_read(
    db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Пометить все уведомления как прочитанные."""
    try:
        updated_count = (
            db.query(Notification).filter(Notification.is_read == False).count()
        )
        db.query(Notification).update({"is_read": True})
        db.commit()

        logger.info(f"Помечено как прочитанное {updated_count} уведомлений")
        return {
            "message": "All notifications marked as read",
            "updated_count": updated_count,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при пометке всех уведомлений: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to mark all notifications as read"
        )


@router.post("/create")
async def create_notification(
    notification_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создать уведомление в БД (для отображения в админке)"""
    from models.models import User

    user_id = notification_data.get("user_id")
    message = notification_data.get("message")
    target_url = notification_data.get("target_url")
    booking_id = notification_data.get("booking_id")
    ticket_id = notification_data.get("ticket_id")

    # Проверяем существование пользователя
    user = None
    if user_id:
        user = db.query(User).get(user_id)
        if not user:
            # Если передан user_id как telegram_id, пытаемся найти по нему
            user = db.query(User).filter(User.telegram_id == user_id).first()
            if user:
                user_id = user.id

    # Создаем уведомление в БД
    notification = Notification(
        user_id=user_id,
        message=message,
        target_url=target_url,
        booking_id=booking_id,
        ticket_id=ticket_id,
        created_at=datetime.now(MOSCOW_TZ),
        is_read=False,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return {
        "success": True,
        "notification_id": notification.id,
        "created_at": notification.created_at,
    }
