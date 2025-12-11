from datetime import date, time as time_type, datetime
from typing import List, Optional
import csv
import io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text, or_, func

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
from routes.cache import invalidate_dashboard_cache
from schemas.booking_schemas import (
    BookingBase,
    BookingCreate,
    BookingUpdate,
    BookingStats,
    BookingDetailed,
)
from config import MOSCOW_TZ
from utils.logger import get_logger
from utils.external_api import rubitime, update_rubitime_booking, create_yookassa_payment
from utils.helpers import format_phone_for_rubitime
from utils.cache_manager import cache_manager
from utils.sql_optimization import SQLOptimizer
from utils.cache_invalidation import cache_invalidator
from utils.notifications import send_booking_update_notification
# from utils.bot_instance import get_bot_instance
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = get_logger(__name__)
router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("/detailed")
async def get_bookings_detailed(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=1000),
    user_query: Optional[str] = None,
    date_query: Optional[str] = None,
    status_filter: Optional[str] = None,
    tariff_filter: Optional[str] = None,
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
):
    """Получение бронирований с данными тарифов и пользователей (оптимизированная версия)."""

    def _get_bookings(session):
        try:
            logger.info(
                f"Запрос бронирований: page={page}, per_page={per_page}, "
                f"user_query='{user_query}', date_query='{date_query}', status_filter='{status_filter}', tariff_filter='{tariff_filter}'"
            )
            
            # Логируем обработку поискового запроса
            if user_query and user_query.strip():
                query_stripped = user_query.strip()
                if query_stripped.isdigit():
                    logger.info(f"Поиск по ID бронирования: {query_stripped}")
                else:
                    query_lower = query_stripped.lower()
                    query_upper = query_stripped.upper()
                    query_title = query_stripped.capitalize()
                    logger.info(f"Текстовый поиск - оригинал: '{query_stripped}', нижний: '{query_lower}', верхний: '{query_upper}', заглавный: '{query_title}'")

            # Построение ORM query с eager loading (исправлен P-HIGH-3: миграция raw SQL на ORM)
            query = session.query(Booking).options(
                joinedload(Booking.user),
                joinedload(Booking.tariff)
            )

            # Применение фильтров
            if user_query and user_query.strip():
                query_stripped = user_query.strip()
                if query_stripped.isdigit():
                    # Поиск по ID бронирования
                    query = query.filter(Booking.id == int(query_stripped))
                else:
                    # Поиск по имени пользователя или названию тарифа (регистронезависимо)
                    # func.lower() работает с кириллицей в SQLite
                    search_pattern = f"%{query_stripped.lower()}%"
                    query = query.join(User).join(Tariff).filter(
                        or_(
                            func.lower(User.full_name).like(search_pattern),
                            func.lower(Tariff.name).like(search_pattern)
                        )
                    )

            if date_query and date_query.strip():
                try:
                    if date_query.count("-") == 2:
                        query_date = datetime.strptime(date_query, "%Y-%m-%d").date()
                    elif date_query.count(".") == 2:
                        query_date = datetime.strptime(date_query, "%d.%m.%Y").date()
                    else:
                        raise ValueError("Unsupported date format")

                    query = query.filter(Booking.visit_date == query_date)
                except ValueError:
                    logger.error(f"Ошибка формата даты: {date_query}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Неверный формат даты '{date_query}'. Используйте формат YYYY-MM-DD или DD.MM.YYYY",
                    )

            if status_filter and status_filter.strip():
                if status_filter == "paid":
                    query = query.filter(Booking.paid == True)
                elif status_filter == "unpaid":
                    query = query.filter(Booking.paid == False)
                elif status_filter == "confirmed":
                    query = query.filter(Booking.confirmed == True)
                elif status_filter == "pending":
                    query = query.filter(Booking.confirmed == False)

            if tariff_filter and tariff_filter.strip() and tariff_filter != "all":
                try:
                    tariff_id = int(tariff_filter)
                    query = query.filter(Booking.tariff_id == tariff_id)
                except ValueError:
                    logger.warning(f"Invalid tariff_filter format: {tariff_filter}")
                    # Игнорируем некорректный фильтр

            # Подсчет общего количества записей
            total_count = query.count()

            # Применение сортировки и пагинации
            bookings = query.order_by(Booking.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

            # Формирование ответа (упрощено благодаря ORM)
            enriched_bookings = []
            for booking in bookings:
                booking_item = {
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
                    "user": {
                        "id": booking.user.id,
                        "telegram_id": booking.user.telegram_id,
                        "full_name": booking.user.full_name or "Имя не указано",
                        "username": booking.user.username,
                        "phone": booking.user.phone,
                        "email": booking.user.email,
                    },
                    "tariff": {
                        "id": booking.tariff.id,
                        "name": booking.tariff.name or f"Тариф #{booking.tariff.id}",
                        "price": float(booking.tariff.price) if booking.tariff.price else 0.0,
                        "description": booking.tariff.description or "Описание недоступно",
                        "purpose": booking.tariff.purpose,
                        "is_active": booking.tariff.is_active if booking.tariff.is_active is not None else False,
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
        raise HTTPException(status_code=500, detail="Не удалось загрузить список бронирований. Попробуйте перезагрузить страницу")


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
        raise HTTPException(status_code=500, detail="Не удалось загрузить статистику бронирований. Проверьте подключение к базе данных")


@router.get("", response_model=List[BookingBase])
async def get_bookings(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=1000),
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
            raise HTTPException(status_code=400, detail=f"Неверный формат даты '{date_query}'. Используйте формат YYYY-MM-DD")

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
            raise HTTPException(status_code=404, detail=f"Пользователь с Telegram ID {booking_data.user_id} не найден в системе")

        tariff = (
            session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        )
        if not tariff:
            logger.error(f"Тариф с ID {booking_data.tariff_id} не найден")
            raise HTTPException(status_code=404, detail=f"Тариф с ID {booking_data.tariff_id} не найден в системе")

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
                raise HTTPException(status_code=404, detail=f"Промокод с ID {booking_data.promocode_id} не найден в системе")

            if not promocode.is_active:
                logger.warning(f"Промокод {promocode.name} неактивен")
                raise HTTPException(status_code=400, detail=f"Промокод неактивен и не может быть использован")

            if promocode.expiration_date and promocode.expiration_date < datetime.now(
                MOSCOW_TZ
            ):
                logger.warning(f"Промокод {promocode.name} истек")
                raise HTTPException(status_code=410, detail=f"Срок действия промокода истек")

            if promocode.usage_quantity <= 0:
                logger.warning(f"Промокод {promocode.name} исчерпан")
                raise HTTPException(
                    status_code=410, detail=f"Промокод исчерпан, все использования закончились"
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

        # Создание записи в Rubitime при подтверждении
        if booking_data.confirmed:
            try:
                from utils.helpers import format_phone_for_rubitime
                from utils.external_api import rubitime
                from datetime import datetime

                logger.info(f"[ADMIN BOOKING] Бронирование подтверждено, проверка создания записи в Rubitime для брони #{result['id']}")

                # Получаем данные user и tariff для проверки service_id
                def _get_rubitime_data(session):
                    user = session.query(User).filter(User.telegram_id == booking_data.user_id).first()
                    tariff = session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
                    promocode = None
                    if booking_data.promocode_id:
                        promocode = session.query(Promocode).filter(Promocode.id == booking_data.promocode_id).first()
                    return user, tariff, promocode

                user, tariff, promocode = DatabaseManager.safe_execute(_get_rubitime_data)

                logger.info(f"[ADMIN BOOKING] User: {user.id if user else None}, Tariff: {tariff.id if tariff else None}, service_id: {tariff.service_id if tariff else None}")

                if not tariff:
                    logger.warning(f"[ADMIN BOOKING] Тариф не найден, пропускаем создание в Rubitime")
                elif not tariff.service_id:
                    logger.warning(f"[ADMIN BOOKING] У тарифа {tariff.id} нет service_id, пропускаем создание в Rubitime")
                elif tariff and tariff.service_id:
                    logger.info(
                        f"Создание записи Rubitime для подтвержденной брони #{result['id']} (создание админом)"
                    )

                    formatted_phone = format_phone_for_rubitime(user.phone or "")

                    if formatted_phone != "Не указано":
                        # Форматирование даты и времени для Rubitime
                        if result.get("visit_time") and result.get("duration"):
                            # Парсим visit_time если это строка
                            if isinstance(result["visit_time"], str):
                                from datetime import time
                                hour, minute = map(int, result["visit_time"].split(":"))
                                visit_time_obj = time(hour, minute)
                            else:
                                visit_time_obj = result["visit_time"]

                            rubitime_date = datetime.combine(
                                result["visit_date"], visit_time_obj
                            ).strftime("%Y-%m-%d %H:%M:%S")
                            rubitime_duration = result["duration"] * 60
                        else:
                            rubitime_date = (
                                result["visit_date"].strftime("%Y-%m-%d") + " 09:00:00"
                            )
                            rubitime_duration = None

                        # Формирование комментария
                        comment_parts = [
                            f"Подтвержденная бронь через админ панель - {tariff.name}"
                        ]

                        if promocode:
                            comment_parts.append(
                                f"Промокод: {promocode.name} (-{promocode.discount}%)"
                            )

                        if result.get("duration") and result["duration"] > 1:
                            comment_parts.append(
                                f"Длительность: {result['duration']} час(ов)"
                            )

                        final_comment = " | ".join(comment_parts)

                        # Параметры для создания записи в Rubitime
                        rubitime_params = {
                            "service_id": tariff.service_id,
                            "date": rubitime_date,
                            "phone": formatted_phone,
                            "name": user.full_name or "Клиент",
                            "comment": final_comment,
                            "source": "Admin Panel",
                        }

                        if rubitime_duration is not None:
                            rubitime_params["duration"] = rubitime_duration

                        if user.email and user.email.strip():
                            rubitime_params["email"] = user.email.strip()

                        logger.info(f"Параметры для Rubitime: {rubitime_params}")

                        rubitime_id = await rubitime("create_record", rubitime_params)

                        if rubitime_id:
                            # Обновляем rubitime_id в базе данных
                            def _update_rubitime_id(session):
                                booking = session.query(Booking).filter(Booking.id == result["id"]).first()
                                if booking:
                                    booking.rubitime_id = str(rubitime_id)
                                    session.commit()

                            DatabaseManager.safe_execute(_update_rubitime_id)

                            # Обновляем result dict для возврата
                            result["rubitime_id"] = str(rubitime_id)

                            logger.info(
                                f"Создана запись Rubitime #{rubitime_id} для брони #{result['id']}"
                            )
                        else:
                            logger.warning(
                                f"Не удалось создать запись в Rubitime для брони #{result['id']}"
                            )
                    else:
                        logger.warning(
                            f"Не удалось создать запись в Rubitime: некорректный телефон для брони #{result['id']}"
                        )

            except Exception as e:
                logger.error(
                    f"Ошибка создания записи в Rubitime при создании брони #{result.get('id', 'unknown')}: {e}"
                )

        # Отправка уведомления пользователю если бронирование подтверждено
        if booking_data.confirmed:
            try:
                from utils.bot_instance import get_bot

                logger.info(f"[ADMIN BOOKING] Попытка отправки уведомления для подтвержденной брони #{result['id']}")

                bot = get_bot()
                logger.info(f"[ADMIN BOOKING] Bot instance: {bot is not None}")

                if bot:
                    # Получаем данные для уведомления
                    def _get_user_and_tariff(session):
                        user = session.query(User).filter(User.telegram_id == booking_data.user_id).first()
                        tariff = session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
                        return user, tariff

                    user, tariff = DatabaseManager.safe_execute(_get_user_and_tariff)

                    logger.info(f"[ADMIN BOOKING] User for notification: {user.id if user else None}, telegram_id: {user.telegram_id if user else None}")
                    logger.info(f"[ADMIN BOOKING] Tariff for notification: {tariff.id if tariff else None}")

                    if user and user.telegram_id and tariff:
                        logger.info(
                            f"Отправка уведомления о создании подтвержденной брони пользователю {user.telegram_id}"
                        )

                        # Форматирование времени и длительности
                        visit_time_str = ""
                        if result.get("visit_time"):
                            try:
                                # result["visit_time"] может быть строкой или time объектом
                                if isinstance(result["visit_time"], str):
                                    from datetime import time
                                    hour, minute = map(int, result["visit_time"].split(":"))
                                    time_obj = time(hour, minute)
                                    visit_time_str = f" в {time_obj.strftime('%H:%M')}"
                                else:
                                    visit_time_str = f" в {result['visit_time'].strftime('%H:%M')}"
                            except:
                                pass

                        duration_str = ""
                        if result.get("duration"):
                            duration_str = f" ({result['duration']}ч)"

                        # Форматирование даты
                        visit_date_str = result["visit_date"]
                        if hasattr(result["visit_date"], "strftime"):
                            visit_date_str = result["visit_date"].strftime('%d.%m.%Y')

                        # Формирование сообщения
                        message = f"""Ваша бронь подтверждена!

Тариф: {tariff.name}
Дата: {visit_date_str}{visit_time_str}{duration_str}
Сумма: {result['amount']:.2f} ₽

Ждем вас в назначенное время!"""

                        # Отправка уведомления
                        await bot.send_message(user.telegram_id, message)

                        logger.info(
                            f"✅ [ADMIN BOOKING] Уведомление о подтвержденной брони успешно отправлено пользователю {user.telegram_id}"
                        )
                    else:
                        logger.warning(f"[ADMIN BOOKING] Не удалось отправить уведомление: user={user is not None}, telegram_id={user.telegram_id if user else None}, tariff={tariff is not None}")
                else:
                    logger.warning(f"[ADMIN BOOKING] Bot instance не получен, уведомление не отправлено")

            except Exception as e:
                # Ошибка отправки уведомления не должна блокировать создание брони
                logger.error(f"❌ [ADMIN BOOKING] Ошибка отправки уведомления о созд брони: {e}", exc_info=True)

        # Инвалидируем связанные кэши после успешного создания
        await cache_invalidator.invalidate_booking_related_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания бронирования из ТГ бота: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать бронирование. Проверьте корректность данных и попробуйте позже")


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
            raise HTTPException(status_code=404, detail=f"Пользователь с Telegram ID {booking_data.user_id} не найден в системе")

        tariff = (
            session.query(Tariff).filter(Tariff.id == booking_data.tariff_id).first()
        )
        if not tariff:
            logger.error(f"Тариф с ID {booking_data.tariff_id} не найден")
            raise HTTPException(status_code=404, detail=f"Тариф с ID {booking_data.tariff_id} не найден в системе")

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
                raise HTTPException(status_code=404, detail=f"Промокод с ID {booking_data.promocode_id} не найден в системе")

            if not promocode.is_active:
                logger.warning(f"Промокод {promocode.name} неактивен")
                raise HTTPException(status_code=400, detail=f"Промокод неактивен и не может быть использован")

            if promocode.expiration_date and promocode.expiration_date < datetime.now(
                MOSCOW_TZ
            ):
                logger.warning(f"Промокод {promocode.name} истек")
                raise HTTPException(status_code=410, detail=f"Срок действия промокода истек")

            if promocode.usage_quantity <= 0:
                logger.warning(f"Промокод {promocode.name} исчерпан")
                raise HTTPException(
                    status_code=410, detail=f"Промокод исчерпан, все использования закончились"
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
        raise HTTPException(status_code=500, detail="Не удалось создать бронирование. Проверьте корректность данных и попробуйте позже")


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
            raise HTTPException(status_code=400, detail=f"ID бронирования должен быть положительным числом")

        booking = db.query(Booking).filter(Booking.id == booking_id_int).first()

        if not booking:
            raise HTTPException(status_code=404, detail=f"Бронирование не найдено в системе")

        return {
            "id": booking.id,
            "exists": True,
            "user_id": booking.user_id,
            "tariff_id": booking.tariff_id,
            "paid": booking.paid,
            "confirmed": booking.confirmed,
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неверный формат ID бронирования. Ожидается числовое значение")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка валидации booking ID {booking_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка валидации ID бронирования. Попробуйте позже")


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
            raise HTTPException(status_code=400, detail=f"Неверный формат ID бронирования: '{booking_id}'. Ожидается числовое значение")

        if booking_id_int <= 0:
            raise HTTPException(status_code=400, detail=f"ID бронирования должен быть положительным числом, получено: {booking_id_int}")

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
            raise HTTPException(status_code=404, detail=f"Бронирование не найдено в системе")

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
        raise HTTPException(status_code=500, detail=f"Не удалось загрузить информацию о бронировании #{booking_id}. Проверьте подключение к базе данных")


@router.get("/{booking_id}", response_model=BookingBase)
async def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
):
    """Получение бронирования по ID."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail=f"Бронирование #{booking_id} не найдено в системе")
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
            raise HTTPException(status_code=404, detail=f"Бронирование #{booking_id} не найдено в системе")

        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

        if not user:
            raise HTTPException(status_code=404, detail=f"Пользователь с ID {booking.user_id} не найден")
        if not tariff:
            raise HTTPException(status_code=404, detail=f"Тариф с ID {booking.tariff_id} не найден")

        old_confirmed = booking.confirmed
        old_paid = booking.paid

        logger.info(
            f"Обновление бронирования #{booking_id} администратором {current_admin.login}: {update_data}"
        )

        if "confirmed" in update_data:
            booking.confirmed = update_data["confirmed"]

        if "paid" in update_data:
            booking.paid = update_data["paid"]

        if "amount" in update_data:
            booking.amount = update_data["amount"]

        # Создание записи в Rubitime при подтверждении
        if (
            "confirmed" in update_data
            and update_data["confirmed"]
            and not old_confirmed
            and not booking.rubitime_id
            and tariff.service_id
        ):

            try:
                from utils.helpers import format_phone_for_rubitime
                from utils.external_api import rubitime
                from datetime import datetime

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

                elif (
                    "confirmed" in update_data
                    and not update_data["confirmed"]
                    and old_confirmed
                ):
                    visit_time_str = (
                        f" в {booking.visit_time.strftime('%H:%M')}"
                        if booking.visit_time
                        else ""
                    )
                    duration_str = f" ({booking.duration}ч)" if booking.duration else ""

                    message = f"""Ваша бронь была отменена

Тариф: {tariff.name}
Дата: {booking.visit_date.strftime('%d.%m.%Y')}{visit_time_str}{duration_str}

Если у вас есть вопросы, пожалуйста, свяжитесь с администрацией."""

                    await bot.send_message(user.telegram_id, message)
                    logger.info(
                        f"Отправлено уведомление об отмене бронирования пользователю {user.telegram_id}"
                    )

            except Exception as e:
                logger.error(
                    f"Не удалось отправить уведомление пользователю {user.telegram_id}: {e}"
                )

        # Удаление записи из Rubitime при отмене бронирования
        if (
            "confirmed" in update_data
            and not update_data["confirmed"]
            and old_confirmed
            and booking.rubitime_id
        ):
            try:
                from utils.external_api import rubitime

                logger.info(
                    f"Отмена подтверждения брони #{booking.id}, удаление из Rubitime #{booking.rubitime_id}"
                )

                result = await rubitime("delete_record", {"record_id": booking.rubitime_id})

                if result == "404":
                    logger.warning(
                        f"Запись Rubitime #{booking.rubitime_id} не найдена при отмене (404)"
                    )
                elif result:
                    logger.info(
                        f"Запись Rubitime #{booking.rubitime_id} удалена при отмене брони"
                    )
                    # Очищаем rubitime_id в базе данных
                    booking.rubitime_id = None
                    db.commit()
                else:
                    logger.warning(
                        f"Не удалось удалить запись Rubitime #{booking.rubitime_id} при отмене"
                    )

            except Exception as e:
                logger.error(
                    f"Ошибка удаления Rubitime #{booking.rubitime_id} при отмене: {e}"
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
        raise HTTPException(status_code=500, detail=f"Не удалось обновить бронирование #{booking_id}. Попробуйте позже")


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
            raise HTTPException(status_code=404, detail=f"Бронирование #{booking_id} не найдено в системе")

        # Получаем информацию о пользователе и тарифе для логирования
        user = db.query(User).filter(User.id == booking.user_id).first()
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

        booking_info = {
            "id": booking.id,
            "user_id": booking.user_id,
            "user_name": user.full_name if user else f"User ID {booking.user_id}",
            "user_telegram_id": user.telegram_id if user else None,
            "tariff_name": tariff.name if tariff else f"Tariff ID {booking.tariff_id}",
            "amount": float(booking.amount),
            "paid": booking.paid,
            "confirmed": booking.confirmed,
            "visit_date": (
                booking.visit_date.isoformat() if booking.visit_date else None
            ),
            "rubitime_id": booking.rubitime_id,
        }

        # Попытка удаления записи из Rubitime если есть rubitime_id
        rubitime_delete_status = None
        if booking.rubitime_id:
            try:
                from utils.external_api import rubitime

                logger.info(
                    f"Попытка удаления записи Rubitime #{booking.rubitime_id} для брони #{booking.id}"
                )

                result = await rubitime("delete_record", {"record_id": booking.rubitime_id})

                if result == "404":
                    # Запись не найдена в Rubitime - это предупреждение, но не ошибка
                    logger.warning(
                        f"Запись Rubitime #{booking.rubitime_id} не найдена (404), продолжаем удаление из БД"
                    )
                    rubitime_delete_status = "not_found"
                elif result:
                    logger.info(
                        f"Запись Rubitime #{booking.rubitime_id} успешно удалена"
                    )
                    rubitime_delete_status = "success"
                else:
                    logger.warning(
                        f"Не удалось удалить запись Rubitime #{booking.rubitime_id}, но продолжаем удаление из БД"
                    )
                    rubitime_delete_status = "error"

            except Exception as e:
                logger.error(
                    f"Ошибка удаления записи Rubitime #{booking.rubitime_id}: {e}"
                )
                rubitime_delete_status = "exception"

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

        # При удалении бронирования уведомление НЕ отправляется
        # (по требованию задачи - при удалении не уведомлять пользователя)
        logger.info(f"Бронирование #{booking_id} удалено без уведомления пользователя")

        # Инвалидируем связанные кэши после успешного удаления
        await cache_invalidator.invalidate_booking_related_cache()

        response = {
            "message": "Бронирование удалено",
            "booking_id": booking_info["id"],
            "user_id": booking_info["user_id"],
            "tariff_name": booking_info["tariff_name"],
            "visit_date": booking_info["visit_date"],
            "amount": booking_info["amount"],
        }

        # Добавляем информацию о статусе удаления из Rubitime
        if booking_info.get("rubitime_id"):
            response["rubitime_status"] = rubitime_delete_status
            response["rubitime_id"] = booking_info["rubitime_id"]

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления бронирования {booking_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Не удалось удалить бронирование #{booking_id}. Попробуйте позже")


@router.post("/bulk-delete")
async def bulk_delete_bookings(
    booking_ids: List[int],
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.DELETE_BOOKINGS])
    ),
):
    """Массовое удаление бронирований."""
    try:
        if not booking_ids:
            raise HTTPException(status_code=400, detail="Список бронирований пуст")

        logger.info(f"Начало массового удаления {len(booking_ids)} бронирований")

        # Получаем все бронирования для удаления
        bookings = db.query(Booking).filter(Booking.id.in_(booking_ids)).all()

        if not bookings:
            raise HTTPException(status_code=404, detail="Бронирования не найдены")

        deleted_count = 0
        notifications_deleted = 0

        for booking in bookings:
            # Удаляем связанные уведомления
            notifications = db.query(Notification).filter(
                Notification.booking_id == booking.id
            ).all()
            for notification in notifications:
                db.delete(notification)
                notifications_deleted += 1

            # Удаляем бронирование
            db.delete(booking)
            deleted_count += 1

        db.commit()

        # Инвалидируем кэши
        await cache_invalidator.invalidate_booking_related_cache()

        logger.info(f"Массово удалено {deleted_count} бронирований и {notifications_deleted} уведомлений")

        return {
            "message": f"Успешно удалено {deleted_count} бронирований",
            "deleted_count": deleted_count,
            "deleted_notifications": notifications_deleted
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка массового удаления бронирований: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось удалить бронирования")


@router.post("/bulk-cancel")
async def bulk_cancel_bookings(
    booking_ids: List[int],
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.EDIT_BOOKINGS])
    ),
):
    """Массовая отмена бронирований (установка статуса подтверждения в False)."""
    try:
        if not booking_ids:
            raise HTTPException(status_code=400, detail="Список бронирований пуст")

        logger.info(f"Начало массовой отмены {len(booking_ids)} бронирований")

        # Получаем все бронирования для отмены
        bookings = db.query(Booking).filter(Booking.id.in_(booking_ids)).all()

        if not bookings:
            raise HTTPException(status_code=404, detail="Бронирования не найдены")

        cancelled_count = 0

        for booking in bookings:
            # Отменяем бронирование (снимаем подтверждение)
            if booking.confirmed:
                booking.confirmed = False
                cancelled_count += 1

        db.commit()

        # Инвалидируем кэши
        await cache_invalidator.invalidate_booking_related_cache()

        logger.info(f"Массово отменено {cancelled_count} бронирований")

        return {
            "message": f"Успешно отменено {cancelled_count} бронирований",
            "cancelled_count": cancelled_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка массовой отмены бронирований: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось отменить бронирования")


@router.post("/bulk-export")
async def bulk_export_bookings(
    booking_ids: List[int],
    db: Session = Depends(get_db),
    _: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_BOOKINGS])),
):
    """Массовый экспорт выбранных бронирований в CSV файл."""
    try:
        if not booking_ids:
            raise HTTPException(status_code=400, detail="Список бронирований пуст")

        logger.info(f"Начало массового экспорта {len(booking_ids)} бронирований")

        # Получаем бронирования с joinedload для оптимизации
        bookings = db.query(Booking).options(
            joinedload(Booking.user),
            joinedload(Booking.tariff)
        ).filter(Booking.id.in_(booking_ids)).all()

        if not bookings:
            raise HTTPException(status_code=404, detail="Бронирования не найдены")

        # Создаем CSV в памяти
        output = io.StringIO()
        output.write('\ufeff')  # UTF-8 BOM

        fieldnames = [
            'ID', 'Пользователь', 'Telegram ID', 'Тариф', 'Дата визита',
            'Время начала', 'Время окончания', 'Сумма', 'Оплачено',
            'Подтверждено', 'Промокод', 'Дата создания', 'Комментарий'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for booking in bookings:
            writer.writerow({
                'ID': booking.id,
                'Пользователь': booking.user.full_name if booking.user else f'User ID {booking.user_id}',
                'Telegram ID': booking.user.telegram_id if booking.user else '',
                'Тариф': booking.tariff.name if booking.tariff else f'Tariff ID {booking.tariff_id}',
                'Дата визита': booking.visit_date.strftime('%d.%m.%Y') if booking.visit_date else '',
                'Время начала': booking.time_start.strftime('%H:%M') if booking.time_start else '',
                'Время окончания': booking.time_end.strftime('%H:%M') if booking.time_end else '',
                'Сумма': f'{booking.amount:.2f}',
                'Оплачено': 'Да' if booking.paid else 'Нет',
                'Подтверждено': 'Да' if booking.confirmed else 'Нет',
                'Промокод': booking.promocode_used or '',
                'Дата создания': booking.created_at.strftime('%d.%m.%Y %H:%M') if booking.created_at else '',
                'Комментарий': booking.comment or ''
            })

        output.seek(0)

        filename = f"bookings_bulk_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        logger.info(f"Массово экспортировано {len(bookings)} бронирований в файл {filename}")

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка массового экспорта бронирований: {e}")
        raise HTTPException(status_code=500, detail="Не удалось экспортировать бронирования")


@router.post("/{booking_id}/recalculate")
async def recalculate_booking_amount(
    booking_id: int,
    data: dict,  # visit_date, visit_time, duration
    db: Session = Depends(get_db),
    _: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.VIEW_BOOKINGS])
    ),
):
    """
    Пересчитывает сумму бронирования с учетом новых параметров и скидок.

    Логика расчета:
    1. Получить тариф и его цену
    2. Базовая сумма = price * duration (или просто price для опенспейса)
    3. Применить скидку промокода (если был использован)
    4. Применить скидку 10% если duration >= 3 часа
    5. Вернуть финальную сумму
    """
    try:
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Бронирование не найдено")

        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()
        if not tariff:
            raise HTTPException(status_code=404, detail="Тариф не найден")

        # Получить параметры (используем новые значения или текущие)
        duration = data.get("duration", booking.duration)

        # Базовая сумма
        if duration:
            base_amount = tariff.price * duration
        else:
            base_amount = tariff.price

        # Собираем скидки
        total_discount = 0

        # Скидка промокода (если был)
        if booking.promocode_id:
            promocode = db.query(Promocode).filter(
                Promocode.id == booking.promocode_id
            ).first()
            if promocode:
                total_discount += promocode.discount

        # Скидка за длительность (3+ часов)
        if duration and duration >= 3:
            total_discount += 10

        # Максимум 100%
        total_discount = min(100, total_discount)

        # Финальная сумма
        final_amount = base_amount * (1 - total_discount / 100)

        logger.info(
            f"Recalculated booking {booking_id}: base={base_amount}, "
            f"discount={total_discount}%, final={final_amount}"
        )

        return {
            "amount": round(final_amount, 2),
            "base_amount": round(base_amount, 2),
            "discount": total_discount,
            "duration": duration
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка пересчета суммы бронирования {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось пересчитать сумму")


@router.put("/{booking_id}/full")
async def update_booking_full(
    booking_id: int,
    update_data: dict,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.EDIT_BOOKINGS])
    ),
):
    """
    Полное обновление бронирования с изменением даты, времени, длительности и суммы.

    Если бронирование подтверждено и есть rubitime_id:
    - Обновить запись в Rubitime CRM
    """
    try:
        def _update(session):
            booking = session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                raise HTTPException(status_code=404, detail="Бронирование не найдено")

            # Сохранить старые значения для логирования
            old_values = {
                "visit_date": booking.visit_date,
                "visit_time": booking.visit_time,
                "duration": booking.duration,
                "amount": booking.amount
            }

            # Обновить поля
            if "visit_date" in update_data:
                # Конвертировать строку в date если нужно
                if isinstance(update_data["visit_date"], str):
                    from datetime import datetime
                    booking.visit_date = datetime.strptime(update_data["visit_date"], "%Y-%m-%d").date()
                else:
                    booking.visit_date = update_data["visit_date"]

            if "visit_time" in update_data:
                # Конвертировать строку в time если нужно
                if isinstance(update_data["visit_time"], str):
                    from datetime import datetime
                    booking.visit_time = datetime.strptime(update_data["visit_time"], "%H:%M:%S").time()
                else:
                    booking.visit_time = update_data["visit_time"]

            if "duration" in update_data:
                booking.duration = update_data["duration"]

            if "amount" in update_data:
                booking.amount = update_data["amount"]

            session.commit()

            # Получить тариф для Rubitime
            tariff = session.query(Tariff).filter(Tariff.id == booking.tariff_id).first()

            return booking, tariff, old_values

        updated_booking, tariff, old_values = DatabaseManager.safe_execute(_update)

        # Если подтверждено и есть rubitime_id - обновить в Rubitime
        if updated_booking.confirmed and updated_booking.rubitime_id:
            try:
                if tariff and tariff.service_id:
                    update_rubitime_booking(
                        rubitime_id=updated_booking.rubitime_id,
                        service_id=tariff.service_id,
                        visit_date=updated_booking.visit_date,
                        visit_time=updated_booking.visit_time,
                        duration=updated_booking.duration
                    )
                    logger.info(f"Rubitime booking {updated_booking.rubitime_id} updated successfully")
            except Exception as e:
                logger.error(f"Ошибка обновления Rubitime: {e}")

        # Логирование изменений
        logger.info(
            # f"Booking {booking_id} updated by admin {current_admin.username}: "
            f"OLD: {old_values} -> NEW: visit_date={updated_booking.visit_date}, "
            f"visit_time={updated_booking.visit_time}, duration={updated_booking.duration}, "
            f"amount={updated_booking.amount}"
        )

        # Инвалидация кэша
        await invalidate_dashboard_cache()

        # Отправить уведомление пользователю о изменении брони (только если бронь подтверждена)
        try:
            if updated_booking.confirmed:
                user = db.query(User).filter(User.id == updated_booking.user_id).first()
                if user and user.telegram_id:
                    # Подготовить данные для уведомления
                    booking_data = {
                        "visit_date": updated_booking.visit_date,
                        "visit_time": updated_booking.visit_time,
                        "duration": updated_booking.duration,
                        "amount": updated_booking.amount
                    }
                    tariff_data = {
                        "name": tariff.name if tariff else "Неизвестно"
                    }
                    await send_booking_update_notification(user.telegram_id, booking_data, tariff_data)
                    logger.info(f"Update notification sent to user {user.telegram_id}")
            else:
                logger.info(f"Booking {booking_id} is not confirmed, notification not sent")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

        # Сериализация ответа
        booking_dict = {
            "id": updated_booking.id,
            "user_id": updated_booking.user_id,
            "tariff_id": updated_booking.tariff_id,
            "visit_date": updated_booking.visit_date.isoformat() if updated_booking.visit_date else None,
            "visit_time": updated_booking.visit_time.isoformat() if updated_booking.visit_time else None,
            "duration": updated_booking.duration,
            "amount": updated_booking.amount,
            "confirmed": updated_booking.confirmed,
            "paid": updated_booking.paid,
            "payment_id": updated_booking.payment_id,
            "rubitime_id": updated_booking.rubitime_id
        }

        return {"success": True, "booking": booking_dict}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления бронирования {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить бронирование")


@router.post("/{booking_id}/send-payment-link")
async def send_payment_link(
    booking_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(
        verify_token_with_permissions([Permission.EDIT_BOOKINGS])
    ),
):
    """
    Создает платеж в YooKassa и отправляет ссылку пользователю в Telegram.

    Условия:
    - Бронирование должно быть подтверждено (confirmed=True)
    - Бронирование не должно быть оплачено (paid=False)
    - Тариф должен быть meeting_room
    """
    try:
        # Получить бронирование с тарифом и пользователем
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Бронирование не найдено")

        if not booking.confirmed:
            raise HTTPException(
                status_code=400,
                detail="Бронирование должно быть подтверждено перед отправкой ссылки"
            )

        if booking.paid:
            raise HTTPException(
                status_code=400,
                detail="Бронирование уже оплачено"
            )

        # Проверка что это переговорная
        tariff = db.query(Tariff).filter(Tariff.id == booking.tariff_id).first()
        if not tariff:
            raise HTTPException(status_code=404, detail="Тариф не найден")

        if tariff.purpose not in ["meeting_room", "переговорная", "meeting"]:
            raise HTTPException(
                status_code=400,
                detail="Платежные ссылки доступны только для переговорных"
            )

        # Получить пользователя
        user = db.query(User).filter(User.id == booking.user_id).first()
        if not user or not user.telegram_id:
            raise HTTPException(
                status_code=400,
                detail="У пользователя нет Telegram ID"
            )

        # Создать платеж в YooKassa
        try:
            payment_data = {
                "user_id": user.telegram_id,
                "amount": booking.amount,
                "description": f"Оплата бронирования: {tariff.name}",
            }

            payment_result = await create_yookassa_payment(payment_data)

            if not payment_result or not payment_result.get("payment_id"):
                raise Exception("Не удалось создать платеж")

            payment_id = payment_result["payment_id"]
            confirmation_url = payment_result["confirmation_url"]

            # Сохранить payment_id в бронировании
            booking.payment_id = payment_id
            db.commit()

            logger.info(f"Payment created for booking {booking_id}: payment_id={payment_id}")

        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка создания платежа: {str(e)}"
            )

        # Отправить ссылку пользователю в Telegram
        try:
            # bot = get_bot_instance()
            bot = get_bot()
            # Форматирование даты и времени
            date_str = booking.visit_date.strftime('%d.%m.%Y') if booking.visit_date else "Не указано"
            time_str = ""
            if booking.visit_time:
                time_str = f"\n🕐 <b>Время:</b> {booking.visit_time.strftime('%H:%M')}"

            duration_str = ""
            if booking.duration:
                duration_str = f"\n⏱ <b>Длительность:</b> {booking.duration} ч."

            # Форматирование сообщения
            message_text = f"""💳 <b>Ссылка на оплату бронирования</b>

📋 <b>Тариф:</b> {tariff.name}
📅 <b>Дата:</b> {date_str}{time_str}{duration_str}

💰 <b>Сумма к оплате:</b> {booking.amount:.0f} ₽

👇 Нажмите кнопку ниже для оплаты:"""

            # Создать клавиатуру с кнопкой оплаты
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить {booking.amount:.0f} ₽",
                    url=confirmation_url
                )]
            ])

            await bot.send_message(
                chat_id=user.telegram_id,
                text=message_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )

            logger.info(
                f"Payment link sent to user {user.telegram_id} for booking {booking_id} "
                # f"by admin {current_admin.username}"
            )

            return {
                "success": True,
                "payment_id": payment_id,
                "message": f"Ссылка на оплату отправлена пользователю {user.full_name}"
            }

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка отправки сообщения: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки платежной ссылки для бронирования {booking_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось отправить платежную ссылку")
