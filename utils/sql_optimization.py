"""
Утилиты для оптимизации SQL запросов и создания индексов
"""

from typing import Dict, List, Any
from sqlalchemy import text, Index
from sqlalchemy.orm import Session

from utils.logger import get_logger

logger = get_logger(__name__)


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
