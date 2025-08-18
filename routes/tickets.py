# from schemas.ticket_schemas import TicketCreate
# from datetime import datetime
# from typing import List, Optional
# from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
# from sqlalchemy.orm import Session
# from sqlalchemy import text
# from pydantic import BaseModel
#
# from models.models import Ticket, User, TicketStatus, Notification, DatabaseManager
# from dependencies import get_db, verify_token, get_bot
# from config import MOSCOW_TZ
# from utils.logger import get_logger
#
# logger = get_logger(__name__)
# router = APIRouter(prefix="/tickets", tags=["tickets"])
#
#
# @router.get("/detailed")
# async def get_tickets_detailed(
#     page: int = Query(1, ge=1),
#     per_page: int = Query(20, ge=1, le=100),
#     status: Optional[str] = None,
#     user_query: Optional[str] = None,
#     _: str = Depends(verify_token),
# ):
#     """Получение тикетов с данными пользователей и фильтрацией."""
#
#     def _get_tickets(session):
#         try:
#             base_query = """
#                 SELECT
#                     t.id, t.user_id, t.description, t.photo_id, t.response_photo_id,
#                     t.status, t.comment, t.created_at, t.updated_at,
#                     u.telegram_id, u.full_name, u.username, u.phone, u.email
#                 FROM tickets t
#                 LEFT JOIN users u ON t.user_id = u.id
#             """
#
#             where_conditions = []
#             params = {}
#
#             if user_query and user_query.strip():
#                 where_conditions.append("u.full_name LIKE :user_query")
#                 params["user_query"] = f"%{user_query.strip()}%"
#
#             if status and status.strip():
#                 where_conditions.append("t.status = :status")
#                 params["status"] = status.strip()
#
#             if where_conditions:
#                 base_query += " WHERE " + " AND ".join(where_conditions)
#
#             count_query = f"SELECT COUNT(*) FROM ({base_query}) as counted"
#             total_count = session.execute(text(count_query), params).scalar()
#
#             final_query = (
#                 base_query + " ORDER BY t.created_at DESC LIMIT :limit OFFSET :offset"
#             )
#             params["limit"] = per_page
#             params["offset"] = (page - 1) * per_page
#
#             result = session.execute(text(final_query), params).fetchall()
#
#             enriched_tickets = []
#             for row in result:
#                 ticket_item = {
#                     "id": int(row.id),
#                     "user_id": int(row.user_id),
#                     "description": row.description,
#                     "photo_id": row.photo_id,
#                     "response_photo_id": row.response_photo_id,
#                     "status": row.status,
#                     "comment": row.comment,
#                     "created_at": row.created_at,
#                     "updated_at": row.updated_at,
#                     "user": {
#                         "id": row.user_id,
#                         "telegram_id": row.telegram_id,
#                         "full_name": row.full_name or "Имя не указано",
#                         "username": row.username,
#                         "phone": row.phone,
#                         "email": row.email,
#                     },
#                 }
#                 enriched_tickets.append(ticket_item)
#
#             total_pages = (total_count + per_page - 1) // per_page
#
#             return {
#                 "tickets": enriched_tickets,
#                 "total_count": int(total_count),
#                 "page": int(page),
#                 "per_page": int(per_page),
#                 "total_pages": int(total_pages),
#             }
#
#         except Exception as e:
#             logger.error(f"Ошибка в _get_tickets: {e}")
#             raise
#
#     try:
#         return DatabaseManager.safe_execute(_get_tickets)
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Критическая ошибка при получении тикетов: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")
#
#
# @router.get("/stats")
# async def get_tickets_stats(_: str = Depends(verify_token)):
#     """Получение статистики по тикетам."""
#
#     def _get_stats(session):
#         total_tickets = session.execute(text("SELECT COUNT(*) FROM tickets")).scalar()
#         open_tickets = session.execute(
#             text("SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'")
#         ).scalar()
#         in_progress_tickets = session.execute(
#             text("SELECT COUNT(*) FROM tickets WHERE status = 'IN_PROGRESS'")
#         ).scalar()
#         closed_tickets = session.execute(
#             text("SELECT COUNT(*) FROM tickets WHERE status = 'CLOSED'")
#         ).scalar()
#
#         return {
#             "total_tickets": total_tickets,
#             "open_tickets": open_tickets,
#             "in_progress_tickets": in_progress_tickets,
#             "closed_tickets": closed_tickets,
#             "avg_response_time": 0,  # Можно добавить реальную логику
#         }
#
#     try:
#         return DatabaseManager.safe_execute(_get_stats)
#     except Exception as e:
#         logger.error(f"Ошибка при получении статистики тикетов: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")
#
#
# @router.post("")
# async def create_ticket(ticket_data: TicketCreate, db: Session = Depends(get_db)):
#     """Создание нового тикета. Используется ботом."""
#     user = db.query(User).filter(User.telegram_id == ticket_data.user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     status_enum = TicketStatus.OPEN
#     if ticket_data.status:
#         try:
#             status_enum = TicketStatus(ticket_data.status)
#         except ValueError:
#             status_enum = TicketStatus.OPEN
#
#     ticket = Ticket(
#         user_id=user.id,
#         description=ticket_data.description,
#         photo_id=ticket_data.photo_id,
#         status=status_enum,
#         comment=ticket_data.comment,
#         created_at=datetime.now(MOSCOW_TZ),
#         updated_at=datetime.now(MOSCOW_TZ),
#     )
#
#     db.add(ticket)
#     db.commit()
#     db.refresh(ticket)
#
#     return {"id": ticket.id, "message": "Ticket created successfully"}
#
#
# @router.get("/users/telegram/{telegram_id}/tickets")
# async def get_user_tickets_by_telegram_id(
#     telegram_id: int, status: Optional[str] = Query(None), db: Session = Depends(get_db)
# ):
#     """Получение тикетов пользователя по его Telegram ID."""
#     try:
#         user = db.query(User).filter(User.telegram_id == telegram_id).first()
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
#
#         query = (
#             db.query(Ticket)
#             .filter(Ticket.user_id == user.id)
#             .order_by(Ticket.created_at.desc())
#         )
#
#         if status:
#             try:
#                 status_enum = TicketStatus[status]
#                 query = query.filter(Ticket.status == status_enum)
#             except KeyError:
#                 raise HTTPException(status_code=400, detail="Invalid status")
#
#         tickets = query.all()
#
#         result = []
#         for ticket in tickets:
#             result.append(
#                 {
#                     "id": ticket.id,
#                     "description": ticket.description,
#                     "photo_id": ticket.photo_id,
#                     "response_photo_id": ticket.response_photo_id,
#                     "status": ticket.status.name,
#                     "comment": ticket.comment,
#                     "created_at": ticket.created_at.isoformat(),
#                     "updated_at": ticket.updated_at.isoformat(),
#                     "user_id": ticket.user_id,
#                 }
#             )
#
#         return result
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Ошибка при получении тикетов пользователя {telegram_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")
#
#
# @router.put("/{ticket_id}")
# async def update_ticket(
#     ticket_id: int,
#     update_data: dict,
#     db: Session = Depends(get_db),
#     _: str = Depends(verify_token),
# ):
#     """Обновление тикета (статус, комментарий)."""
#     try:
#         ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
#         if not ticket:
#             raise HTTPException(status_code=404, detail="Ticket not found")
#
#         user = db.query(User).filter(User.id == ticket.user_id).first()
#
#         old_status = ticket.status
#         old_comment = ticket.comment
#
#         if "status" in update_data:
#             try:
#                 new_status = TicketStatus[update_data["status"]]
#                 ticket.status = new_status
#             except KeyError:
#                 raise HTTPException(status_code=400, detail="Invalid status")
#
#         if "comment" in update_data:
#             ticket.comment = update_data["comment"]
#
#         if "response_photo_id" in update_data:
#             ticket.response_photo_id = update_data["response_photo_id"]
#
#         ticket.updated_at = datetime.now(MOSCOW_TZ)
#
#         db.commit()
#         db.refresh(ticket)
#
#         # Отправка уведомления пользователю
#         bot = get_bot()
#         if bot and user and user.telegram_id and not update_data.get("photo_sent"):
#             try:
#                 status_changed = old_status != ticket.status
#                 comment_changed = ticket.comment and ticket.comment != old_comment
#
#                 if status_changed or comment_changed:
#                     status_messages = {
#                         TicketStatus.OPEN: "📋 Ваша заявка получена и находится в обработке",
#                         TicketStatus.IN_PROGRESS: "⚙️ Ваша заявка взята в работу",
#                         TicketStatus.CLOSED: "✅ Ваша заявка решена",
#                     }
#
#                     message = f"🎫 <b>Обновление по заявке #{ticket.id}</b>\n\n"
#
#                     if status_changed:
#                         message += status_messages.get(
#                             ticket.status, f"Статус: {ticket.status.name}"
#                         )
#
#                     if comment_changed:
#                         message += f"\n\n💬 <b>Комментарий администратора:</b>\n{ticket.comment}"
#
#                     from utils.external_api import send_telegram_notification
#
#                     await send_telegram_notification(bot, user.telegram_id, message)
#
#             except Exception as e:
#                 logger.error(
#                     f"❌ Ошибка отправки уведомления о тикете #{ticket.id}: {e}"
#                 )
#
#         return {
#             "id": ticket.id,
#             "description": ticket.description,
#             "photo_id": ticket.photo_id,
#             "response_photo_id": ticket.response_photo_id,
#             "status": ticket.status.name,
#             "comment": ticket.comment,
#             "created_at": ticket.created_at.isoformat(),
#             "updated_at": ticket.updated_at.isoformat(),
#         }
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"❌ Ошибка обновления тикета {ticket_id}: {e}")
#         db.rollback()
#         raise HTTPException(status_code=500, detail="Internal server error")

# routes/tickets.py - ИСПРАВЛЕННЫЙ
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from models.models import Ticket, User, TicketStatus, Notification, DatabaseManager
from dependencies import get_db, verify_token, get_bot
from config import MOSCOW_TZ
from schemas.ticket_schemas import TicketCreate
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tickets", tags=["tickets"])


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
    """Обновление тикета (статус, комментарий)."""
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        user = db.query(User).filter(User.id == ticket.user_id).first()

        old_status = ticket.status
        old_comment = ticket.comment

        if "status" in update_data:
            try:
                new_status = TicketStatus[update_data["status"]]
                ticket.status = new_status
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid status")

        if "comment" in update_data:
            ticket.comment = update_data["comment"]

        if "response_photo_id" in update_data:
            ticket.response_photo_id = update_data["response_photo_id"]

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
