from datetime import datetime
from pathlib import Path
from typing import List, Optional
import base64
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

logger = get_logger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


# router = APIRouter(tags=["tickets"])


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
            base_query = """
                SELECT 
                    t.id, t.user_id, t.description, t.photo_id, t.response_photo_id,
                    t.status, t.comment, t.created_at, t.updated_at,
                    u.telegram_id, u.full_name, u.username, u.phone, u.email
                FROM tickets t
                LEFT JOIN users u ON t.user_id = u.id
            """

            where_conditions = []
            params = {}

            if user_query and user_query.strip():
                where_conditions.append("u.full_name LIKE :user_query")
                params["user_query"] = f"%{user_query.strip()}%"

            if status and status.strip():
                where_conditions.append("t.status = :status")
                params["status"] = status.strip()

            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            count_query = f"SELECT COUNT(*) FROM ({base_query}) as counted"
            total_count = session.execute(text(count_query), params).scalar()

            final_query = (
                base_query + " ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset"
            )
            params["limit"] = per_page
            params["offset"] = (page - 1) * per_page

            result = session.execute(text(final_query), params).fetchall()

            enriched_tickets = []
            for row in result:
                ticket_item = {
                    "id": int(row.id),
                    "user_id": int(row.user_id),
                    "description": row.description,
                    "photo_id": row.photo_id,
                    "response_photo_id": row.response_photo_id,
                    "status": row.status,
                    "comment": row.comment,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                    "user": {
                        "id": row.user_id,
                        "telegram_id": row.telegram_id,
                        "full_name": row.full_name or "Имя не указано",
                        "username": row.username,
                        "phone": row.phone,
                        "email": row.email,
                    },
                }
                enriched_tickets.append(ticket_item)

            total_pages = (total_count + per_page - 1) // per_page

            return {
                "tickets": enriched_tickets,
                "total_count": int(total_count),
                "page": int(page),
                "per_page": int(per_page),
                "total_pages": int(total_pages),
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_tickets: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_tickets)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при получении тикетов: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
            raise HTTPException(status_code=404, detail="Ticket not found")

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
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("")
async def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
    """Создание нового тикета. Используется ботом."""
    user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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


# ИСПРАВЛЕНО: Правильный эндпоинт для получения тикетов пользователя
@router.get("/users/telegram/{telegram_id}/tickets")
async def get_user_tickets_by_telegram_id(
    telegram_id: int, status: Optional[str] = Query(None), db: Session = Depends(get_db)
):
    """Получение тикетов пользователя по его Telegram ID."""
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

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
        raise HTTPException(status_code=500, detail="Internal server error")


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
            raise HTTPException(status_code=404, detail="Ticket not found")

        user = db.query(User).filter(User.id == ticket.user_id).first()

        old_status = ticket.status
        old_comment = ticket.comment

        # Обновляем статус
        if "status" in update_data and update_data["status"]:
            try:
                new_status = TicketStatus[update_data["status"]]
                ticket.status = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        # Обновляем комментарий
        if "comment" in update_data:
            ticket.comment = update_data["comment"]

        ticket.updated_at = datetime.now(MOSCOW_TZ)

        db.commit()
        db.refresh(ticket)

        # Отправка уведомления пользователю
        bot = get_bot()
        if bot and user and user.telegram_id and not update_data.get("photo_sent"):
            try:
                status_changed = old_status != ticket.status
                comment_changed = ticket.comment and ticket.comment != old_comment

                if status_changed or comment_changed:
                    status_messages = {
                        TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
                        TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
                        TicketStatus.CLOSED: "✅ Ваша заявка решена",
                    }

                    message = f"🎫 <b>Обновление по заявке #{ticket.id}</b>\n\n"

                    if status_changed:
                        message += status_messages.get(
                            ticket.status, f"Статус: {ticket.status.name}"
                        )

                    if comment_changed:
                        message += f"\n\n💬 <b>Комментарий администратора:</b>\n{ticket.comment}"

                    from utils.external_api import send_telegram_notification

                    await send_telegram_notification(bot, user.telegram_id, message)

            except Exception as e:
                logger.error(
                    f"❌ Ошибка отправки уведомления о тикете #{ticket.id}: {e}"
                )

        return {
            "id": ticket.id,
            "description": ticket.description,
            "photo_id": ticket.photo_id,
            "response_photo_id": ticket.response_photo_id,
            "status": ticket.status.name,
            "comment": ticket.comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка обновления тикета {ticket_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


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
    """Получение фото тикета по ID."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if not ticket.photo_id:
            raise HTTPException(
                status_code=404, detail="Photo not found for this ticket"
            )

        bot = get_bot()
        if not bot:
            raise HTTPException(status_code=503, detail="Telegram bot not available")

        try:
            photo_data, mime_type = await _get_telegram_photo_data(ticket.photo_id, bot)

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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{ticket_id}/photo-base64")
async def get_ticket_photo_base64(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото тикета в формате base64."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if not ticket.photo_id:
            raise HTTPException(
                status_code=404, detail="Photo not found for this ticket"
            )

        bot = get_bot()
        if not bot:
            raise HTTPException(status_code=503, detail="Telegram bot not available")

        try:
            photo_data, mime_type = await _get_telegram_photo_data(ticket.photo_id, bot)

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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{ticket_id}/response-photo")
async def get_ticket_response_photo(
    ticket_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение фото ответа администратора на тикет."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if not ticket.response_photo_id:
            raise HTTPException(
                status_code=404, detail="Response photo not found for this ticket"
            )

        bot = get_bot()
        if not bot:
            raise HTTPException(status_code=503, detail="Telegram bot not available")

        try:
            photo_data, mime_type = await _get_telegram_photo_data(
                ticket.response_photo_id, bot
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
        raise HTTPException(status_code=500, detail="Internal server error")


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
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        user = db.query(User).filter(User.id == ticket.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_status = ticket.status
        old_comment = ticket.comment

        # Обработка загружаемого фото
        response_photo_id = None
        if file:
            try:
                # Проверяем размер файла (максимум 10MB)
                if file.size and file.size > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=400, detail="File too large. Maximum size is 10MB"
                    )

                # Проверяем тип файла
                allowed_types = [
                    "image/jpeg",
                    "image/jpg",
                    "image/png",
                    "image/gif",
                    "image/webp",
                ]
                if file.content_type and file.content_type not in allowed_types:
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid file type. Only images are allowed",
                    )

                # Читаем содержимое файла
                file_content = await file.read()

                logger.info(
                    f"Получено фото для отправки пользователю тикета {ticket_id}, размер: {len(file_content)} байт"
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(
                    f"Ошибка обработки загруженного фото для тикета {ticket_id}: {e}"
                )
                raise HTTPException(
                    status_code=500, detail="Failed to process uploaded photo"
                )

        # Обновляем статус
        if status:
            try:
                new_status = TicketStatus[status]
                ticket.status = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        # Обновляем комментарий
        if comment is not None:
            ticket.comment = comment

        ticket.updated_at = datetime.now(MOSCOW_TZ)

        # Отправка фото и сообщения пользователю через Telegram
        bot = get_bot()
        photo_sent = False

        if bot and user.telegram_id:
            try:
                status_changed = old_status != ticket.status
                comment_changed = ticket.comment and ticket.comment != old_comment
                has_file = file is not None

                if status_changed or comment_changed or has_file:
                    status_messages = {
                        TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
                        TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
                        TicketStatus.CLOSED: "✅ Ваша заявка решена",
                    }

                    message = f"🎫 <b>Обновление по заявке #{ticket.id}</b>\n\n"

                    if status_changed:
                        message += status_messages.get(
                            ticket.status, f"Статус: {ticket.status.name}"
                        )

                    if comment_changed:
                        message += f"\n\n💬 <b>Комментарий администратора:</b>\n{ticket.comment}"

                    # Отправляем фото если есть
                    if has_file and file_content:
                        try:
                            from io import BytesIO
                            from aiogram.types import BufferedInputFile

                            # Создаем BufferedInputFile для отправки через aiogram
                            input_file = BufferedInputFile(
                                file_content,
                                filename=file.filename or f"response_{ticket_id}.jpg",
                            )

                            # Отправляем фото с сообщением
                            sent_message = await bot.send_photo(
                                chat_id=user.telegram_id,
                                photo=input_file,
                                caption=message,
                                parse_mode="HTML",
                            )

                            # Получаем file_id отправленного фото для сохранения в БД
                            if sent_message.photo:
                                response_photo_id = sent_message.photo[
                                    -1
                                ].file_id  # Берем самое большое фото
                                ticket.response_photo_id = response_photo_id

                            photo_sent = True
                            logger.info(
                                f"Отправлено сообщение с фото пользователю {user.telegram_id}, file_id: {response_photo_id}"
                            )

                        except Exception as e:
                            logger.error(
                                f"Ошибка отправки фото пользователю {user.telegram_id}: {e}"
                            )
                            # Отправляем только текст в случае ошибки
                            try:
                                from utils.external_api import (
                                    send_telegram_notification,
                                )

                                await send_telegram_notification(
                                    bot, user.telegram_id, message
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
                                bot, user.telegram_id, message
                            )
                        except Exception as text_error:
                            logger.error(
                                f"Ошибка отправки текстового сообщения: {text_error}"
                            )

            except Exception as e:
                logger.error(
                    f"❌ Ошибка отправки уведомления о тикете #{ticket.id}: {e}"
                )

        # Сохраняем изменения в БД после успешной отправки
        db.commit()
        db.refresh(ticket)

        # Возвращаем обновленный тикет
        updated_ticket = {
            "id": ticket.id,
            "description": ticket.description,
            "photo_id": ticket.photo_id,
            "response_photo_id": ticket.response_photo_id,
            "status": ticket.status.name,
            "comment": ticket.comment,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "user_id": ticket.user_id,
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name or "Имя не указано",
                "username": user.username,
                "phone": user.phone,
                "email": user.email,
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
            f"❌ Ошибка отправки фото пользователю для тикета {ticket_id}: {e}"
        )
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{ticket_id}")
async def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Удаление тикета."""
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    db.delete(ticket)
    db.commit()

    logger.info(f"🗑 Удален тикет #{ticket_id}")
    return {"message": "Ticket deleted successfully"}
