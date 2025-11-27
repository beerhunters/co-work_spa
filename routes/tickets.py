from datetime import datetime
from pathlib import Path
from typing import List, Optional
import base64
import asyncio
from pathlib import Path
from fastapi.responses import FileResponse, Response
from config import TICKET_PHOTOS_DIR
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from models.models import Ticket, User, TicketStatus, Notification, DatabaseManager
from dependencies import get_db, verify_token, get_bot
from config import MOSCOW_TZ, TICKET_PHOTOS_DIR
from schemas.ticket_schemas import TicketCreate
from utils.logger import get_logger
from utils.async_file_utils import AsyncFileManager
from utils.file_security import validate_upload_file, create_safe_file_path
from utils.sql_optimization import SQLOptimizer

logger = get_logger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


async def get_photo_from_telegram(photo_id: str) -> tuple[bytes, str]:
    """Получаем фото напрямую из Telegram без кэширования"""
    try:
        bot = get_bot()
        if not bot:
            raise Exception("Telegram bot not available")

        photo_data, mime_type = await _get_telegram_photo_data(photo_id, bot)
        logger.debug(f"Фото загружено из Telegram: {photo_id}")
        return photo_data, mime_type

    except Exception as e:
        logger.error(f"Ошибка получения фото {photo_id}: {e}")
        raise


@router.get("")
async def get_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_query: Optional[str] = Query(None),
    _: str = Depends(verify_token),
):
    """Получение тикетов (возвращает только массив для фронтенда)."""
    result = await get_tickets_detailed(page, per_page, status, user_query, _)
    return result.get("tickets", []) if isinstance(result, dict) else []


@router.get("/detailed")
async def get_tickets_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    user_query: Optional[str] = None,
    _: str = Depends(verify_token),
):
    """Получение тикетов с данными пользователей и фильтрацией."""

    def _get_tickets(session):
        try:
            # Используем оптимизированный запрос с индексами
            return SQLOptimizer.get_optimized_tickets_with_users(
                session, page, per_page, status, user_query
            )

        except Exception as e:
            logger.error(f"Ошибка в _get_tickets: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_tickets)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при получении тикетов: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.get("/{ticket_id}")
async def get_ticket_by_id(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение тикета по ID."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        user = db.query(User).filter(User.id == ticket.user_id).first()

        return {
            "id": ticket.id,
            "user_id": ticket.user_id,
            "description": ticket.description,
            "photo_id": ticket.photo_id,
            "response_photo_id": ticket.response_photo_id,
            "status": ticket.status.name,
            "comment": ticket.comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "user": (
                {
                    "id": user.id if user else ticket.user_id,
                    "telegram_id": user.telegram_id if user else None,
                    "full_name": user.full_name if user else "Пользователь не найден",
                    "username": user.username if user else None,
                    "phone": user.phone if user else None,
                    "email": user.email if user else None,
                }
                if user
                else {
                    "id": ticket.user_id,
                    "telegram_id": None,
                    "full_name": "Пользователь не найден",
                    "username": None,
                    "phone": None,
                    "email": None,
                }
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении тикета {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.get("/stats")
async def get_tickets_stats(_: str = Depends(verify_token)):
    """Получение статистики по тикетам."""

    def _get_stats(session):
        total_tickets = session.execute(text("SELECT COUNT(*) FROM tickets")).scalar()
        open_tickets = session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'")
        ).scalar()
        in_progress_tickets = session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE status = 'IN_PROGRESS'")
        ).scalar()
        closed_tickets = session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE status = 'CLOSED'")
        ).scalar()

        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "in_progress_tickets": in_progress_tickets,
            "closed_tickets": closed_tickets,
            "avg_response_time": 0,  # Можно добавить реальную логику
        }

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики тикетов: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.post("")
async def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    """Создание нового тикета. Используется ботом."""
    user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Пользователь не найден в системе")

    status_enum = TicketStatus.OPEN
    if ticket_data.status:
        try:
            status_enum = TicketStatus(ticket_data.status)
        except ValueError:
            status_enum = TicketStatus.OPEN

    ticket = Ticket(
        user_id=user.id,
        description=ticket_data.description,
        photo_id=ticket_data.photo_id,
        status=status_enum,
        comment=ticket_data.comment,
        created_at=datetime.now(MOSCOW_TZ),
        updated_at=datetime.now(MOSCOW_TZ),
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return {"id": ticket.id, "message": "Ticket created successfully"}


@router.get("/users/telegram/{telegram_id}/tickets")
async def get_user_tickets_by_telegram_id(
    telegram_id: int, status: Optional[str] = Query(None), db: Session = Depends(get_db)
):
    """Получение тикетов пользователя по его Telegram ID."""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь не найден в системе")

        query = (
            db.query(Ticket)
            .filter(Ticket.user_id == user.id)
            .order_by(Ticket.created_at.desc())
        )

        if status:
            try:
                status_enum = TicketStatus[status]
                query = query.filter(Ticket.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        tickets = query.all()

        result = []
        for ticket in tickets:
            result.append(
                {
                    "id": ticket.id,
                    "description": ticket.description,
                    "photo_id": ticket.photo_id,
                    "response_photo_id": ticket.response_photo_id,
                    "status": ticket.status.name,
                    "comment": ticket.comment,
                    "created_at": ticket.created_at.isoformat(),
                    "updated_at": ticket.updated_at.isoformat(),
                    "user_id": ticket.user_id,
                }
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении тикетов пользователя {telegram_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление тикета (статус, комментарий, фото ответа)."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        user = db.query(User).filter(User.id == ticket.user_id).first()

        old_status = ticket.status
        old_comment = ticket.comment

        # Сохраняем ID для использования после async операций
        user_telegram_id = user.telegram_id if user else None

        # Подготавливаем данные для обновления
        db_update_data = {}

        # Обновляем статус
        if "status" in update_data and update_data["status"]:
            try:
                new_status = TicketStatus[update_data["status"]]
                db_update_data["status"] = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        # Обновляем комментарий
        if "comment" in update_data:
            db_update_data["comment"] = update_data["comment"]

        db_update_data["updated_at"] = datetime.now(MOSCOW_TZ)

        # Отправка уведомления пользователю
        bot = get_bot()
        if bot and user and user_telegram_id and not update_data.get("photo_sent"):
            try:
                status_changed = (
                    "status" in db_update_data
                    and old_status != db_update_data["status"]
                )
                comment_changed = (
                    "comment" in db_update_data
                    and db_update_data["comment"]
                    and db_update_data["comment"] != old_comment
                )

                if status_changed or comment_changed:
                    status_messages = {
                        TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
                        TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
                        TicketStatus.CLOSED: "✅ Ваша заявка решена",
                    }

                    message = f"🎫 <b>Обновление по заявке #{ticket_id}</b>\n\n"

                    if status_changed:
                        message += status_messages.get(
                            db_update_data["status"],
                            f"Статус: {db_update_data['status'].name}",
                        )

                    if comment_changed:
                        message += f"\n\n💬 <b>Комментарий администратора:</b>\n{db_update_data['comment']}"

                    from utils.external_api import send_telegram_notification

                    await send_telegram_notification(bot, user_telegram_id, message)

            except Exception as e:
                logger.error(f"Ошибка отправки уведомления о тикете #{ticket_id}: {e}")

        # Обновляем тикет в БД через свежий запрос
        fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not fresh_ticket:
            raise HTTPException(
                status_code=404, detail=f"Тикет не найден при попытке обновления"
            )

        # Применяем изменения
        for key, value in db_update_data.items():
            setattr(fresh_ticket, key, value)

        db.commit()
        db.refresh(fresh_ticket)

        return {
            "id": fresh_ticket.id,
            "description": fresh_ticket.description,
            "photo_id": fresh_ticket.photo_id,
            "response_photo_id": fresh_ticket.response_photo_id,
            "status": fresh_ticket.status.name,
            "comment": fresh_ticket.comment,
            "created_at": fresh_ticket.created_at.isoformat(),
            "updated_at": fresh_ticket.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления тикета {ticket_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


async def _get_telegram_photo_data(photo_id: str, bot) -> tuple[bytes, str]:
    """Получение данных фото из Telegram."""
    try:
        file = await bot.get_file(photo_id)

        # Определяем MIME type по расширению
        file_path = file.file_path
        ext = Path(file_path).suffix.lower() if file_path else ".jpg"

        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

        # Скачиваем файл в память
        from io import BytesIO

        file_data = BytesIO()
        await bot.download_file(file.file_path, destination=file_data)
        file_data.seek(0)

        return file_data.read(), mime_type

    except Exception as e:
        logger.error(f"Ошибка загрузки фото {photo_id} из Telegram: {e}")
        raise


@router.get("/{ticket_id}/photo")
async def get_ticket_photo(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото тикета по ID напрямую из Telegram."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        if not ticket.photo_id:
            raise HTTPException(
                status_code=404, detail=f"Фото не найдено для тикета #{ticket_id}"
            )

        try:
            # Загружаем фото напрямую из Telegram
            photo_data, mime_type = await get_photo_from_telegram(ticket.photo_id)

            return Response(
                content=photo_data,
                media_type=mime_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Disposition": f"inline; filename=ticket_{ticket_id}_photo.jpg",
                },
            )

        except Exception as e:
            logger.error(
                f"Ошибка загрузки фото из Telegram для тикета {ticket_id}: {e}"
            )
            raise HTTPException(
                status_code=404, detail="Photo not available from Telegram"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения фото тикета {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.get("/{ticket_id}/photo-base64")
async def get_ticket_photo_base64(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото тикета в формате base64 напрямую из Telegram."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        if not ticket.photo_id:
            raise HTTPException(
                status_code=404, detail=f"Фото не найдено для тикета #{ticket_id}"
            )

        try:
            # Загружаем фото напрямую из Telegram
            photo_data, mime_type = await get_photo_from_telegram(ticket.photo_id)

            # Кодируем в base64
            base64_data = base64.b64encode(photo_data).decode("utf-8")
            data_url = f"data:{mime_type};base64,{base64_data}"

            return {
                "photo_url": data_url,
                "mime_type": mime_type,
                "size": len(photo_data),
                "ticket_id": ticket_id,
            }

        except Exception as e:
            logger.error(
                f"Ошибка загрузки фото из Telegram для тикета {ticket_id}: {e}"
            )
            raise HTTPException(
                status_code=404, detail="Photo not available from Telegram"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения base64 фото тикета {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.get("/{ticket_id}/response-photo")
async def get_ticket_response_photo(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото ответа администратора на тикет напрямую из Telegram."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        if not ticket.response_photo_id:
            raise HTTPException(
                status_code=404, detail=f"Фото ответа не найдено для тикета #{ticket_id}"
            )

        try:
            # Загружаем фото напрямую из Telegram
            photo_data, mime_type = await get_photo_from_telegram(
                ticket.response_photo_id
            )

            return Response(
                content=photo_data,
                media_type=mime_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Disposition": f"inline; filename=ticket_{ticket_id}_response.jpg",
                },
            )

        except Exception as e:
            logger.error(
                f"Ошибка загрузки фото ответа из Telegram для тикета {ticket_id}: {e}"
            )
            raise HTTPException(
                status_code=404, detail="Response photo not available from Telegram"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения фото ответа тикета {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.get("/{ticket_id}/response-photo-base64")
async def get_ticket_response_photo_base64(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото ответа администратора на тикет в формате base64."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        if not ticket.response_photo_id:
            raise HTTPException(
                status_code=404, detail=f"Фото ответа не найдено для тикета #{ticket_id}"
            )

        try:
            # Загружаем фото напрямую из Telegram
            photo_data, mime_type = await get_photo_from_telegram(
                ticket.response_photo_id
            )

            # Конвертируем в base64
            import base64
            photo_base64 = base64.b64encode(photo_data).decode('utf-8')
            data_url = f"data:{mime_type};base64,{photo_base64}"

            logger.info(f"Получено base64 фото ответа для тикета {ticket_id}")
            return {"photo_url": data_url}

        except Exception as e:
            logger.error(
                f"Ошибка загрузки фото ответа из Telegram для тикета {ticket_id}: {e}"
            )
            raise HTTPException(
                status_code=404, detail="Response photo not available from Telegram"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения base64 фото ответа тикета {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.post("/{ticket_id}/photo")
async def send_photo_to_user(
    ticket_id: int,
    file: UploadFile = File(...),
    comment: str = Form(None),
    status: str = Form(None),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Отправка фото пользователю с комментарием и обновлением статуса тикета."""
    try:
        # Получаем данные тикета и пользователя
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

        user = db.query(User).filter(User.id == ticket.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь не найден в системе")

        # Сохраняем исходные значения для сравнения
        old_status = ticket.status
        old_comment = ticket.comment

        # Сохраняем ID и telegram_id для последующего использования
        ticket_id_value = ticket.id
        user_telegram_id = user.telegram_id
        user_id_value = user.id

        # Обработка загружаемого фото с комплексной валидацией безопасности
        file_content = None
        if file:
            try:
                # Комплексная валидация файла с проверкой безопасности
                file_info = await validate_upload_file(
                    file, 
                    file_type='image',
                    check_content=True  # Проверяем реальное содержимое
                )
                
                # Читаем содержимое файла
                file_content = await file.read()
                
                logger.info(
                    f"Получено и валидировано фото для отправки пользователю тикета {ticket_id}: "
                    f"{file_info['filename']} ({file_info['size']} байт, {file_info.get('width', '?')}x{file_info.get('height', '?')})"
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка обработки загруженного фото для тикета {ticket_id}: {e}"
                )
                raise HTTPException(
                    status_code=500, detail="Не удалось обработать загруженное фото. Проверьте формат файла"
                )

        # Подготавливаем данные для обновления
        update_data = {}

        # Обновляем статус
        if status:
            try:
                new_status = TicketStatus[status]
                update_data["status"] = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        # Обновляем комментарий
        if comment is not None:
            update_data["comment"] = comment

        update_data["updated_at"] = datetime.now(MOSCOW_TZ)

        # Отправка фото и сообщения пользователю через Telegram
        bot = get_bot()
        photo_sent = False
        response_photo_id = None

        if bot and user_telegram_id:
            try:
                status_changed = (
                    "status" in update_data and old_status != update_data["status"]
                )
                comment_changed = (
                    "comment" in update_data
                    and update_data["comment"]
                    and update_data["comment"] != old_comment
                )
                has_file = file_content is not None

                if status_changed or comment_changed or has_file:
                    status_messages = {
                        TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
                        TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
                        TicketStatus.CLOSED: "✅ Ваша заявка решена",
                    }

                    message = f"🎫 <b>Обновление по заявке #{ticket_id_value}</b>\n\n"

                    if status_changed:
                        message += status_messages.get(
                            update_data["status"],
                            f"Статус: {update_data['status'].name}",
                        )

                    if comment_changed:
                        message += f"\n\n💬 <b>Комментарий администратора:</b>\n{update_data['comment']}"

                    # Отправляем фото если есть
                    if has_file and file_content:
                        try:
                            from aiogram.types import BufferedInputFile

                            # Создаем BufferedInputFile для отправки через aiogram
                            input_file = BufferedInputFile(
                                file_content,
                                filename=file.filename
                                or f"response_{ticket_id_value}.jpg",
                            )

                            # Отправляем фото с сообщением
                            sent_message = await bot.send_photo(
                                chat_id=user_telegram_id,
                                photo=input_file,
                                caption=message,
                                parse_mode="HTML",
                            )

                            # Получаем file_id отправленного фото для сохранения в БД
                            if sent_message.photo:
                                response_photo_id = sent_message.photo[-1].file_id
                                update_data["response_photo_id"] = response_photo_id

                            photo_sent = True
                            logger.info(
                                f"Отправлено сообщение с фото пользователю {user_telegram_id}, file_id: {response_photo_id}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Ошибка отправки фото пользователю {user_telegram_id}: {e}"
                            )
                            # Отправляем только текст в случае ошибки
                            try:
                                from utils.external_api import (
                                    send_telegram_notification,
                                )

                                await send_telegram_notification(
                                    bot, user_telegram_id, message
                                )
                            except Exception as fallback_error:
                                logger.error(
                                    f"Ошибка отправки текстового сообщения: {fallback_error}"
                                )
                    else:
                        # Отправляем только текст
                        try:
                            from utils.external_api import send_telegram_notification

                            await send_telegram_notification(
                                bot, user_telegram_id, message
                            )
                        except Exception as text_error:
                            logger.error(
                                f"Ошибка отправки текстового сообщения: {text_error}"
                            )

            except Exception as e:
                logger.error(
                    f"Ошибка отправки уведомления о тикете #{ticket_id_value}: {e}"
                )

        # КРИТИЧЕСКИЙ МОМЕНТ: Обновляем тикет в БД ПОСЛЕ отправки через новый запрос
        try:
            # Получаем свежий объект тикета из БД
            fresh_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if not fresh_ticket:
                raise HTTPException(
                    status_code=404, detail=f"Тикет не найден при попытке обновления"
                )

            # Применяем все изменения к свежему объекту
            for key, value in update_data.items():
                setattr(fresh_ticket, key, value)

            # Сохраняем изменения
            db.commit()
            db.refresh(fresh_ticket)

            logger.info(f"Тикет #{ticket_id_value} успешно обновлен в БД")

        except Exception as db_error:
            logger.error(f"Ошибка обновления тикета в БД: {db_error}")
            db.rollback()
            # Даже если БД не обновилась, уведомление уже отправлено
            # Возвращаем частичный успех
            return {
                "success": False,
                "message": "Photo sent but database update failed",
                "photo_sent": photo_sent,
                "db_error": str(db_error),
                "response_photo_id": response_photo_id,
            }

        # Получаем обновленные данные пользователя для ответа
        updated_user = db.query(User).filter(User.id == user_id_value).first()

        # Возвращаем обновленный тикет
        updated_ticket = {
            "id": fresh_ticket.id,
            "description": fresh_ticket.description,
            "photo_id": fresh_ticket.photo_id,
            "response_photo_id": fresh_ticket.response_photo_id,
            "status": fresh_ticket.status.name,
            "comment": fresh_ticket.comment,
            "created_at": fresh_ticket.created_at.isoformat(),
            "updated_at": fresh_ticket.updated_at.isoformat(),
            "user_id": fresh_ticket.user_id,
            "user": {
                "id": updated_user.id if updated_user else user_id_value,
                "telegram_id": (
                    updated_user.telegram_id if updated_user else user_telegram_id
                ),
                "full_name": (
                    updated_user.full_name if updated_user else "Имя не указано"
                ),
                "username": updated_user.username if updated_user else None,
                "phone": updated_user.phone if updated_user else None,
                "email": updated_user.email if updated_user else None,
            },
        }

        return {
            "success": True,
            "message": (
                "Photo sent to user successfully"
                if photo_sent
                else "Ticket updated successfully"
            ),
            "photo_sent": photo_sent,
            "updated_ticket": updated_ticket,
            "response_photo_id": response_photo_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Критическая ошибка в send_photo_to_user для тикета {ticket_id}: {e}"
        )
        db.rollback()
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера. Попробуйте позже или обратитесь к администратору")


@router.delete("/{ticket_id}")
async def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Удаление тикета."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Тикет #{ticket_id} не найден в системе")

    db.delete(ticket)
    db.commit()

    logger.info(f"Удален тикет #{ticket_id}")
    return {"message": "Ticket deleted successfully"}
