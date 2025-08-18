# ================== routes/newsletters.py ==================
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Query
from pathlib import Path
import time
import asyncio

from dependencies import verify_token, get_bot
from config import NEWSLETTER_PHOTOS_DIR, MOSCOW_TZ
from models.models import Newsletter, User, DatabaseManager
from schemas.newsletter_schemas import NewsletterResponse
from utils.logger import get_logger
from utils.external_api import send_telegram_notification, send_telegram_photo

logger = get_logger(__name__)
# router = APIRouter(prefix="/newsletters", tags=["newsletters"])
router = APIRouter(tags=["newsletters"])


@router.get("/newsletters")
async def get_newsletters(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_token),
):
    """Получение рассылок (для фронтенда)."""
    return await get_newsletter_history(limit, offset, _)


@router.post("/newsletters/send")
async def send_newsletter(
    message: str = Form(...),
    recipient_type: str = Form(...),
    user_ids: Optional[List[str]] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    _: str = Depends(verify_token),
):
    """Отправка рассылки пользователям через Telegram бота."""
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not available")

    # Валидация
    if not message.strip():
        raise HTTPException(
            status_code=400, detail="Текст сообщения не может быть пустым"
        )

    if len(message) > 4096:
        raise HTTPException(status_code=400, detail="Сообщение слишком длинное")

    if recipient_type not in ["all", "selected"]:
        raise HTTPException(status_code=400, detail="Неверный тип получателей")

    if recipient_type == "selected" and not user_ids:
        raise HTTPException(status_code=400, detail="Не выбраны получатели")

    # Валидация фотографий
    photo_paths = []
    if photos:
        if len(photos) > 10:
            raise HTTPException(
                status_code=400, detail="Превышено максимальное количество фотографий"
            )

        NEWSLETTER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

        for idx, photo in enumerate(photos):
            if photo.content_type and photo.content_type.startswith("image/"):
                timestamp = int(time.time())
                file_ext = Path(photo.filename).suffix if photo.filename else ".jpg"
                filename = f"newsletter_{timestamp}_{idx}{file_ext}"
                file_path = NEWSLETTER_PHOTOS_DIR / filename

                contents = await photo.read()
                with open(file_path, "wb") as f:
                    f.write(contents)

                photo_paths.append(str(file_path))

    # Получение получателей
    def _get_recipients(session):
        if recipient_type == "all":
            users = session.query(User).filter(User.telegram_id.isnot(None)).all()
        else:
            telegram_ids = [int(uid) for uid in user_ids if uid.isdigit()]
            users = session.query(User).filter(User.telegram_id.in_(telegram_ids)).all()

        return [
            {
                "telegram_id": user.telegram_id,
                "full_name": user.full_name or f"User {user.telegram_id}",
            }
            for user in users
        ]

    recipients = DatabaseManager.safe_execute(_get_recipients)

    if not recipients:
        raise HTTPException(status_code=400, detail="Нет получателей для рассылки")

    # Отправка сообщений
    success_count = 0
    failed_count = 0

    for recipient in recipients:
        try:
            if photo_paths:
                if len(photo_paths) == 1:
                    # Одно фото
                    with open(photo_paths[0], "rb") as photo:
                        await send_telegram_photo(
                            bot, recipient["telegram_id"], photo, message
                        )
                else:
                    # Несколько фото - отправляем как медиагруппу
                    from aiogram.types import InputMediaPhoto, FSInputFile

                    media_group = []
                    for photo_idx, photo_path in enumerate(photo_paths):
                        media = InputMediaPhoto(
                            media=FSInputFile(photo_path),
                            caption=message if photo_idx == 0 else None,
                            parse_mode="HTML" if photo_idx == 0 else None,
                        )
                        media_group.append(media)

                    await bot.send_media_group(
                        chat_id=recipient["telegram_id"], media=media_group
                    )
            else:
                # Только текст
                await send_telegram_notification(bot, recipient["telegram_id"], message)

            success_count += 1
            await asyncio.sleep(0.05)  # Небольшая задержка

        except Exception as e:
            failed_count += 1
            logger.error(
                f"Ошибка отправки пользователю {recipient['telegram_id']}: {e}"
            )

    # Определяем статус рассылки
    if success_count == len(recipients):
        status = "success"
    elif success_count == 0:
        status = "failed"
    else:
        status = "partial"

    # Сохраняем в БД
    def _save_newsletter(session):
        newsletter = Newsletter(
            message=message,
            recipient_type=recipient_type,
            recipient_ids=",".join([str(r["telegram_id"]) for r in recipients]),
            total_count=len(recipients),
            success_count=success_count,
            failed_count=failed_count,
            photo_count=len(photo_paths),
            status=status,
            created_at=datetime.now(MOSCOW_TZ),
        )
        session.add(newsletter)
        session.flush()

        return {
            "id": newsletter.id,
            "total_count": newsletter.total_count,
            "success_count": newsletter.success_count,
            "failed_count": newsletter.failed_count,
            "photo_count": newsletter.photo_count or 0,
            "status": newsletter.status,
            "recipient_type": newsletter.recipient_type,
            "created_at": newsletter.created_at,
        }

    result = DatabaseManager.safe_execute(_save_newsletter)

    # Удаляем временные файлы
    for photo_path in photo_paths:
        try:
            Path(photo_path).unlink()
        except Exception as e:
            logger.warning(f"Failed to delete photo {photo_path}: {e}")

    logger.info(f"Newsletter sent: {success_count}/{len(recipients)} delivered")

    return result


@router.get("/newsletters/history", response_model=List[NewsletterResponse])
async def get_newsletter_history(
    limit: int = 50, offset: int = 0, _: str = Depends(verify_token)
):
    """Получение истории рассылок."""

    def _get_history(session):
        newsletters = (
            session.query(Newsletter)
            .order_by(Newsletter.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return [
            {
                "id": n.id,
                "message": n.message,
                "status": n.status,
                "total_count": n.total_count,
                "success_count": n.success_count,
                "photo_count": n.photo_count or 0,
                "created_at": n.created_at,
            }
            for n in newsletters
        ]

    try:
        return DatabaseManager.safe_execute(_get_history)
    except Exception as e:
        logger.error(f"Error getting newsletter history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter history")
