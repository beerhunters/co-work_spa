from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Query
from pathlib import Path
import time
import asyncio
import aiofiles
from utils.async_file_utils import AsyncFileManager
from utils.file_validation import FileValidator
from dependencies import verify_token, verify_token_with_permissions, get_bot
from config import NEWSLETTER_PHOTOS_DIR, MOSCOW_TZ
from models.models import Newsletter, User, DatabaseManager, Permission
from schemas.newsletter_schemas import NewsletterResponse
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/newsletters", tags=["newsletters"])


async def save_uploaded_photo_async(photo: UploadFile, idx: int) -> Optional[str]:
    """Безопасное сохранение фотографии с валидацией"""
    try:
        # Валидация файла
        FileValidator.validate_image_file(photo)
        
        # Валидация содержимого
        contents = await photo.read()
        if not await FileValidator.validate_file_content(contents, 'image'):
            logger.warning(f"File {photo.filename} failed content validation")
            return None

        # Генерация безопасного имени файла
        safe_filename = FileValidator.generate_safe_filename(
            photo.filename, f"newsletter_{idx}"
        )
        file_path = NEWSLETTER_PHOTOS_DIR / safe_filename

        # Используем AsyncFileManager
        success = await AsyncFileManager.save_uploaded_file(contents, file_path)
        return str(file_path) if success else None

    except HTTPException:
        # Пробрасываем HTTP исключения валидации
        raise
    except Exception as e:
        logger.error(f"Error saving photo {idx}: {e}")
        return None


async def cleanup_photos_async(photo_paths: List[str]):
    """Упрощенная очистка с AsyncFileManager"""
    for photo_path in photo_paths:
        await AsyncFileManager.delete_file_async(Path(photo_path))


@router.get("")
async def get_newsletters(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение рассылок (для фронтенда)."""
    return await get_newsletter_history(limit, offset, _)


@router.post("/send")
async def send_newsletter(
    message: str = Form(...),
    recipient_type: str = Form(...),
    user_ids: Optional[List[str]] = Form(None),
    photos: Optional[List[UploadFile]] = File(None),
    _: str = Depends(verify_token_with_permissions([Permission.SEND_NEWSLETTERS])),
):
    """Отправка рассылки пользователям через Telegram бота с асинхронной обработкой файлов."""
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

    # Асинхронная обработка фотографий
    photo_paths = []
    if photos:
        if len(photos) > 10:
            raise HTTPException(
                status_code=400,
                detail="Превышено максимальное количество фотографий (максимум 10)",
            )

        # Обрабатываем все фото параллельно
        photo_tasks = [
            save_uploaded_photo_async(photo, idx) for idx, photo in enumerate(photos)
        ]

        # Ждем завершения всех задач
        saved_paths = await asyncio.gather(*photo_tasks, return_exceptions=True)

        # Фильтруем успешно сохраненные фото
        for result in saved_paths:
            if isinstance(result, str):  # Успешно сохранено
                photo_paths.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Photo processing failed: {result}")

        logger.info(f"Successfully processed {len(photo_paths)}/{len(photos)} photos")

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

    try:
        recipients = DatabaseManager.safe_execute(_get_recipients)
    except Exception as e:
        # Очищаем загруженные фото при ошибке
        await cleanup_photos_async(photo_paths)
        logger.error(f"Error getting recipients: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recipients")

    if not recipients:
        await cleanup_photos_async(photo_paths)
        raise HTTPException(status_code=400, detail="Нет получателей для рассылки")

    # Отправка сообщений
    success_count = 0
    failed_count = 0

    for recipient in recipients:
        try:
            if photo_paths:
                if len(photo_paths) == 1:
                    # Одно фото - читаем асинхронно и отправляем
                    async with aiofiles.open(photo_paths[0], "rb") as photo_file:
                        photo_content = await photo_file.read()

                    from aiogram.types import BufferedInputFile

                    photo_file_obj = BufferedInputFile(
                        photo_content, filename=Path(photo_paths[0]).name
                    )

                    await bot.send_photo(
                        chat_id=recipient["telegram_id"],
                        photo=photo_file_obj,
                        caption=message,
                        parse_mode="HTML",
                    )
                else:
                    # Несколько фото - отправляем как медиагруппу
                    from aiogram.types import InputMediaPhoto, BufferedInputFile

                    media_group = []
                    for photo_idx, photo_path in enumerate(photo_paths):
                        # Асинхронно читаем каждое фото
                        async with aiofiles.open(photo_path, "rb") as photo_file:
                            photo_content = await photo_file.read()

                        media = InputMediaPhoto(
                            media=BufferedInputFile(
                                photo_content, filename=f"photo_{photo_idx}.jpg"
                            ),
                            caption=message if photo_idx == 0 else None,
                            parse_mode="HTML" if photo_idx == 0 else None,
                        )
                        media_group.append(media)

                    await bot.send_media_group(
                        chat_id=recipient["telegram_id"], media=media_group
                    )
            else:
                # Только текст
                await bot.send_message(
                    chat_id=recipient["telegram_id"], text=message, parse_mode="HTML"
                )

            success_count += 1

            # Небольшая задержка для избежания rate limiting
            await asyncio.sleep(0.05)

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

    try:
        result = DatabaseManager.safe_execute(_save_newsletter)
    except Exception as e:
        logger.error(f"Error saving newsletter: {e}")
        # Продолжаем выполнение, даже если не удалось сохранить в БД
        result = {
            "total_count": len(recipients),
            "success_count": success_count,
            "failed_count": failed_count,
            "photo_count": len(photo_paths),
            "status": status,
        }

    # Асинхронно удаляем временные файлы
    await cleanup_photos_async(photo_paths)

    logger.info(f"Newsletter sent: {success_count}/{len(recipients)} delivered")
    return result


@router.get("/history", response_model=List[NewsletterResponse])
async def get_newsletter_history(
    limit: int = 50,
    offset: int = 0,
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
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


@router.delete("/clear-history")
async def clear_newsletter_history(
    current_admin: str = Depends(
        verify_token_with_permissions([Permission.MANAGE_NEWSLETTERS])
    ),
):
    """Очистка всей истории рассылок."""

    def _clear_history(session):
        # Получаем количество рассылок для логирования
        count = session.query(Newsletter).count()

        # Удаляем все рассылки
        session.query(Newsletter).delete()
        session.flush()

        return count

    try:
        deleted_count = DatabaseManager.safe_execute(_clear_history)

        logger.info(
            f"Newsletter history cleared by admin {current_admin}. Deleted {deleted_count} newsletters"
        )
        return {
            "message": f"Newsletter history cleared successfully",
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Error clearing newsletter history: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to clear newsletter history"
        )


@router.get("/{newsletter_id}", response_model=NewsletterResponse)
async def get_newsletter_detail(
    newsletter_id: int,
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение деталей конкретной рассылки."""

    def _get_newsletter(session):
        newsletter = (
            session.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        )
        if not newsletter:
            return None

        return {
            "id": newsletter.id,
            "message": newsletter.message,
            "status": newsletter.status,
            "total_count": newsletter.total_count,
            "success_count": newsletter.success_count,
            "photo_count": newsletter.photo_count or 0,
            "created_at": newsletter.created_at,
        }

    try:
        result = DatabaseManager.safe_execute(_get_newsletter)
        if not result:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        return result
    except Exception as e:
        logger.error(f"Error getting newsletter {newsletter_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter details")


@router.delete("/{newsletter_id}")
async def delete_newsletter(
    newsletter_id: int,
    current_admin: str = Depends(
        verify_token_with_permissions([Permission.MANAGE_NEWSLETTERS])
    ),
):
    """Удаление конкретной рассылки."""

    def _delete_newsletter(session):
        newsletter = (
            session.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        )
        if not newsletter:
            return False

        newsletter_info = {
            "id": newsletter.id,
            "message": (
                newsletter.message[:50] + "..."
                if len(newsletter.message) > 50
                else newsletter.message
            ),
            "created_at": newsletter.created_at,
        }

        session.delete(newsletter)
        session.flush()
        return newsletter_info

    try:
        result = DatabaseManager.safe_execute(_delete_newsletter)
        if not result:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        logger.info(f"Newsletter {newsletter_id} deleted by admin {current_admin}")
        return {
            "message": f"Newsletter {newsletter_id} successfully deleted",
            "deleted_newsletter": result,
        }

    except Exception as e:
        logger.error(f"Error deleting newsletter {newsletter_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete newsletter")
