from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Query
from fastapi.responses import StreamingResponse
from pathlib import Path
import time
import asyncio
import aiofiles
import json
import csv
import io
from celery.result import AsyncResult
from utils.async_file_utils import AsyncFileManager
from utils.file_validation import FileValidator
from dependencies import verify_token, verify_token_with_permissions, get_bot
from config import NEWSLETTER_PHOTOS_DIR, MOSCOW_TZ
from models.models import Newsletter, User, DatabaseManager, Permission
from schemas.newsletter_schemas import NewsletterResponse
from utils.logger import get_logger
from tasks.newsletter_tasks import send_newsletter_task

logger = get_logger(__name__)
router = APIRouter(prefix="/newsletters", tags=["newsletters"])


def get_users_by_segment(session, segment_type: str, params: dict = None):
    """
    Получение пользователей по типу сегмента.

    Supported segments:
    - active_users: пользователи с бронированиями за последние N дней
    - new_users: недавно зарегистрированные (за последние N дней)
    - vip_users: пользователи с >= N успешных бронирований
    - inactive_users: пользователи без бронирований N+ дней
    - with_agreement: пользователи согласившиеся с условиями
    """
    from datetime import timedelta

    params = params or {}
    query = session.query(User).filter(User.telegram_id.isnot(None))

    if segment_type == "active_users":
        days = params.get("days", 30)
        cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=days)
        # Пользователи с недавними бронированиями
        query = query.filter(User.reg_date >= cutoff_date)

    elif segment_type == "new_users":
        days = params.get("days", 7)
        cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=days)
        query = query.filter(User.reg_date >= cutoff_date)

    elif segment_type == "vip_users":
        min_bookings = params.get("min_bookings", 5)
        query = query.filter(User.successful_bookings >= min_bookings)

    elif segment_type == "inactive_users":
        days = params.get("days", 30)
        cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=days)
        query = query.filter(User.reg_date < cutoff_date)
        query = query.filter(User.successful_bookings == 0)

    elif segment_type == "with_agreement":
        query = query.filter(User.agreed_to_terms == True)

    else:
        raise ValueError(f"Unknown segment type: {segment_type}")

    return query.all()


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
    status: Optional[str] = Query(None),
    recipient_type: Optional[str] = Query(None),
    segment_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    current_admin: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение рассылок (для фронтенда)."""
    return await get_newsletter_history(
        limit=limit,
        offset=offset,
        status=status,
        recipient_type=recipient_type,
        segment_type=segment_type,
        search=search,
        date_from=date_from,
        date_to=date_to,
        _=current_admin
    )


@router.post("/send")
async def send_newsletter(
    message: str = Form(...),
    recipient_type: str = Form(...),
    user_ids: Optional[List[str]] = Form(None),
    segment_type: Optional[str] = Form(None),
    segment_params: Optional[str] = Form(None),  # JSON string
    photos: Optional[List[UploadFile]] = File(None),
    _: str = Depends(verify_token_with_permissions([Permission.SEND_NEWSLETTERS])),
):
    """Отправка рассылки пользователям через Telegram бота с использованием фоновой очереди."""
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

    if recipient_type not in ["all", "selected", "segment"]:
        raise HTTPException(status_code=400, detail="Неверный тип получателей")

    if recipient_type == "selected" and not user_ids:
        raise HTTPException(status_code=400, detail="Не выбраны получатели")

    if recipient_type == "segment" and not segment_type:
        raise HTTPException(status_code=400, detail="Не указан тип сегмента")

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
        elif recipient_type == "selected":
            telegram_ids = [int(uid) for uid in user_ids if uid.isdigit()]
            users = session.query(User).filter(User.telegram_id.in_(telegram_ids)).all()
        elif recipient_type == "segment":
            # Парсим параметры сегментации
            import json
            params = {}
            if segment_params:
                try:
                    params = json.loads(segment_params)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid segment_params JSON: {segment_params}")

            # Получаем пользователей по сегменту
            users = get_users_by_segment(session, segment_type, params)
        else:
            users = []

        return [
            {
                "user_id": user.id,
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

    # Подготовка данных для Celery задачи
    newsletter_data = {
        "recipient_type": recipient_type,
        "segment_type": segment_type if recipient_type == "segment" else None,
        "segment_params": segment_params if recipient_type == "segment" else None,
    }

    # Запуск Celery задачи для фоновой отправки
    try:
        task = send_newsletter_task.apply_async(
            args=[message, recipients, photo_paths, newsletter_data],
            queue='newsletters'
        )

        logger.info(f"Newsletter task queued: {task.id} for {len(recipients)} recipients")

        return {
            "task_id": task.id,
            "status": "queued",
            "total_count": len(recipients),
            "message": "Рассылка поставлена в очередь на отправку"
        }

    except Exception as e:
        # При ошибке запуска задачи очищаем фотографии
        await cleanup_photos_async(photo_paths)
        logger.error(f"Error queuing newsletter task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось поставить рассылку в очередь: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_newsletter_task_status(
    task_id: str,
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение статуса задачи рассылки по task_id."""
    try:
        task_result = AsyncResult(task_id)

        if task_result.state == 'PENDING':
            response = {
                'task_id': task_id,
                'state': 'PENDING',
                'status': 'Задача в очереди...',
                'current': 0,
                'total': 0,
            }
        elif task_result.state == 'PROGRESS':
            response = {
                'task_id': task_id,
                'state': 'PROGRESS',
                'status': task_result.info.get('status', ''),
                'current': task_result.info.get('current', 0),
                'total': task_result.info.get('total', 0),
                'success': task_result.info.get('success', 0),
                'failed': task_result.info.get('failed', 0),
            }
        elif task_result.state == 'SUCCESS':
            result = task_result.result
            response = {
                'task_id': task_id,
                'state': 'SUCCESS',
                'status': 'Рассылка завершена',
                'result': result,
            }
        elif task_result.state == 'FAILURE':
            response = {
                'task_id': task_id,
                'state': 'FAILURE',
                'status': 'Ошибка при выполнении рассылки',
                'error': str(task_result.info),
            }
        else:
            response = {
                'task_id': task_id,
                'state': task_result.state,
                'status': str(task_result.info),
            }

        return response

    except Exception as e:
        logger.error(f"Error checking task status {task_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статус задачи: {str(e)}"
        )


@router.get("/history", response_model=List[NewsletterResponse])
async def get_newsletter_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Фильтр по статусу: success, failed, partial"),
    recipient_type: Optional[str] = Query(None, description="Фильтр по типу: all, selected, segment"),
    segment_type: Optional[str] = Query(None, description="Фильтр по типу сегмента"),
    search: Optional[str] = Query(None, description="Поиск по тексту сообщения"),
    date_from: Optional[str] = Query(None, description="Фильтр от даты (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Фильтр до даты (YYYY-MM-DD)"),
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение истории рассылок с фильтрацией и поиском."""

    def _get_history(session):
        query = session.query(Newsletter)

        # Применяем фильтры
        if status:
            query = query.filter(Newsletter.status == status)

        if recipient_type:
            query = query.filter(Newsletter.recipient_type == recipient_type)

        if segment_type:
            query = query.filter(Newsletter.segment_type == segment_type)

        if search:
            # Поиск по тексту сообщения
            query = query.filter(Newsletter.message.contains(search))

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
                query = query.filter(Newsletter.created_at >= from_date)
            except ValueError:
                pass  # Игнорируем неверный формат даты

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
                # Добавляем 1 день, чтобы включить весь день date_to
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Newsletter.created_at <= to_date)
            except ValueError:
                pass  # Игнорируем неверный формат даты

        newsletters = (
            query
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
                "recipient_type": n.recipient_type,
                "segment_type": n.segment_type,
                "created_at": n.created_at,
            }
            for n in newsletters
        ]

    try:
        return DatabaseManager.safe_execute(_get_history)
    except Exception as e:
        logger.error(f"Error getting newsletter history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get newsletter history")


@router.get("/export-csv")
async def export_newsletters_csv(
    status: Optional[str] = Query(None),
    recipient_type: Optional[str] = Query(None),
    segment_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Экспорт истории рассылок в CSV с фильтрацией."""

    def _get_newsletters_for_export(session):
        query = session.query(Newsletter)

        # Применяем те же фильтры, что и в /history
        if status:
            query = query.filter(Newsletter.status == status)
        if recipient_type:
            query = query.filter(Newsletter.recipient_type == recipient_type)
        if segment_type:
            query = query.filter(Newsletter.segment_type == segment_type)
        if search:
            query = query.filter(Newsletter.message.contains(search))
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
                query = query.filter(Newsletter.created_at >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=MOSCOW_TZ)
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Newsletter.created_at <= to_date)
            except ValueError:
                pass

        return query.order_by(Newsletter.created_at.desc()).all()

    try:
        newsletters = DatabaseManager.safe_execute(_get_newsletters_for_export)

        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow([
            'ID',
            'Дата отправки',
            'Статус',
            'Тип получателей',
            'Тип сегмента',
            'Всего получателей',
            'Доставлено',
            'Не доставлено',
            'Процент успеха (%)',
            'Фотографий',
            'Сообщение (первые 100 символов)'
        ])

        # Данные
        for n in newsletters:
            success_rate = (n.success_count / n.total_count * 100) if n.total_count > 0 else 0

            # Переводим типы на русский
            recipient_type_ru = {
                'all': 'Все пользователи',
                'selected': 'Выбранные',
                'segment': 'Сегмент'
            }.get(n.recipient_type, n.recipient_type)

            segment_type_ru = ''
            if n.segment_type:
                segment_type_ru = {
                    'active_users': 'Активные',
                    'new_users': 'Новые',
                    'vip_users': 'VIP',
                    'inactive_users': 'Неактивные',
                    'with_agreement': 'С соглашением'
                }.get(n.segment_type, n.segment_type)

            status_ru = {
                'success': 'Успешно',
                'partial': 'Частично',
                'failed': 'Ошибка'
            }.get(n.status, n.status)

            writer.writerow([
                n.id,
                n.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                status_ru,
                recipient_type_ru,
                segment_type_ru,
                n.total_count,
                n.success_count,
                n.total_count - n.success_count,
                f"{success_rate:.1f}",
                n.photo_count or 0,
                n.message[:100] + ('...' if len(n.message) > 100 else '')
            ])

        # Подготовка файла для скачивания
        output.seek(0)

        # Имя файла с датой
        filename = f"newsletters_export_{datetime.now(MOSCOW_TZ).strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM для правильного отображения в Excel
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        logger.error(f"Error exporting newsletters to CSV: {e}")
        raise HTTPException(status_code=500, detail="Failed to export newsletters")


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
            "recipient_type": newsletter.recipient_type,
            "segment_type": newsletter.segment_type,
            "segment_params": newsletter.segment_params,
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


@router.get("/{newsletter_id}/recipients")
async def get_newsletter_recipients(
    newsletter_id: int,
    _: str = Depends(verify_token_with_permissions([Permission.VIEW_NEWSLETTERS])),
):
    """Получение детальной информации о получателях конкретной рассылки."""

    def _get_recipients(session):
        from models.models import NewsletterRecipient

        # Проверяем, существует ли рассылка
        newsletter = (
            session.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        )
        if not newsletter:
            return None

        # Получаем всех получателей
        recipients = (
            session.query(NewsletterRecipient)
            .filter(NewsletterRecipient.newsletter_id == newsletter_id)
            .order_by(NewsletterRecipient.sent_at.desc())
            .all()
        )

        return {
            "newsletter_id": newsletter_id,
            "total_count": len(recipients),
            "recipients": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "telegram_id": r.telegram_id,
                    "full_name": r.full_name,
                    "status": r.status,
                    "error_message": r.error_message,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                }
                for r in recipients
            ],
        }

    try:
        result = DatabaseManager.safe_execute(_get_recipients)
        if result is None:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        return result
    except Exception as e:
        logger.error(f"Error getting recipients for newsletter {newsletter_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to get newsletter recipients"
        )


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
