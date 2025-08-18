from datetime import date, time as time_type, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from models.models import (
    Booking,
    User,
    Tariff,
    Promocode,
    Notification,
    DatabaseManager,
)
from dependencies import get_db, verify_token, get_bot
from schemas.booking_schemas import (
    BookingBase,
    BookingCreate,
    BookingUpdate,
    BookingStats,
    BookingDetailed,
)
from config import MOSCOW_TZ
from utils.logger import get_logger
from utils.external_api import rubitime
from utils.helpers import format_phone_for_rubitime

logger = get_logger(__name__)
router = APIRouter(prefix="/bookings", tags=["bookings"])
# router = APIRouter(tags=["bookings"])


@router.get("/detailed")
async def get_bookings_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: str = Depends(verify_token),
):
    """Получение бронирований с данными тарифов и пользователей (оптимизированная версия)."""

    def _get_bookings(session):
        try:
            logger.info(
                f"Запрос бронирований: page={page}, per_page={per_page}, "
                f"user_query='{user_query}', date_query='{date_query}', status_filter='{status_filter}'"
            )

            base_query = """
                SELECT 
                    b.id, b.user_id, b.tariff_id, b.visit_date, b.visit_time,
                    b.duration, b.promocode_id, b.amount, b.payment_id, b.paid,
                    b.rubitime_id, b.confirmed, b.created_at,
                    u.telegram_id, u.full_name, u.username, u.phone, u.email,
                    t.name as tariff_name, t.price as tariff_price, 
                    t.description as tariff_description, t.purpose as tariff_purpose, t.is_active
                FROM bookings b
                LEFT JOIN users u ON b.user_id = u.id
                LEFT JOIN tariffs t ON b.tariff_id = t.id
            """

            where_conditions = []
            params = {}

            if user_query and user_query.strip():
                where_conditions.append("u.full_name LIKE :user_query")
                params["user_query"] = f"%{user_query.strip()}%"

            if date_query and date_query.strip():
                try:
                    if date_query.count("-") == 2:
                        query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                    elif date_query.count(".") == 2:
                        query_date = datetime.strptime(date_query, "%d.%m.%Y").date()
                    else:
                        raise ValueError("Unsupported date format")

                    where_conditions.append("b.visit_date = :date_query")
                    params["date_query"] = query_date.isoformat()
                except ValueError:
                    logger.error(f"Ошибка формата даты: {date_query}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid date format. Use YYYY-MM-DD or DD.MM.YYYY",
                    )

            if status_filter and status_filter.strip():
                if status_filter == "paid":
                    where_conditions.append("b.paid = 1")
                elif status_filter == "unpaid":
                    where_conditions.append("b.paid = 0")
                elif status_filter == "confirmed":
                    where_conditions.append("b.confirmed = 1")
                elif status_filter == "pending":
                    where_conditions.append("b.confirmed = 0")

            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            count_query = f"SELECT COUNT(*) FROM ({base_query}) as counted"
            total_count = session.execute(text(count_query), params).scalar()

            final_query = (
                base_query + " ORDER BY b.created_at DESC LIMIT :limit OFFSET :offset"
            )
            params["limit"] = per_page
            params["offset"] = (page - 1) * per_page

            result = session.execute(text(final_query), params).fetchall()

            enriched_bookings = []
            for row in result:
                booking_item = {
                    "id": int(row.id),
                    "user_id": int(row.user_id),
                    "tariff_id": int(row.tariff_id),
                    "visit_date": row.visit_date,
                    "visit_time": row.visit_time,
                    "duration": int(row.duration) if row.duration else None,
                    "promocode_id": int(row.promocode_id) if row.promocode_id else None,
                    "amount": float(row.amount),
                    "payment_id": row.payment_id,
                    "paid": bool(row.paid),
                    "rubitime_id": row.rubitime_id,
                    "confirmed": bool(row.confirmed),
                    "created_at": row.created_at,
                    "user": {
                        "id": row.user_id,
                        "telegram_id": row.telegram_id,
                        "full_name": row.full_name or "Имя не указано",
                        "username": row.username,
                        "phone": row.phone,
                        "email": row.email,
                    },
                    "tariff": {
                        "id": row.tariff_id,
                        "name": row.tariff_name or f"Тариф #{row.tariff_id}",
                        "price": float(row.tariff_price) if row.tariff_price else 0.0,
                        "description": row.tariff_description or "Описание недоступно",
                        "purpose": row.tariff_purpose,
                        "is_active": (
                            bool(row.is_active) if row.is_active is not None else False
                        ),
                    },
                }
                enriched_bookings.append(booking_item)

            total_pages = (total_count + per_page - 1) // per_page

            return {
                "bookings": enriched_bookings,
                "total_count": int(total_count),
                "page": int(page),
                "per_page": int(per_page),
                "total_pages": int(total_pages),
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_bookings: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_bookings)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при получении бронирований: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats")
async def get_booking_stats(_: str = Depends(verify_token)):
    """Получение статистики по бронированиям."""

    def _get_stats(session):
        try:
            total_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings")
            ).scalar()
            paid_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE paid = 1")
            ).scalar()
            confirmed_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE confirmed = 1")
            ).scalar()

            total_revenue = session.execute(
                text("SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE paid = 1")
            ).scalar()

            current_month_start = (
                datetime.now(MOSCOW_TZ)
                .replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
            )

            current_month_bookings = session.execute(
                text("SELECT COUNT(*) FROM bookings WHERE created_at >= :start_date"),
                {"start_date": current_month_start},
            ).scalar()

            current_month_revenue = session.execute(
                text(
                    "SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE created_at >= :start_date AND paid = 1"
                ),
                {"start_date": current_month_start},
            ).scalar()

            top_tariffs = session.execute(
                text(
                    """
                    SELECT t.name, COUNT(b.id) as booking_count
                    FROM tariffs t
                    JOIN bookings b ON t.id = b.tariff_id
                    GROUP BY t.id, t.name
                    ORDER BY booking_count DESC
                    LIMIT 5
                """
                )
            ).fetchall()

            return {
                "total_bookings": total_bookings,
                "paid_bookings": paid_bookings,
                "confirmed_bookings": confirmed_bookings,
                "total_revenue": float(total_revenue),
                "current_month_bookings": current_month_bookings,
                "current_month_revenue": float(current_month_revenue),
                "top_tariffs": [
                    {"name": row.name, "count": row.booking_count}
                    for row in top_tariffs
                ],
            }

        except Exception as e:
            logger.error(f"Ошибка в _get_stats: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Ошибка при получении статистики бронирований: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("", response_model=List[BookingBase])
async def get_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение списка бронирований с пагинацией и фильтрацией."""
    query = db.query(Booking).order_by(Booking.created_at.desc())

    if user_query:
        query = query.join(User).filter(User.full_name.ilike(f"%{user_query}%"))

    if date_query:
        try:
            query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
            query = query.filter(Booking.visit_date == query_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    bookings = query.offset((page - 1) * per_page).limit(per_page).all()
    return bookings


@router.post("", response_model=BookingBase)
async def create_booking(booking_data: BookingCreate):
    """Создание бронирования с улучшенной обработкой промокодов."""

    def _create_booking(session):
        logger.info(
            f"Создание бронирования: user_id={booking_data.user_id}, "
            f"tariff_id={booking_data.tariff_id}, promocode_id={booking_data.promocode_id}"
        )

        user = (
            session.query(User).filter(User.telegram_id == booking_data.user_id).first()
        )
        if not user:
            logger.error(f"Пользователь с telegram_id {booking_data.user_id} не найден")
            raise HTTPException(status_code=404, detail="User not found")

        tariff = (
            session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        )
        if not tariff:
            logger.error(f"Тариф с ID {booking_data.tariff_id} не найден")
            raise HTTPException(status_code=404, detail="Tariff not found")

        amount = booking_data.amount
        promocode = None

        if booking_data.promocode_id:
            logger.info(f"Обработка промокода ID: {booking_data.promocode_id}")

            promocode = (
                session.query(Promocode)
                .filter(Promocode.id == booking_data.promocode_id)
                .first()
            )

            if not promocode:
                logger.error(f"Промокод с ID {booking_data.promocode_id} не найден")
                raise HTTPException(status_code=404, detail="Promocode not found")

            if not promocode.is_active:
                logger.warning(f"Промокод {promocode.name} неактивен")
                raise HTTPException(status_code=400, detail="Promocode is not active")

            if promocode.expiration_date and promocode.expiration_date < datetime.now(
                MOSCOW_TZ
            ):
                logger.warning(f"Промокод {promocode.name} истек")
                raise HTTPException(status_code=410, detail="Promocode expired")

            if promocode.usage_quantity <= 0:
                logger.warning(f"Промокод {promocode.name} исчерпан")
                raise HTTPException(
                    status_code=410, detail="Promocode usage limit exceeded"
                )

            original_amount = amount
            amount = amount * (1 - promocode.discount / 100)
            logger.info(
                f"Сумма пересчитана: {original_amount} -> {amount} (скидка {promocode.discount}%)"
            )

            old_usage = promocode.usage_quantity
            promocode.usage_quantity -= 1
            logger.info(
                f"🎫 ПРОМОКОД {promocode.name}: использований было {old_usage}, стало {promocode.usage_quantity}"
            )

        booking = Booking(
            user_id=user.id,
            tariff_id=tariff.id,
            visit_date=booking_data.visit_date,
            visit_time=booking_data.visit_time,
            duration=booking_data.duration,
            promocode_id=booking_data.promocode_id,
            amount=amount,
            payment_id=booking_data.payment_id,
            paid=booking_data.paid,
            confirmed=booking_data.confirmed,
            rubitime_id=booking_data.rubitime_id,
        )

        session.add(booking)
        session.flush()

        notification = Notification(
            user_id=user.id,
            message=f"Создана новая бронь от {user.full_name or 'пользователя'}",
            target_url=f"/bookings/{booking.id}",
            booking_id=booking.id,
        )
        session.add(notification)

        if booking_data.paid:
            old_bookings = user.successful_bookings or 0
            user.successful_bookings = old_bookings + 1
            logger.info(
                f"👤 Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        logger.info(f"✅ Создано бронирование #{booking.id} с суммой {amount} ₽")

        if promocode:
            logger.info(
                f"✅ Промокод {promocode.name} успешно использован, осталось: {promocode.usage_quantity}"
            )

        booking_dict = {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date,
            "visit_time": booking.visit_time,
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),
            "payment_id": booking.payment_id,
            "paid": booking.paid,
            "rubitime_id": booking.rubitime_id,
            "confirmed": booking.confirmed,
            "created_at": booking.created_at,
        }

        return booking_dict

    try:
        return DatabaseManager.safe_execute(_create_booking)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бронирования: {e}")
        raise HTTPException(status_code=500, detail="Failed to create booking")


@router.get("/{booking_id}/validate")
async def validate_booking_id(
    booking_id: str, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Проверка существования бронирования по ID."""
    try:
        booking_id_int = int(booking_id)
        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail="Booking ID must be positive")

        booking = db.query(Booking).filter(Booking.id == booking_id_int).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        return {
            "id": booking.id,
            "exists": True,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "paid": booking.paid,
            "confirmed": booking.confirmed,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid booking ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка валидации booking ID {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Validation error")


@router.get("/{booking_id}/detailed")
async def get_booking_detailed(
    booking_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Получение детальной информации о конкретном бронировании."""
    try:
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")

        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail="Booking ID must be positive")

        booking = db.query(Booking).filter(Booking.id == booking_id_int).first()

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()
        promocode = None

        if booking.promocode_id:
            promocode = (
                db.query(Promocode).filter(Promocode.id == booking.promocode_id).first()
            )

        booking_detail = {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date.isoformat(),
            "visit_time": (
                booking.visit_time.isoformat() if booking.visit_time else None
            ),
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),
            "payment_id": booking.payment_id,
            "paid": bool(booking.paid),
            "rubitime_id": booking.rubitime_id,
            "confirmed": bool(booking.confirmed),
            "created_at": booking.created_at.isoformat(),
            "user": (
                {
                    "id": user.id if user else booking.user_id,
                    "telegram_id": user.telegram_id if user else None,
                    "full_name": user.full_name if user else "Пользователь не найден",
                    "phone": user.phone if user else None,
                    "email": user.email if user else None,
                    "username": user.username if user else None,
                    "successful_bookings": user.successful_bookings if user else 0,
                    "language_code": user.language_code if user else "ru",
                    "invited_count": user.invited_count if user else 0,
                    "reg_date": (
                        user.reg_date.isoformat() if user and user.reg_date else None
                    ),
                    "first_join_time": (
                        user.first_join_time.isoformat() if user else None
                    ),
                    "agreed_to_terms": bool(user.agreed_to_terms) if user else False,
                    "avatar": user.avatar if user else None,
                    "referrer_id": user.referrer_id if user else None,
                }
                if user
                else {
                    "id": booking.user_id,
                    "telegram_id": None,
                    "full_name": "Пользователь не найден",
                    "phone": None,
                    "email": None,
                    "username": None,
                    "successful_bookings": 0,
                    "language_code": "ru",
                    "invited_count": 0,
                    "reg_date": None,
                    "first_join_time": None,
                    "agreed_to_terms": False,
                    "avatar": None,
                    "referrer_id": None,
                }
            ),
            "tariff": (
                {
                    "id": tariff.id if tariff else booking.tariff_id,
                    "name": tariff.name if tariff else "Тариф не найден",
                    "description": (
                        tariff.description if tariff else "Описание недоступно"
                    ),
                    "price": (float(tariff.price) if tariff else 0.0),
                    "purpose": tariff.purpose if tariff else None,
                    "service_id": tariff.service_id if tariff else None,
                    "is_active": bool(tariff.is_active) if tariff else False,
                }
                if tariff
                else {
                    "id": booking.tariff_id,
                    "name": "Тариф не найден",
                    "description": "Описание недоступно",
                    "price": 0.0,
                    "purpose": None,
                    "service_id": None,
                    "is_active": False,
                }
            ),
            "promocode": (
                {
                    "id": promocode.id,
                    "name": promocode.name,
                    "discount": int(promocode.discount),
                    "usage_quantity": int(promocode.usage_quantity),
                    "expiration_date": (
                        promocode.expiration_date.isoformat()
                        if promocode.expiration_date
                        else None
                    ),
                    "is_active": bool(promocode.is_active),
                }
                if promocode
                else None
            ),
        }

        return booking_detail

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при получении детального бронирования {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение бронирования по ID."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


@router.put("/{booking_id}")
async def update_booking(
    booking_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление статуса бронирования (подтверждение/оплата)."""
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not tariff:
            raise HTTPException(status_code=404, detail="Tariff not found")

        old_confirmed = booking.confirmed
        old_paid = booking.paid

        if "confirmed" in update_data:
            booking.confirmed = update_data["confirmed"]

        if "paid" in update_data:
            booking.paid = update_data["paid"]

        # Создание записи в Rubitime при подтверждении
        if (
            "confirmed" in update_data
            and update_data["confirmed"]
            and not old_confirmed
            and not booking.rubitime_id
            and tariff.service_id
        ):

            try:
                logger.info(
                    f"Создание записи Rubitime для подтвержденной брони #{booking.id}"
                )

                formatted_phone = format_phone_for_rubitime(user.phone or "")

                if formatted_phone != "Не указано":
                    if booking.visit_time and booking.duration:
                        rubitime_date = datetime.combine(
                            booking.visit_date, booking.visit_time
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        rubitime_duration = booking.duration * 60
                    else:
                        rubitime_date = (
                            booking.visit_date.strftime("%Y-%m-%d") + " 09:00:00"
                        )
                        rubitime_duration = None

                    comment_parts = [
                        f"Подтвержденная бронь через Telegram бота - {tariff.name}"
                    ]

                    if booking.promocode_id:
                        promocode = (
                            db.query(Promocode)
                            .filter(Promocode.id == booking.promocode_id)
                            .first()
                        )
                        if promocode:
                            comment_parts.append(
                                f"Промокод: {promocode.name} (-{promocode.discount}%)"
                            )

                    if booking.duration and booking.duration > 1:
                        comment_parts.append(
                            f"Длительность: {booking.duration} час(ов)"
                        )

                    final_comment = " | ".join(comment_parts)

                    rubitime_params = {
                        "service_id": tariff.service_id,
                        "date": rubitime_date,
                        "phone": formatted_phone,
                        "name": user.full_name or "Клиент",
                        "comment": final_comment,
                        "source": "Telegram Bot Admin",
                    }

                    if rubitime_duration is not None:
                        rubitime_params["duration"] = rubitime_duration

                    if user.email and user.email.strip():
                        rubitime_params["email"] = user.email.strip()

                    logger.info(f"Параметры для Rubitime: {rubitime_params}")

                    rubitime_id = await rubitime("create_record", rubitime_params)

                    if rubitime_id:
                        booking.rubitime_id = str(rubitime_id)
                        logger.info(
                            f"✅ Создана запись Rubitime #{booking.rubitime_id} для подтвержденной брони #{booking.id}"
                        )
                    else:
                        logger.warning(
                            f"⚠️ Не удалось создать запись в Rubitime для брони #{booking.id}"
                        )

            except Exception as e:
                logger.error(
                    f"❌ Ошибка создания записи в Rubitime при подтверждении брони #{booking.id}: {e}"
                )

        # Обновление счетчика успешных бронирований
        if (
            "paid" in update_data
            and update_data["paid"]
            and not old_paid
            and tariff.purpose
            and tariff.purpose.lower() in ["опенспейс", "coworking"]
        ):
            old_bookings = user.successful_bookings or 0
            user.successful_bookings = old_bookings + 1
            logger.info(
                f"👤 Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        db.commit()
        db.refresh(booking)

        # Отправка уведомлений пользователю
        bot = get_bot()
        if bot and user.telegram_id:
            try:
                if (
                    "confirmed" in update_data
                    and update_data["confirmed"]
                    and not old_confirmed
                ):
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )
                    duration_str = f" ({booking.duration}ч)" if booking.duration else ""

                    message = f"""✅ <b>Ваша бронь подтверждена!</b>

📋 <b>Тариф:</b> {tariff.name}
📅 <b>Дата:</b> {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}{duration_str}
💰 <b>Сумма:</b> {booking.amount:.2f} ₽

💡 <b>Что дальше:</b> Ждем вас в назначенное время!"""

                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")
                    logger.info(
                        f"📤 Отправлено уведомление о подтверждении пользователю {user.telegram_id}"
                    )

                elif "paid" in update_data and update_data["paid"] and not old_paid:
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )

                    message = f"""💳 <b>Оплата зачислена!</b>

📋 <b>Тариф:</b> {tariff.name}
📅 <b>Дата:</b> {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}
💰 <b>Сумма:</b> {booking.amount:.2f} ₽

✅ Ваша оплата успешно обработана и зачислена."""

                    await bot.send_message(user.telegram_id, message, parse_mode="HTML")
                    logger.info(
                        f"📤 Отправлено уведомление об оплате пользователю {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"❌ Не удалось отправить уведомление пользователю {user.telegram_id}: {e}"
                )

        return {
            "id": booking.id,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "visit_date": booking.visit_date.isoformat(),
            "visit_time": (
                booking.visit_time.isoformat() if booking.visit_time else None
            ),
            "duration": booking.duration,
            "promocode_id": booking.promocode_id,
            "amount": float(booking.amount),
            "payment_id": booking.payment_id,
            "paid": bool(booking.paid),
            "rubitime_id": booking.rubitime_id,
            "confirmed": bool(booking.confirmed),
            "created_at": booking.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка обновления бронирования {booking_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{booking_id}")
async def delete_booking(
    booking_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление бронирования."""
    booking = db.query(Booking).get(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    db.delete(booking)
    db.commit()
    return {"message": "Booking deleted"}
