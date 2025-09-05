from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from fastapi import HTTPException
from models.models import DatabaseManager
from dependencies import verify_token
from utils.logger import get_logger
from utils.sql_optimization import SQLOptimizer
from utils.cache_manager import cache_manager
from datetime import datetime, timedelta
from typing import Optional
import calendar

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(_: str = Depends(verify_token)):
    """Получение общей статистики для дашборда с кэшированием."""

    cache_key = cache_manager.get_cache_key("dashboard", "stats")

    def _get_stats():
        def _db_query(session):
            return SQLOptimizer.get_optimized_dashboard_stats(session)

        return DatabaseManager.safe_execute(_db_query)

    try:
        # Используем кэш с TTL для дашборда
        return await cache_manager.get_or_set(
            cache_key, _get_stats, ttl=cache_manager.dashboard_ttl
        )
    except Exception as e:
        logger.error(f"Ошибка в get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")


@router.get("/chart-data")
async def get_chart_data(
    year: int = Query(default_factory=lambda: datetime.now().year),
    month: int = Query(default_factory=lambda: datetime.now().month),
    _: str = Depends(verify_token),
):
    """Получение данных для графика по дням выбранного месяца с кэшированием."""

    cache_key = cache_manager.get_cache_key("dashboard", "chart_data", year, month)

    def _get_chart_data():
        def _db_query(session):
            try:
                # Проверяем корректность месяца и года
                if month < 1 or month > 12:
                    raise ValueError("Month must be between 1 and 12")

                if year < 2020 or year > datetime.now().year + 1:
                    raise ValueError("Invalid year")

                # Получаем количество дней в месяце
                days_in_month = calendar.monthrange(year, month)[1]

                # Инициализируем массивы для каждого дня месяца
                user_registrations = [0] * days_in_month
                ticket_creations = [0] * days_in_month
                booking_creations = [0] * days_in_month

                # Форматируем параметры для SQLite
                year_str = str(year)
                month_str = f"{month:02d}"

                # Запрос для регистраций пользователей (SQLite)
                user_query = text(
                    """
                    SELECT
                        CAST(strftime('%d', COALESCE(reg_date, first_join_time)) AS INTEGER) as day,
                        COUNT(*) as count
                    FROM users
                    WHERE
                        (reg_date IS NOT NULL AND strftime('%Y', reg_date) = :year AND strftime('%m', reg_date) = :month_str)
                       OR
                        (reg_date IS NULL AND first_join_time IS NOT NULL AND strftime('%Y', first_join_time) = :year AND strftime('%m', first_join_time) = :month_str)
                    GROUP BY CAST(strftime('%d', COALESCE(reg_date, first_join_time)) AS INTEGER)
                    """
                )

                user_results = session.execute(
                    user_query, {"year": year_str, "month_str": month_str}
                ).fetchall()
                for row in user_results:
                    if row.day and 1 <= row.day <= days_in_month:
                        user_registrations[row.day - 1] = row.count

                # Запрос для создания тикетов (SQLite)
                ticket_query = text(
                    """
                    SELECT
                        CAST(strftime('%d', created_at) AS INTEGER) as day,
                        COUNT(*) as count
                    FROM tickets
                    WHERE strftime('%Y', created_at) = :year AND strftime('%m', created_at) = :month_str
                    GROUP BY CAST(strftime('%d', created_at) AS INTEGER)
                    """
                )

                ticket_results = session.execute(
                    ticket_query, {"year": year_str, "month_str": month_str}
                ).fetchall()
                for row in ticket_results:
                    if row.day and 1 <= row.day <= days_in_month:
                        ticket_creations[row.day - 1] = row.count

                # Запрос для бронирований (SQLite)
                booking_query = text(
                    """
                    SELECT
                        CAST(strftime('%d', created_at) AS INTEGER) as day,
                        COUNT(*) as count
                    FROM bookings
                    WHERE strftime('%Y', created_at) = :year AND strftime('%m', created_at) = :month_str
                    GROUP BY CAST(strftime('%d', created_at) AS INTEGER)
                    """
                )

                booking_results = session.execute(
                    booking_query, {"year": year_str, "month_str": month_str}
                ).fetchall()
                for row in booking_results:
                    if row.day and 1 <= row.day <= days_in_month:
                        booking_creations[row.day - 1] = row.count

                # Создаем метки для дней месяца
                day_labels = [str(i) for i in range(1, days_in_month + 1)]

                # Получаем название месяца на русском
                month_names = {
                    1: "Январь",
                    2: "Февраль",
                    3: "Март",
                    4: "Апрель",
                    5: "Май",
                    6: "Июнь",
                    7: "Июль",
                    8: "Август",
                    9: "Сентябрь",
                    10: "Октябрь",
                    11: "Ноябрь",
                    12: "Декабрь",
                }

                return {
                    "labels": day_labels,
                    "datasets": {
                        "user_registrations": user_registrations,
                        "ticket_creations": ticket_creations,
                        "booking_creations": booking_creations,
                    },
                    "period": {
                        "year": year,
                        "month": month,
                        "month_name": month_names[month],
                        "days_in_month": days_in_month,
                    },
                    "totals": {
                        "users": sum(user_registrations),
                        "tickets": sum(ticket_creations),
                        "bookings": sum(booking_creations),
                    },
                }

            except ValueError as e:
                logger.error(f"Ошибка валидации параметров: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Ошибка в запросе данных графика: {e}")
                raise

        return DatabaseManager.safe_execute(_db_query)

    try:
        # Используем кэш с более длинным TTL для исторических данных
        return await cache_manager.get_or_set(
            cache_key,
            _get_chart_data,
            ttl=cache_manager.static_data_ttl,  # 30 минут для исторических данных
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка в get_chart_data: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных графика")


@router.get("/available-periods")
async def get_available_periods(_: str = Depends(verify_token)):
    """Получение доступных периодов для выбора (месяцы с данными) с кэшированием."""

    cache_key = cache_manager.get_cache_key("dashboard", "available_periods")

    def _get_periods():
        def _db_query(session):
            try:
                # Получаем диапазон дат с данными (SQLite)
                date_ranges_query = text(
                    """
                    SELECT
                        MIN(date_col) as min_date,
                        MAX(date_col) as max_date
                    FROM (
                             SELECT COALESCE(reg_date, first_join_time) as date_col FROM users WHERE COALESCE(reg_date, first_join_time) IS NOT NULL
                             UNION ALL
                             SELECT created_at as date_col FROM tickets WHERE created_at IS NOT NULL
                             UNION ALL
                             SELECT created_at as date_col FROM bookings WHERE created_at IS NOT NULL
                         ) as all_dates
                    """
                )

                result = session.execute(date_ranges_query).fetchone()

                # Всегда возвращаем 12 месяцев (текущий + 11 предыдущих)
                current_date = datetime.now()
                periods = []
                
                month_names = {
                    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
                    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
                    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
                }
                
                # Генерируем 12 месяцев: текущий + 11 предыдущих
                for i in range(12):
                    # Вычисляем месяц и год
                    target_month = current_date.month - i
                    target_year = current_date.year
                    
                    # Корректируем если месяц стал отрицательным
                    while target_month <= 0:
                        target_month += 12
                        target_year -= 1
                    
                    periods.append({
                        "year": target_year,
                        "month": target_month,
                        "display": f"{month_names[target_month]} {target_year}",
                    })
                
                if not result or not result.min_date:
                    return {
                        "periods": periods,
                        "current": {
                            "year": current_date.year,
                            "month": current_date.month,
                        },
                    }

                # В SQLite результат может быть строкой, нужно парсить
                def parse_date(date_val):
                    if isinstance(date_val, str):
                        try:
                            # Пробуем разные форматы
                            if "T" in date_val:
                                return datetime.fromisoformat(
                                    date_val.replace("Z", "+00:00")
                                )
                            else:
                                return datetime.strptime(
                                    date_val[:19], "%Y-%m-%d %H:%M:%S"
                                )
                        except:
                            return datetime.now()
                    return date_val

                # Используем уже созданный список periods (12 месяцев)
                # Текущий период  
                now = datetime.now()
                current_period = {"year": now.year, "month": now.month}

                return {"periods": periods, "current": current_period}

            except Exception as e:
                logger.error(f"Ошибка получения доступных периодов: {e}")
                raise

        return DatabaseManager.safe_execute(_db_query)

    try:
        # Периоды меняются редко, кэшируем на 30 минут
        return await cache_manager.get_or_set(
            cache_key, _get_periods, ttl=cache_manager.static_data_ttl
        )
    except Exception as e:
        logger.error(f"Критическая ошибка в get_available_periods: {e}")
        raise HTTPException(
            status_code=500, detail="Ошибка получения доступных периодов"
        )


@router.get("/bookings-calendar")
async def get_bookings_calendar(
    year: int = Query(default_factory=lambda: datetime.now().year),
    month: int = Query(default_factory=lambda: datetime.now().month),
    _: str = Depends(verify_token),
):
    """Получение данных бронирований для календаря."""

    cache_key = cache_manager.get_cache_key("dashboard", "bookings_calendar", year, month)

    def _get_bookings_data():
        def _db_query(session):
            try:
                # Валидация входных параметров
                if not (1 <= month <= 12):
                    raise ValueError(f"Недопустимый месяц: {month}")
                if not (2000 <= year <= 9999):
                    raise ValueError(f"Недопустимый год: {year}")

                year_str = str(year).zfill(4)
                month_str = str(month).zfill(2)

                # Запрос бронирований за месяц с данными пользователя
                bookings_query = text(
                    """
                    SELECT 
                        b.id,
                        b.visit_date,
                        b.visit_time,
                        b.confirmed,
                        b.paid,
                        b.amount,
                        u.full_name as user_name,
                        u.telegram_id,
                        t.name as tariff_name
                    FROM bookings b
                    LEFT JOIN users u ON b.user_id = u.id
                    LEFT JOIN tariffs t ON b.tariff_id = t.id
                    WHERE strftime('%Y', b.visit_date) = :year 
                      AND strftime('%m', b.visit_date) = :month_str
                    ORDER BY b.visit_date, b.visit_time
                    """
                )

                results = session.execute(
                    bookings_query, {"year": year_str, "month_str": month_str}
                ).fetchall()

                bookings = []
                for row in results:
                    # Форматируем данные бронирования
                    booking = {
                        "id": row.id,
                        "visit_date": row.visit_date.isoformat() if hasattr(row.visit_date, 'isoformat') else str(row.visit_date),
                        "visit_time": str(row.visit_time) if row.visit_time else None,
                        "confirmed": bool(row.confirmed),
                        "paid": bool(row.paid),
                        "amount": float(row.amount) if row.amount else 0,
                        "user_name": row.user_name,
                        "telegram_id": row.telegram_id,
                        "tariff_name": row.tariff_name
                    }
                    bookings.append(booking)

                return {
                    "bookings": bookings,
                    "period": {
                        "year": year,
                        "month": month,
                        "total_bookings": len(bookings)
                    }
                }

            except ValueError as e:
                logger.error(f"Ошибка валидации параметров календаря: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Ошибка в запросе данных календаря: {e}")
                raise

        return DatabaseManager.safe_execute(_db_query)

    try:
        # Кэшируем данные календаря
        return await cache_manager.get_or_set(
            cache_key,
            _get_bookings_data,
            ttl=cache_manager.dashboard_ttl,  # 5 минут
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка в get_bookings_calendar: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения данных календаря")
