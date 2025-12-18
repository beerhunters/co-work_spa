"""
Утилиты для оптимизации SQL запросов и создания индексов
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy import text, Index
from sqlalchemy.orm import Session

from utils.logger import get_logger

logger = get_logger(__name__)


def calculate_change_percentage(current_value: float, previous_value: float) -> float:
    """
    Вычисление процента изменения между двумя значениями

    Args:
        current_value: Текущее значение
        previous_value: Предыдущее значение

    Returns:
        Процент изменения (положительный для роста, отрицательный для снижения)
    """
    if previous_value == 0:
        return 100.0 if current_value > 0 else 0.0

    change = ((current_value - previous_value) / previous_value) * 100
    return round(change, 1)


def get_sparkline_data(session: Session, days: int = 7) -> Dict[str, List[int]]:
    """
    Получение данных для sparkline графиков за последние N дней

    Args:
        session: Сессия БД
        days: Количество дней (по умолчанию 7)

    Returns:
        Dict с массивами данных для каждой метрики
    """
    from datetime import datetime, timedelta

    try:
        # Вычисляем диапазон дат (последние N дней включая сегодня)
        end_date = datetime.now().replace(hour=23, minute=59, second=59)
        start_date = (end_date - timedelta(days=days-1)).replace(hour=0, minute=0, second=0)

        logger.info(f"Fetching sparkline data for {days} days: {start_date} - {end_date}")

        # Один оптимизированный запрос для всех метрик
        sparkline_query = text("""
            WITH date_range AS (
                SELECT DATE(:start_date, '+' || value || ' days') as date
                FROM (
                    SELECT 0 as value UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL
                    SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6
                )
            ),
            daily_data AS (
                -- Пользователи по дням
                SELECT
                    DATE(COALESCE(u.reg_date, u.first_join_time)) as date,
                    'users' as type,
                    COUNT(*) as count,
                    0 as avg_value
                FROM users u
                WHERE COALESCE(u.reg_date, u.first_join_time) >= :start_date
                  AND COALESCE(u.reg_date, u.first_join_time) <= :end_date
                GROUP BY DATE(COALESCE(u.reg_date, u.first_join_time))

                UNION ALL

                -- Бронирования по дням
                SELECT
                    DATE(b.created_at) as date,
                    'bookings' as type,
                    COUNT(*) as count,
                    0 as avg_value
                FROM bookings b
                WHERE b.created_at >= :start_date AND b.created_at <= :end_date
                GROUP BY DATE(b.created_at)

                UNION ALL

                -- Тикеты по дням
                SELECT
                    DATE(t.created_at) as date,
                    'tickets' as type,
                    COUNT(*) as count,
                    0 as avg_value
                FROM tickets t
                WHERE t.created_at >= :start_date AND t.created_at <= :end_date
                GROUP BY DATE(t.created_at)

                UNION ALL

                -- Средний чек по дням (включая опенспейс и офисы)
                SELECT
                    DATE(payment_date) as date,
                    'avg_booking' as type,
                    0 as count,
                    CASE
                        WHEN COUNT(*) > 0 THEN CAST(SUM(amount) AS REAL) / COUNT(*)
                        ELSE 0
                    END as avg_value
                FROM (
                    SELECT b.created_at as payment_date, b.amount
                    FROM bookings b
                    WHERE b.paid = 1
                      AND b.created_at >= :start_date
                      AND b.created_at <= :end_date
                    UNION ALL
                    SELECT oph.payment_date, oph.amount
                    FROM openspace_payment_history oph
                    WHERE oph.payment_date >= :start_date
                      AND oph.payment_date <= :end_date
                    UNION ALL
                    SELECT ooffph.payment_date, ooffph.amount
                    FROM office_payment_history ooffph
                    WHERE ooffph.payment_date >= :start_date
                      AND ooffph.payment_date <= :end_date
                ) combined_payments
                GROUP BY DATE(payment_date)
            )
            SELECT
                dr.date,
                COALESCE(MAX(CASE WHEN dd.type = 'users' THEN dd.count END), 0) as users_count,
                COALESCE(MAX(CASE WHEN dd.type = 'bookings' THEN dd.count END), 0) as bookings_count,
                COALESCE(MAX(CASE WHEN dd.type = 'tickets' THEN dd.count END), 0) as tickets_count,
                COALESCE(MAX(CASE WHEN dd.type = 'avg_booking' THEN dd.avg_value END), 0) as avg_booking_value
            FROM date_range dr
            LEFT JOIN daily_data dd ON dr.date = dd.date
            GROUP BY dr.date
            ORDER BY dr.date
        """)

        results = session.execute(sparkline_query, {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }).fetchall()

        # Формируем массивы данных
        users_data = []
        bookings_data = []
        tickets_data = []
        avg_booking_data = []
        labels = []

        for row in results:
            users_data.append(int(row.users_count or 0))
            bookings_data.append(int(row.bookings_count or 0))
            tickets_data.append(int(row.tickets_count or 0))
            avg_booking_data.append(round(float(row.avg_booking_value or 0), 2))
            # Форматируем метку (день недели сокращённо)
            date_obj = datetime.strptime(row.date, '%Y-%m-%d')
            day_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            labels.append(day_names[date_obj.weekday()])

        logger.info(f"Sparkline data fetched: {len(users_data)} days")

        return {
            "users": {
                "values": users_data,
                "labels": labels
            },
            "bookings": {
                "values": bookings_data,
                "labels": labels
            },
            "tickets": {
                "values": tickets_data,
                "labels": labels
            },
            "average_booking_value": {
                "values": avg_booking_data,
                "labels": labels
            }
        }

    except Exception as e:
        logger.error(f"Ошибка получения данных sparkline: {e}", exc_info=True)
        # Возвращаем пустые данные при ошибке
        empty_data = [0] * days
        empty_labels = [''] * days
        return {
            "users": {"values": empty_data, "labels": empty_labels},
            "bookings": {"values": empty_data, "labels": empty_labels},
            "tickets": {"values": empty_data, "labels": empty_labels},
            "average_booking_value": {"values": empty_data, "labels": empty_labels}
        }


class SQLOptimizer:
    """Класс для оптимизации SQL запросов"""

    @staticmethod
    def create_optimized_indexes(session: Session) -> Dict[str, bool]:
        """
        Создание оптимизированных индексов для улучшения производительности

        Returns:
            Dict с результатами создания индексов
        """
        results = {}

        # Индексы для таблицы users
        user_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        ]

        # Индексы для таблицы tickets
        ticket_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON tickets(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_status_created ON tickets(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(user_id, status)",
        ]

        # Индексы для таблицы bookings
        booking_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_bookings_user_id ON bookings(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_created_at ON bookings(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_tariff_id ON bookings(tariff_id)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_paid ON bookings(paid)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_confirmed ON bookings(confirmed)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_paid_amount ON bookings(paid, amount)",
            "CREATE INDEX IF NOT EXISTS idx_bookings_created_paid ON bookings(created_at, paid)",
        ]

        # Индексы для таблицы admins
        admin_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_admins_login ON admins(login)",
            "CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role)",
            "CREATE INDEX IF NOT EXISTS idx_admins_created_at ON admins(created_at)",
        ]

        # Индексы для таблицы tariffs
        tariff_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_tariffs_is_active ON tariffs(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_tariffs_type ON tariffs(type)",
            "CREATE INDEX IF NOT EXISTS idx_tariffs_price ON tariffs(price)",
        ]

        # Индексы для таблицы notifications
        notification_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)",
        ]

        all_indexes = {
            "users": user_indexes,
            "tickets": ticket_indexes,
            "bookings": booking_indexes,
            "admins": admin_indexes,
            "tariffs": tariff_indexes,
            "notifications": notification_indexes,
        }

        for table_name, indexes in all_indexes.items():
            results[table_name] = []

            for index_sql in indexes:
                try:
                    session.execute(text(index_sql))
                    session.commit()

                    index_name = (
                        index_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
                    )
                    results[table_name].append(
                        {"index": index_name, "status": "success"}
                    )
                    logger.info(f"Создан индекс: {index_name}")

                except Exception as e:
                    index_name = (
                        index_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
                    )
                    results[table_name].append(
                        {"index": index_name, "status": "failed", "error": str(e)}
                    )
                    logger.error(f"Ошибка создания индекса {index_name}: {e}")
                    session.rollback()

        return results

    @staticmethod
    def get_optimized_dashboard_stats(session: Session) -> Dict[str, Any]:
        """
        Оптимизированный запрос статистики для дашборда - одним запросом

        Returns:
            Dict со статистикой
        """
        try:
            # Объединенный запрос для получения всей статистики сразу
            stats_query = text(
                """
                               SELECT
                                       (SELECT COUNT(*) FROM users) as total_users,
                                       (SELECT COUNT(*) FROM bookings) as total_bookings,
                                       (SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED') as open_tickets,
                                       (SELECT COUNT(*) FROM tariffs WHERE is_active = 1) as active_tariffs,
                                       (SELECT COUNT(*) FROM bookings WHERE paid = 1) as paid_bookings,
                                       (SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE paid = 1) as total_revenue,
                                       (SELECT COUNT(*) FROM tickets WHERE status = 'OPEN') as open_tickets_only,
                                       (SELECT COUNT(*) FROM tickets WHERE status = 'IN_PROGRESS') as in_progress_tickets,
                                       (SELECT COUNT(*) FROM tickets WHERE status = 'CLOSED') as closed_tickets,
                                       (SELECT COUNT(*) FROM notifications WHERE is_read = 0) as unread_notifications
                               """
            )

            from utils.logger import get_logger
            logger = get_logger(__name__)
            
            logger.info("Executing dashboard stats SQL query")
            result = session.execute(stats_query).fetchone()
            
            if not result:
                logger.warning("No result returned from dashboard stats query")
                raise ValueError("No data returned from dashboard stats query")
            
            logger.info(f"Query returned result with {len(result._fields) if hasattr(result, '_fields') else 'unknown'} fields")
            
            stats_data = {
                "total_users": int(result.total_users or 0),
                "total_bookings": int(result.total_bookings or 0),
                "open_tickets": int(result.open_tickets or 0),
                "active_tariffs": int(result.active_tariffs or 0),
                "paid_bookings": int(result.paid_bookings or 0),
                "total_revenue": float(result.total_revenue or 0),
                "ticket_stats": {
                    "open": int(result.open_tickets_only or 0),
                    "in_progress": int(result.in_progress_tickets or 0),
                    "closed": int(result.closed_tickets or 0),
                },
                "unread_notifications": int(result.unread_notifications or 0),
            }
            
            logger.info(f"Successfully parsed dashboard stats: {stats_data}")
            return stats_data

        except Exception as e:
            logger.error(f"Ошибка выполнения оптимизированного запроса статистики: {e}")
            
            # Возвращаем базовую статистику при ошибке
            logger.warning("Возвращаем базовую статистику из-за ошибки SQL запроса")
            return {
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
            }

    @staticmethod
    def get_dashboard_stats_with_comparison(
        session: Session,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, Any]:
        """
        Оптимизированная статистика дашборда с сравнением двух периодов

        Args:
            session: Сессия БД
            period_start: Начало текущего периода
            period_end: Конец текущего периода

        Returns:
            Dict со статистикой и процентами изменения
        """
        try:
            # Вычисляем предыдущий период (той же длительности)
            period_duration = period_end - period_start
            prev_period_start = period_start - period_duration
            prev_period_end = period_start

            logger.info(
                f"Fetching dashboard stats: current period {period_start} - {period_end}, "
                f"previous period {prev_period_start} - {prev_period_end}"
            )

            # Единый оптимизированный запрос с CTE для обоих периодов
            stats_query = text("""
                WITH current_period AS (
                    SELECT
                        -- Пользователи за текущий период
                        COUNT(DISTINCT CASE
                            WHEN COALESCE(u.reg_date, u.first_join_time) >= :period_start
                            AND COALESCE(u.reg_date, u.first_join_time) < :period_end
                            THEN u.id END) as users_count,

                        -- Бронирования за текущий период
                        COUNT(DISTINCT CASE
                            WHEN b.created_at >= :period_start
                            AND b.created_at < :period_end
                            THEN b.id END) as bookings_count,

                        -- Тикеты за текущий период
                        COUNT(DISTINCT CASE
                            WHEN t.created_at >= :period_start
                            AND t.created_at < :period_end
                            THEN t.id END) as tickets_count,

                        -- Доход за текущий период
                        COALESCE(SUM(CASE
                            WHEN b.paid = 1
                            AND b.created_at >= :period_start
                            AND b.created_at < :period_end
                            THEN b.amount ELSE 0 END), 0) as revenue,

                        -- Средний чек за текущий период (включая опенспейс и офисы)
                        COALESCE((
                            SELECT
                                CASE WHEN COUNT(*) > 0
                                THEN CAST(SUM(amount) AS REAL) / COUNT(*)
                                ELSE 0 END
                            FROM (
                                SELECT b.amount
                                FROM bookings b
                                WHERE b.paid = 1
                                  AND b.created_at >= :period_start
                                  AND b.created_at < :period_end
                                UNION ALL
                                SELECT oph.amount
                                FROM openspace_payment_history oph
                                WHERE oph.payment_date >= :period_start
                                  AND oph.payment_date < :period_end
                                UNION ALL
                                SELECT ooffph.amount
                                FROM office_payment_history ooffph
                                WHERE ooffph.payment_date >= :period_start
                                  AND ooffph.payment_date < :period_end
                            )
                        ), 0) as avg_booking_value,

                        -- Пользователи с хотя бы одним бронированием (для конверсии)
                        COUNT(DISTINCT CASE
                            WHEN COALESCE(u.reg_date, u.first_join_time) >= :period_start
                            AND COALESCE(u.reg_date, u.first_join_time) < :period_end
                            AND EXISTS (
                                SELECT 1 FROM bookings b2
                                WHERE b2.user_id = u.id
                            )
                            THEN u.id END) as users_with_bookings
                    FROM users u
                    LEFT JOIN bookings b ON u.id = b.user_id
                    LEFT JOIN tickets t ON u.id = t.user_id
                ),
                previous_period AS (
                    SELECT
                        -- Пользователи за предыдущий период
                        COUNT(DISTINCT CASE
                            WHEN COALESCE(u.reg_date, u.first_join_time) >= :prev_period_start
                            AND COALESCE(u.reg_date, u.first_join_time) < :prev_period_end
                            THEN u.id END) as users_count,

                        -- Бронирования за предыдущий период
                        COUNT(DISTINCT CASE
                            WHEN b.created_at >= :prev_period_start
                            AND b.created_at < :prev_period_end
                            THEN b.id END) as bookings_count,

                        -- Тикеты за предыдущий период
                        COUNT(DISTINCT CASE
                            WHEN t.created_at >= :prev_period_start
                            AND t.created_at < :prev_period_end
                            THEN t.id END) as tickets_count,

                        -- Доход за предыдущий период
                        COALESCE(SUM(CASE
                            WHEN b.paid = 1
                            AND b.created_at >= :prev_period_start
                            AND b.created_at < :prev_period_end
                            THEN b.amount ELSE 0 END), 0) as revenue,

                        -- Средний чек за предыдущий период (включая опенспейс и офисы)
                        COALESCE((
                            SELECT
                                CASE WHEN COUNT(*) > 0
                                THEN CAST(SUM(amount) AS REAL) / COUNT(*)
                                ELSE 0 END
                            FROM (
                                SELECT b.amount
                                FROM bookings b
                                WHERE b.paid = 1
                                  AND b.created_at >= :prev_period_start
                                  AND b.created_at < :prev_period_end
                                UNION ALL
                                SELECT oph.amount
                                FROM openspace_payment_history oph
                                WHERE oph.payment_date >= :prev_period_start
                                  AND oph.payment_date < :prev_period_end
                                UNION ALL
                                SELECT ooffph.amount
                                FROM office_payment_history ooffph
                                WHERE ooffph.payment_date >= :prev_period_start
                                  AND ooffph.payment_date < :prev_period_end
                            )
                        ), 0) as avg_booking_value,

                        -- Пользователи с хотя бы одним бронированием (для конверсии)
                        COUNT(DISTINCT CASE
                            WHEN COALESCE(u.reg_date, u.first_join_time) >= :prev_period_start
                            AND COALESCE(u.reg_date, u.first_join_time) < :prev_period_end
                            AND EXISTS (
                                SELECT 1 FROM bookings b2
                                WHERE b2.user_id = u.id
                            )
                            THEN u.id END) as users_with_bookings
                    FROM users u
                    LEFT JOIN bookings b ON u.id = b.user_id
                    LEFT JOIN tickets t ON u.id = t.user_id
                ),
                current_status AS (
                    SELECT
                        (SELECT COUNT(*) FROM users) as total_users,
                        (SELECT COUNT(*) FROM bookings) as total_bookings,
                        (SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED') as open_tickets,
                        (SELECT COUNT(*) FROM tariffs WHERE is_active = 1) as active_tariffs,
                        (SELECT COUNT(*) FROM bookings WHERE paid = 1) as paid_bookings,
                        (SELECT COALESCE(SUM(amount), 0) FROM bookings WHERE paid = 1) as total_revenue,
                        (SELECT COUNT(*) FROM tickets WHERE status = 'OPEN') as open_tickets_only,
                        (SELECT COUNT(*) FROM tickets WHERE status = 'IN_PROGRESS') as in_progress_tickets,
                        (SELECT COUNT(*) FROM tickets WHERE status = 'CLOSED') as closed_tickets,
                        (SELECT COUNT(*) FROM notifications WHERE is_read = 0) as unread_notifications
                )
                SELECT
                    cp.users_count as current_users,
                    cp.bookings_count as current_bookings,
                    cp.tickets_count as current_tickets,
                    cp.revenue as current_revenue,
                    cp.avg_booking_value as current_avg_booking,
                    cp.users_with_bookings as current_users_with_bookings,
                    pp.users_count as prev_users,
                    pp.bookings_count as prev_bookings,
                    pp.tickets_count as prev_tickets,
                    pp.revenue as prev_revenue,
                    pp.avg_booking_value as prev_avg_booking,
                    pp.users_with_bookings as prev_users_with_bookings,
                    cs.total_users,
                    cs.total_bookings,
                    cs.open_tickets,
                    cs.active_tariffs,
                    cs.paid_bookings,
                    cs.total_revenue,
                    cs.open_tickets_only,
                    cs.in_progress_tickets,
                    cs.closed_tickets,
                    cs.unread_notifications
                FROM current_period cp, previous_period pp, current_status cs
            """)

            result = session.execute(stats_query, {
                'period_start': period_start,
                'period_end': period_end,
                'prev_period_start': prev_period_start,
                'prev_period_end': prev_period_end
            }).fetchone()

            if not result:
                logger.warning("No result returned from dashboard stats comparison query")
                raise ValueError("No data returned from dashboard stats comparison query")

            # Вычисляем проценты изменения
            users_change = calculate_change_percentage(
                float(result.current_users or 0),
                float(result.prev_users or 0)
            )
            bookings_change = calculate_change_percentage(
                float(result.current_bookings or 0),
                float(result.prev_bookings or 0)
            )
            tickets_change = calculate_change_percentage(
                float(result.current_tickets or 0),
                float(result.prev_tickets or 0)
            )
            revenue_change = calculate_change_percentage(
                float(result.current_revenue or 0),
                float(result.prev_revenue or 0)
            )
            avg_booking_change = calculate_change_percentage(
                float(result.current_avg_booking or 0),
                float(result.prev_avg_booking or 0)
            )

            # Вычисляем конверсию (процент пользователей с бронированиями)
            current_conversion = (float(result.current_users_with_bookings or 0) / float(result.current_users or 1)) * 100 if result.current_users else 0
            prev_conversion = (float(result.prev_users_with_bookings or 0) / float(result.prev_users or 1)) * 100 if result.prev_users else 0
            conversion_change = calculate_change_percentage(current_conversion, prev_conversion)

            # Формируем результат
            stats_data = {
                "users": {
                    "current_value": int(result.current_users or 0),
                    "previous_value": int(result.prev_users or 0),
                    "change_percentage": users_change,
                    "total": int(result.total_users or 0)
                },
                "bookings": {
                    "current_value": int(result.current_bookings or 0),
                    "previous_value": int(result.prev_bookings or 0),
                    "change_percentage": bookings_change,
                    "total": int(result.total_bookings or 0)
                },
                "tickets": {
                    "current_value": int(result.current_tickets or 0),
                    "previous_value": int(result.prev_tickets or 0),
                    "change_percentage": tickets_change,
                    "open": int(result.open_tickets or 0)
                },
                "revenue": {
                    "current_value": float(result.current_revenue or 0),
                    "previous_value": float(result.prev_revenue or 0),
                    "change_percentage": revenue_change,
                    "total": float(result.total_revenue or 0)
                },
                "average_booking_value": {
                    "current_value": float(result.current_avg_booking or 0),
                    "previous_value": float(result.prev_avg_booking or 0),
                    "change_percentage": avg_booking_change
                },
                "conversion_rate": {
                    "current_value": round(current_conversion, 1),
                    "previous_value": round(prev_conversion, 1),
                    "change_percentage": conversion_change,
                    "users_with_bookings": int(result.current_users_with_bookings or 0)
                },
                # Дополнительная статистика (для обратной совместимости)
                "active_tariffs": int(result.active_tariffs or 0),
                "paid_bookings": int(result.paid_bookings or 0),
                "total_revenue": float(result.total_revenue or 0),
                "ticket_stats": {
                    "open": int(result.open_tickets_only or 0),
                    "in_progress": int(result.in_progress_tickets or 0),
                    "closed": int(result.closed_tickets or 0)
                },
                "unread_notifications": int(result.unread_notifications or 0),
                "period_info": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "previous_start": prev_period_start.isoformat(),
                    "previous_end": prev_period_end.isoformat()
                }
            }

            logger.info(f"Successfully calculated dashboard stats with comparison: "
                       f"users {users_change:+.1f}%, bookings {bookings_change:+.1f}%, "
                       f"tickets {tickets_change:+.1f}%, revenue {revenue_change:+.1f}%, "
                       f"avg_booking {avg_booking_change:+.1f}%")

            return stats_data

        except Exception as e:
            logger.error(f"Ошибка выполнения запроса статистики с сравнением: {e}", exc_info=True)
            # Возвращаем базовую статистику при ошибке
            return {
                "users": {
                    "current_value": 0,
                    "previous_value": 0,
                    "change_percentage": 0.0,
                    "total": 0
                },
                "bookings": {
                    "current_value": 0,
                    "previous_value": 0,
                    "change_percentage": 0.0,
                    "total": 0
                },
                "tickets": {
                    "current_value": 0,
                    "previous_value": 0,
                    "change_percentage": 0.0,
                    "open": 0
                },
                "revenue": {
                    "current_value": 0.0,
                    "previous_value": 0.0,
                    "change_percentage": 0.0,
                    "total": 0.0
                },
                "average_booking_value": {
                    "current_value": 0.0,
                    "previous_value": 0.0,
                    "change_percentage": 0.0
                },
                "conversion_rate": {
                    "current_value": 0.0,
                    "previous_value": 0.0,
                    "change_percentage": 0.0,
                    "users_with_bookings": 0
                },
                "active_tariffs": 0,
                "paid_bookings": 0,
                "total_revenue": 0.0,
                "ticket_stats": {
                    "open": 0,
                    "in_progress": 0,
                    "closed": 0
                },
                "unread_notifications": 0,
                "period_info": {
                    "start": period_start.isoformat(),
                    "end": period_end.isoformat(),
                    "previous_start": period_start.isoformat(),
                    "previous_end": period_end.isoformat()
                }
            }

    @staticmethod
    def get_optimized_tickets_with_users(
        session: Session,
        page: int = 1,
        per_page: int = 20,
        status: str = None,
        user_query: str = None,
    ) -> Dict[str, Any]:
        """
        Оптимизированный запрос тикетов с пользователями - с использованием индексов

        Returns:
            Dict с тикетами и метаинформацией
        """
        try:
            # Базовый запрос с LEFT JOIN для получения всех данных одним запросом
            # ИСПРАВЛЕНО: заменено u.avatar_path на u.avatar (согласно модели User)
            base_query = """
                         SELECT
                             t.id, t.user_id, t.description, t.photo_id, t.response_photo_id,
                             t.status, t.comment, t.created_at, t.updated_at,
                             u.telegram_id, u.full_name, u.username, u.phone, u.email,
                             u.reg_date, u.avatar
                         FROM tickets t
                                  LEFT JOIN users u ON t.user_id = u.id \
                         """

            where_conditions = []
            params = {}

            # Фильтрация с использованием индексов
            if user_query and user_query.strip():
                query_stripped = user_query.strip()
                query_lower = query_stripped.lower()
                query_upper = query_stripped.upper()
                query_title = query_stripped.capitalize()
                where_conditions.append("""(
                    u.full_name LIKE :user_query_orig OR 
                    u.full_name LIKE :user_query_lower OR 
                    u.full_name LIKE :user_query_upper OR
                    u.full_name LIKE :user_query_title OR
                    t.description LIKE :desc_query_orig OR 
                    t.description LIKE :desc_query_lower OR 
                    t.description LIKE :desc_query_upper OR
                    t.description LIKE :desc_query_title
                )""")
                params["user_query_orig"] = f"%{query_stripped}%"
                params["user_query_lower"] = f"%{query_lower}%"
                params["user_query_upper"] = f"%{query_upper}%"
                params["user_query_title"] = f"%{query_title}%"
                params["desc_query_orig"] = f"%{query_stripped}%"
                params["desc_query_lower"] = f"%{query_lower}%"
                params["desc_query_upper"] = f"%{query_upper}%"
                params["desc_query_title"] = f"%{query_title}%"

            if status and status.strip():
                where_conditions.append("t.status = :status")
                params["status"] = status.strip()

            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)

            # Подсчет общего количества (оптимизировано)
            count_query = f"""
                SELECT COUNT(*) 
                FROM tickets t
                LEFT JOIN users u ON t.user_id = u.id
                {" WHERE " + " AND ".join(where_conditions) if where_conditions else ""}
            """

            total_count = session.execute(text(count_query), params).scalar()

            # Основной запрос с сортировкой и пагинацией
            final_query = (
                base_query
                + """
                ORDER BY t.created_at DESC 
                LIMIT :limit OFFSET :offset
            """
            )

            params.update({"limit": per_page, "offset": (page - 1) * per_page})

            result = session.execute(text(final_query), params).fetchall()

            # Формирование результата
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
                        "reg_date": row.reg_date,
                        "avatar": row.avatar,  # ИСПРАВЛЕНО: изменено с avatar_path на avatar
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
            logger.error(f"Ошибка выполнения оптимизированного запроса тикетов: {e}")
            raise

    @staticmethod
    def get_optimized_bookings_stats(session: Session) -> Dict[str, Any]:
        """
        Оптимизированная статистика бронирований одним запросом

        Returns:
            Dict со статистикой бронирований
        """
        try:
            from datetime import datetime
            from config import MOSCOW_TZ

            current_month_start = datetime.now(MOSCOW_TZ).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

            # Единый оптимизированный запрос
            stats_query = text(
                """
                               SELECT
                                   COUNT(*) as total_bookings,
                                   COUNT(CASE WHEN paid = 1 THEN 1 END) as paid_bookings,
                                   COUNT(CASE WHEN confirmed = 1 THEN 1 END) as confirmed_bookings,
                                   COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) as total_revenue,
                                   COUNT(CASE WHEN created_at >= :start_date THEN 1 END) as current_month_bookings,
                                   COALESCE(SUM(CASE WHEN created_at >= :start_date AND paid = 1 THEN amount ELSE 0 END), 0) as current_month_revenue
                               FROM bookings
                               """
            )

            result = session.execute(
                stats_query, {"start_date": current_month_start}
            ).fetchone()

            # Топ тарифы (отдельный запрос, но оптимизированный)
            top_tariffs_query = text(
                """
                                     SELECT
                                         t.name,
                                         t.price,
                                         COUNT(b.id) as booking_count,
                                         COALESCE(SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END), 0) as revenue
                                     FROM tariffs t
                                              LEFT JOIN bookings b ON t.id = b.tariff_id
                                     WHERE t.is_active = 1
                                     GROUP BY t.id, t.name, t.price
                                     ORDER BY booking_count DESC, revenue DESC
                                     LIMIT 5
                                     """
            )

            top_tariffs_result = session.execute(top_tariffs_query).fetchall()

            top_tariffs = [
                {
                    "name": row.name,
                    "price": float(row.price or 0),
                    "bookings": int(row.booking_count),
                    "revenue": float(row.revenue or 0),
                }
                for row in top_tariffs_result
            ]

            return {
                "total_bookings": int(result.total_bookings or 0),
                "paid_bookings": int(result.paid_bookings or 0),
                "confirmed_bookings": int(result.confirmed_bookings or 0),
                "total_revenue": float(result.total_revenue or 0),
                "current_month_bookings": int(result.current_month_bookings or 0),
                "current_month_revenue": float(result.current_month_revenue or 0),
                "avg_booking_value": (
                    float(result.total_revenue) / max(result.paid_bookings, 1)
                    if result.paid_bookings > 0
                    else 0
                ),
                "top_tariffs": top_tariffs,
            }

        except Exception as e:
            logger.error(
                f"Ошибка выполнения оптимизированной статистики бронирований: {e}"
            )
            raise

    @staticmethod
    def analyze_query_performance(
        session: Session, query: str, params: dict = None
    ) -> Dict[str, Any]:
        """
        Анализ производительности SQL запроса

        Args:
            session: Сессия БД
            query: SQL запрос для анализа
            params: Параметры запроса

        Returns:
            Dict с информацией о производительности
        """
        try:
            import time

            # Получаем план выполнения запроса (для SQLite)
            explain_query = f"EXPLAIN QUERY PLAN {query}"

            start_time = time.time()

            # Выполняем оригинальный запрос
            if params:
                result = session.execute(text(query), params)
            else:
                result = session.execute(text(query))

            rows = result.fetchall()
            execution_time = time.time() - start_time

            # Получаем план выполнения
            if params:
                explain_result = session.execute(text(explain_query), params).fetchall()
            else:
                explain_result = session.execute(text(explain_query)).fetchall()

            return {
                "query": query[:200] + "..." if len(query) > 200 else query,
                "execution_time_ms": round(execution_time * 1000, 2),
                "rows_returned": len(rows),
                "execution_plan": [dict(row._mapping) for row in explain_result],
                "performance_rating": (
                    "good"
                    if execution_time < 0.1
                    else "slow" if execution_time < 1 else "very_slow"
                ),
            }

        except Exception as e:
            logger.error(f"Ошибка анализа производительности запроса: {e}")
            return {
                "query": query[:200] + "..." if len(query) > 200 else query,
                "error": str(e),
                "performance_rating": "error",
            }

    @staticmethod
    def get_database_statistics(session: Session) -> Dict[str, Any]:
        """
        Получение статистики базы данных для мониторинга производительности

        Returns:
            Dict со статистикой БД
        """
        try:
            # Статистика таблиц
            table_stats_query = text(
                """
                                     SELECT
                                         name as table_name,
                                         (SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name = m.name) as index_count
                                     FROM sqlite_master m
                                     WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                     ORDER BY name
                                     """
            )

            table_stats = session.execute(table_stats_query).fetchall()

            # Размеры таблиц (приблизительно для SQLite)
            table_sizes = {}
            for table in table_stats:
                try:
                    count_query = text(f"SELECT COUNT(*) FROM {table.table_name}")
                    count = session.execute(count_query).scalar()
                    table_sizes[table.table_name] = {
                        "row_count": count,
                        "index_count": table.index_count,
                    }
                except Exception as e:
                    logger.warning(
                        f"Не удалось получить статистику для таблицы {table.table_name}: {e}"
                    )
                    table_sizes[table.table_name] = {
                        "row_count": 0,
                        "index_count": table.index_count,
                    }

            return {
                "total_tables": len(table_sizes),
                "table_statistics": table_sizes,
                "total_rows": sum(t["row_count"] for t in table_sizes.values()),
                "total_indexes": sum(t["index_count"] for t in table_sizes.values()),
            }

        except Exception as e:
            logger.error(f"Ошибка получения статистики БД: {e}")
            return {"error": str(e)}
