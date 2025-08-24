from datetime import date, time as time_type, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text

from models.models import (
    Booking,
    User,
    Tariff,
    Promocode,
    Notification,
    DatabaseManager,
    Permission,
)
from dependencies import (
    get_db,
    verify_token,
    verify_token_with_permissions,
    get_bot,
    CachedAdmin,
)
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
from utils.cache_manager import cache_manager
from utils.sql_optimization import SQLOptimizer
from utils.cache_invalidation import cache_invalidator

logger = get_logger(__name__)
router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/detailed")
async def get_bookings_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
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
                # Проверяем, является ли запрос числом (ID бронирования)
                query_stripped = user_query.strip()
                if query_stripped.isdigit():
                    # Поиск по ID бронирования
                    where_conditions.append("b.id = :booking_id")
                    params["booking_id"] = int(query_stripped)
                else:
                    # Поиск по имени пользователя
                    where_conditions.append("u.full_name LIKE :user_query")
                    params["user_query"] = f"%{query_stripped}%"

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
async def get_booking_stats(
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
):
    """Получение статистики по бронированиям с кэшированием."""

    cache_key = cache_manager.get_cache_key("bookings", "stats")
    
    def _get_stats():
        def _db_query(session):
            return SQLOptimizer.get_optimized_bookings_stats(session)
        return DatabaseManager.safe_execute(_db_query)

    try:
        # Используем кэш с TTL для дашборда
        return await cache_manager.get_or_set(
            cache_key, 
            _get_stats, 
            ttl=cache_manager.dashboard_ttl
        )
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
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
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


@router.post("/admin", response_model=BookingBase)
async def create_booking_admin(
    booking_data: BookingCreate,
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.CREATE_BOOKINGS])
    ),
):
    """Создание бронирования администратором с улучшенной обработкой промокодов."""

    def _create_booking(session):
        logger.info(
            f"Создание бронирования администратором {current_admin.login}: "
            f"user_id={booking_data.user_id}, tariff_id={booking_data.tariff_id}, "
            f"promocode_id={booking_data.promocode_id}"
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
                f"ПРОМОКОД {promocode.name}: использований было {old_usage}, стало {promocode.usage_quantity}"
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
                f"Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        logger.info(
            f"Создано бронирование #{booking.id} с суммой {amount} ₽ из ТГ бота"
        )

        if promocode:
            logger.info(
                f"Промокод {promocode.name} успешно использован, осталось: {promocode.usage_quantity}"
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
        result = DatabaseManager.safe_execute(_create_booking)
        # Инвалидируем связанные кэши после успешного создания
        await cache_invalidator.invalidate_booking_related_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бронирования из ТГ бота: {e}")
        raise HTTPException(status_code=500, detail="Failed to create booking")


@router.post("", response_model=BookingBase)
async def create_booking(booking_data: BookingCreate):
    """Создание бронирования из Telegram бота с улучшенной обработкой промокодов."""

    def _create_booking(session):
        logger.info(
            f"Создание бронирования из ТГ бота: "
            f"user_id={booking_data.user_id}, tariff_id={booking_data.tariff_id}, "
            f"promocode_id={booking_data.promocode_id}"
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
                f"ПРОМОКОД {promocode.name}: использований было {old_usage}, стало {promocode.usage_quantity}"
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
                f"Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
            )

        logger.info(f"Создано бронирование #{booking.id} с суммой {amount} ₽")

        if promocode:
            logger.info(
                f"Промокод {promocode.name} успешно использован, осталось: {promocode.usage_quantity}"
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
        result = DatabaseManager.safe_execute(_create_booking)
        # Инвалидируем связанные кэши после успешного создания
        await cache_invalidator.invalidate_booking_related_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бронирования: {e}")
        raise HTTPException(status_code=500, detail="Failed to create booking")


@router.get("/{booking_id}/validate")
async def validate_booking_id(
    booking_id: str,
    db: Session = Depends(get_db),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
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
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
):
    """Получение детальной информации о конкретном бронировании."""
    try:
        try:
            booking_id_int = int(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")

        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail="Booking ID must be positive")

        # Используем eager loading для избежания N+1 query проблемы
        booking = (
            db.query(Booking)
            .options(
                joinedload(Booking.user),
                joinedload(Booking.tariff),
                joinedload(Booking.promocode)
            )
            .filter(Booking.id == booking_id_int)
            .first()
        )

        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        user = booking.user
        tariff = booking.tariff
        promocode = booking.promocode

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
    booking_id: int,
    db: Session = Depends(get_db),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
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
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.EDIT_BOOKINGS])
    ),
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

        logger.info(
            f"Обновление бронирования #{booking_id} администратором {current_admin.login}: {update_data}"
        )

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
                            f"Создана запись Rubitime #{booking.rubitime_id} для подтвержденной брони #{booking.id}"
                        )
                    else:
                        logger.warning(
                            f"Не удалось создать запись в Rubitime для брони #{booking.id}"
                        )

            except Exception as e:
                logger.error(
                    f"Ошибка создания записи в Rubitime при подтверждении брони #{booking.id}: {e}"
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
                f"Счетчик бронирований пользователя {user.telegram_id}: {old_bookings} -> {user.successful_bookings}"
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

                    message = f"""Ваша бронь подтверждена!

Тариф: {tariff.name}
Дата: {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}{duration_str}
Сумма: {booking.amount:.2f} ₽

Ждем вас в назначенное время!"""

                    await bot.send_message(user.telegram_id, message)
                    logger.info(
                        f"Отправлено уведомление о подтверждении пользователю {user.telegram_id}"
                    )

                elif "paid" in update_data and update_data["paid"] and not old_paid:
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )

                    message = f"""Оплата зачислена!

Тариф: {tariff.name}
Дата: {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}
Сумма: {booking.amount:.2f} ₽

Ваша оплата успешно обработана и зачислена."""

                    await bot.send_message(user.telegram_id, message)
                    logger.info(
                        f"Отправлено уведомление об оплате пользователю {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}"
                )

        logger.info(
            f"Бронирование #{booking_id} обновлено администратором {current_admin.login}"
        )

        # Инвалидируем связанные кэши после успешного обновления
        await cache_invalidator.invalidate_booking_related_cache()

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
        logger.error(f"Ошибка обновления бронирования {booking_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{booking_id}")
async def delete_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.DELETE_BOOKINGS])
    ),
):
    """Удаление бронирования."""
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")

        # Получаем информацию о пользователе и тарифе для логирования
        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

        booking_info = {
            "id": booking.id,
            "user_name": user.full_name if user else f"User ID {booking.user_id}",
            "user_telegram_id": user.telegram_id if user else None,
            "tariff_name": tariff.name if tariff else f"Tariff ID {booking.tariff_id}",
            "amount": float(booking.amount),
            "paid": booking.paid,
            "confirmed": booking.confirmed,
            "visit_date": (
                booking.visit_date.isoformat() if booking.visit_date else None
            ),
        }

        # Попытка удаления записи из Rubitime если есть rubitime_id
        if booking.rubitime_id:
            try:
                logger.info(
                    f"Попытка удаления записи Rubitime #{booking.rubitime_id} для брони #{booking.id}"
                )
                # Здесь можно добавить вызов API Rubitime для удаления записи
                # result = await rubitime("delete_record", {"record_id": booking.rubitime_id})
                logger.info(
                    f"Запись Rubitime #{booking.rubitime_id} должна быть удалена вручную"
                )
            except Exception as e:
                logger.warning(
                    f"Не удалось удалить запись Rubitime #{booking.rubitime_id}: {e}"
                )

        # Удаляем связанные уведомления
        notifications_deleted = (
            db.query(Notification)
            .filter(Notification.booking_id == booking.id)
            .delete(synchronize_session=False)
        )

        # Удаляем само бронирование
        db.delete(booking)
        db.commit()

        logger.info(
            f"Бронирование #{booking.id} удалено администратором {current_admin.login}. "
            f"Пользователь: {booking_info['user_name']}, Тариф: {booking_info['tariff_name']}, "
            f"Сумма: {booking_info['amount']} ₽. Удалено уведомлений: {notifications_deleted}"
        )

        # Отправляем уведомление пользователю об удалении брони
        if user and user.telegram_id:
            bot = get_bot()
            if bot:
                try:
                    message = f"""Ваше бронирование было отменено

Тариф: {booking_info['tariff_name']}
Дата: {booking_info['visit_date']}
Сумма: {booking_info['amount']:.2f} ₽

По вопросам обращайтесь к администратору."""

                    await bot.send_message(user.telegram_id, message)
                    logger.info(
                        f"Отправлено уведомление об удалении брони пользователю {user.telegram_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Не удалось отправить уведомление об удалении брони: {e}"
                    )

        # Инвалидируем связанные кэши после успешного удаления
        await cache_invalidator.invalidate_booking_related_cache()

        return {
            "message": "Booking deleted successfully",
            "deleted_booking": booking_info,
            "deleted_notifications": notifications_deleted,
            "rubitime_notice": (
                f"Rubitime record #{booking.rubitime_id} should be deleted manually"
                if booking.rubitime_id
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления бронирования {booking_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete booking")
