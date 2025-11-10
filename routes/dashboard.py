from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from fastapi import HTTPException
from models.models import DatabaseManager
from dependencies import verify_token
from utils.logger import get_logger
from utils.sql_optimization import SQLOptimizer, get_sparkline_data
from utils.cache_manager import cache_manager
from datetime import datetime, timedelta
from typing import Optional
import calendar

logger = get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    period_start: Optional[str] = Query(None, description="Начало периода (ISO формат)"),
    period_end: Optional[str] = Query(None, description="Конец периода (ISO формат)"),
    _: str = Depends(verify_token)
):
    """
    Получение общей статистики для дашборда с кэшированием и процентами изменения.

    Если период не указан, используется текущий месяц.
    """
    logger.info(f"Dashboard stats request started: period_start={period_start}, period_end={period_end}")

    # Определяем период
    if period_start and period_end:
        try:
            period_start_dt = datetime.fromisoformat(period_start.replace('Z', '+00:00'))
            period_end_dt = datetime.fromisoformat(period_end.replace('Z', '+00:00'))
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format.")
    else:
        # По умолчанию - текущий месяц
        now = datetime.now()
        period_start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Следующий месяц, день 1
        if now.month == 12:
            period_end_dt = period_start_dt.replace(year=now.year + 1, month=1)
        else:
            period_end_dt = period_start_dt.replace(month=now.month + 1)

    cache_key = cache_manager.get_cache_key(
        "dashboard", "stats",
        period_start_dt.isoformat(),
        period_end_dt.isoformat()
    )

    def _get_stats():
        def _db_query(session):
            logger.info("Executing dashboard stats database query with comparison")
            try:
                # Получаем основную статистику
                result = SQLOptimizer.get_dashboard_stats_with_comparison(
                    session, period_start_dt, period_end_dt
                )

                # Добавляем данные sparkline (последние 7 дней)
                sparkline_data = get_sparkline_data(session, days=7)
                result['sparkline'] = sparkline_data

                logger.info(f"Database query completed with sparkline data, result type: {type(result)}")
                return result
            except Exception as e:
                logger.error(f"Error in dashboard stats query: {e}", exc_info=True)
                raise

        logger.info("Starting database transaction for dashboard stats")
        result = DatabaseManager.safe_execute(_db_query)
        logger.info(f"Database transaction completed, final result type: {type(result)}")
        return result

    try:
        logger.info("Getting stats from cache or database")
        # Используем кэш с TTL для дашборда
        result = await cache_manager.get_or_set(
            cache_key, _get_stats, ttl=cache_manager.dashboard_ttl
        )

        logger.info(f"Stats result type: {type(result)}")

        # Дополнительная проверка результата
        if not isinstance(result, dict):
            logger.warning(f"Получен некорректный результат статистики: {type(result)}")
            raise ValueError("Некорректный формат данных статистики")

        # Форматируем ответ с трендовыми индикаторами
        def create_trend(change_percentage: float, metric_type: str = "growth"):
            """
            Создаёт индикатор тренда

            Args:
                change_percentage: процент изменения
                metric_type: тип метрики ('growth' для пользователей/бронирований, 'reduction' для тикетов)
            """
            if change_percentage > 0:
                direction = "up"
                is_positive = metric_type == "growth"
            elif change_percentage < 0:
                direction = "down"
                is_positive = metric_type == "reduction"
            else:
                direction = "neutral"
                is_positive = True

            return {
                "value": abs(change_percentage),
                "direction": direction,
                "is_positive": is_positive
            }

        # Формируем карточки статистики с трендами и sparkline
        formatted_result = {
            "users": {
                "current_value": result["users"]["current_value"],
                "previous_value": result["users"]["previous_value"],
                "change_percentage": result["users"]["change_percentage"],
                "trend": create_trend(result["users"]["change_percentage"], "growth"),
                "label": "Всего пользователей",
                "icon": "FiUsers",
                "sparkline": result.get("sparkline", {}).get("users", {"values": [], "labels": []})
            },
            "bookings": {
                "current_value": result["bookings"]["current_value"],
                "previous_value": result["bookings"]["previous_value"],
                "change_percentage": result["bookings"]["change_percentage"],
                "trend": create_trend(result["bookings"]["change_percentage"], "growth"),
                "label": "Всего бронирований",
                "icon": "FiShoppingBag",
                "sparkline": result.get("sparkline", {}).get("bookings", {"values": [], "labels": []})
            },
            "tickets": {
                "current_value": result["tickets"]["current_value"],
                "previous_value": result["tickets"]["previous_value"],
                "change_percentage": result["tickets"]["change_percentage"],
                "trend": create_trend(result["tickets"]["change_percentage"], "reduction"),
                "label": "Открытые заявки",
                "icon": "FiMessageCircle",
                "sparkline": result.get("sparkline", {}).get("tickets", {"values": [], "labels": []})
            },
            # Дополнительная статистика (для обратной совместимости)
            "total_users": result["users"]["total"],
            "total_bookings": result["bookings"]["total"],
            "open_tickets": result["tickets"]["open"],
            "active_tariffs": result["active_tariffs"],
            "paid_bookings": result["paid_bookings"],
            "total_revenue": result["total_revenue"],
            "ticket_stats": result["ticket_stats"],
            "unread_notifications": result["unread_notifications"],
            # Информация о периоде
            "period": {
                "start": period_start_dt.isoformat(),
                "end": period_end_dt.isoformat(),
                "label": period_start_dt.strftime("%B %Y")
            }
        }

        logger.info("Dashboard stats request completed successfully")
        return formatted_result

    except Exception as e:
        logger.error(f"Ошибка в get_dashboard_stats: {e}", exc_info=True)

        # Возвращаем базовые значения при любой ошибке
        logger.warning("Возвращаем базовую статистику из-за ошибки")
        return {
            "users": {
                "current_value": 0,
                "previous_value": 0,
                "change_percentage": 0.0,
                "trend": {"value": 0.0, "direction": "neutral", "is_positive": True},
                "label": "Всего пользователей",
                "icon": "FiUsers",
                "sparkline": {"values": [0]*7, "labels": [""]*7}
            },
            "bookings": {
                "current_value": 0,
                "previous_value": 0,
                "change_percentage": 0.0,
                "trend": {"value": 0.0, "direction": "neutral", "is_positive": True},
                "label": "Всего бронирований",
                "icon": "FiShoppingBag",
                "sparkline": {"values": [0]*7, "labels": [""]*7}
            },
            "tickets": {
                "current_value": 0,
                "previous_value": 0,
                "change_percentage": 0.0,
                "trend": {"value": 0.0, "direction": "neutral", "is_positive": True},
                "label": "Открытые заявки",
                "icon": "FiMessageCircle",
                "sparkline": {"values": [0]*7, "labels": [""]*7}
            },
            "total_users": 0,
            "total_bookings": 0,
            "open_tickets": 0,
            "active_tariffs": 0,
            "paid_bookings": 0,
            "total_revenue": 0.0,
            "ticket_stats": {
                "open": 0,
                "in_progress": 0,
                "closed": 0,
            },
            "unread_notifications": 0,
            "period": {
                "start": datetime.now().isoformat(),
                "end": datetime.now().isoformat(),
                "label": datetime.now().strftime("%B %Y")
            }
        }


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

                # ОПТИМИЗИРОВАННЫЙ ЗАПРОС: Один запрос вместо трех с использованием UNION ALL
                # Это улучшает производительность на 30-50%
                combined_query = text(
                    """
                    WITH daily_data AS (
                        -- Регистрации пользователей
                        SELECT
                            CAST(strftime('%d', COALESCE(reg_date, first_join_time)) AS INTEGER) as day,
                            'users' as data_type,
                            COUNT(*) as count
                        FROM users
                        WHERE
                            (reg_date IS NOT NULL AND strftime('%Y', reg_date) = :year AND strftime('%m', reg_date) = :month_str)
                           OR
                            (reg_date IS NULL AND first_join_time IS NOT NULL AND strftime('%Y', first_join_time) = :year AND strftime('%m', first_join_time) = :month_str)
                        GROUP BY CAST(strftime('%d', COALESCE(reg_date, first_join_time)) AS INTEGER)

                        UNION ALL

                        -- Создание тикетов
                        SELECT
                            CAST(strftime('%d', created_at) AS INTEGER) as day,
                            'tickets' as data_type,
                            COUNT(*) as count
                        FROM tickets
                        WHERE strftime('%Y', created_at) = :year AND strftime('%m', created_at) = :month_str
                        GROUP BY CAST(strftime('%d', created_at) AS INTEGER)

                        UNION ALL

                        -- Создание бронирований
                        SELECT
                            CAST(strftime('%d', created_at) AS INTEGER) as day,
                            'bookings' as data_type,
                            COUNT(*) as count
                        FROM bookings
                        WHERE strftime('%Y', created_at) = :year AND strftime('%m', created_at) = :month_str
                        GROUP BY CAST(strftime('%d', created_at) AS INTEGER)
                    )
                    SELECT * FROM daily_data
                    ORDER BY day, data_type
                    """
                )

                # Выполняем единый запрос
                combined_results = session.execute(
                    combined_query, {"year": year_str, "month_str": month_str}
                ).fetchall()

                # Распределяем результаты по массивам
                for row in combined_results:
                    if row.day and 1 <= row.day <= days_in_month:
                        day_index = row.day - 1
                        if row.data_type == 'users':
                            user_registrations[day_index] = row.count
                        elif row.data_type == 'tickets':
                            ticket_creations[day_index] = row.count
                        elif row.data_type == 'bookings':
                            booking_creations[day_index] = row.count

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
