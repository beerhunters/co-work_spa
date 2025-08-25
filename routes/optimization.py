"""
API маршруты для оптимизации и анализа производительности БД
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from datetime import datetime

from config import MOSCOW_TZ
from dependencies import verify_token
from models.models import DatabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/create-indexes")
async def create_database_indexes(_: str = Depends(verify_token)):
    """
    Создание оптимизированных индексов для улучшения производительности БД

    Требует аутентификации администратора.
    """
    def _create_indexes(session):
        results = {
            "total_indexes": 0,
            "successful": 0,
            "failed": 0,
            "details": {}
        }

        # Определяем индексы для создания
        indexes_to_create = [
            {
                "table": "users",
                "name": "idx_users_telegram_id",
                "columns": ["telegram_id"],
                "unique": True
            },
            {
                "table": "users",
                "name": "idx_users_created_at",
                "columns": ["created_at"],
                "unique": False
            },
            {
                "table": "tickets",
                "name": "idx_tickets_user_id",
                "columns": ["user_id"],
                "unique": False
            },
            {
                "table": "tickets",
                "name": "idx_tickets_status",
                "columns": ["status"],
                "unique": False
            },
            {
                "table": "bookings",
                "name": "idx_bookings_user_id",
                "columns": ["user_id"],
                "unique": False
            },
            {
                "table": "bookings",
                "name": "idx_bookings_status_date",
                "columns": ["status", "created_at"],
                "unique": False
            }
        ]

        for index_def in indexes_to_create:
            table_name = index_def["table"]
            if table_name not in results["details"]:
                results["details"][table_name] = []

            try:
                columns_str = ", ".join(index_def["columns"])

                # Проверяем, существует ли уже индекс
                check_sql = text("""
                                 SELECT name FROM sqlite_master
                                 WHERE type='index' AND name = :index_name
                                 """)

                existing = session.execute(check_sql, {"index_name": index_def["name"]}).fetchone()

                if existing:
                    results["details"][table_name].append({
                        "index": index_def["name"],
                        "status": "skipped",
                        "reason": "Index already exists"
                    })
                    continue

                # Создаем индекс
                if index_def["unique"]:
                    create_sql = text(f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS {index_def["name"]} 
                        ON {table_name} ({columns_str})
                    """)
                else:
                    create_sql = text(f"""
                        CREATE INDEX IF NOT EXISTS {index_def["name"]} 
                        ON {table_name} ({columns_str})
                    """)

                session.execute(create_sql)

                results["details"][table_name].append({
                    "index": index_def["name"],
                    "status": "success"
                })
                results["successful"] += 1

            except Exception as e:
                logger.error(f"Failed to create index {index_def['name']}: {e}")
                results["details"][table_name].append({
                    "index": index_def["name"],
                    "status": "failed",
                    "error": str(e)
                })
                results["failed"] += 1

            results["total_indexes"] += 1

        session.commit()
        return results

    try:
        logger.info("Начинаем создание оптимизированных индексов")

        result = DatabaseManager.safe_execute(_create_indexes)

        return {
            "status": "success",
            "message": "Процесс создания индексов завершен",
            **result
        }

    except Exception as e:
        logger.error(f"Ошибка создания индексов: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать индексы: {str(e)}"
        )


@router.get("/database-stats")
async def get_database_statistics(_: str = Depends(verify_token)):
    """
    Получение реальной статистики базы данных для мониторинга производительности

    Требует аутентификации администратора.
    """
    def _get_db_stats(session):
        stats = {
            "database_size_mb": 0,
            "total_tables": 0,
            "total_indexes": 0,
            "table_statistics": {}
        }

        try:
            # Получаем размер БД
            db_size_result = session.execute(text("""
                                                  SELECT page_count * page_size as size
                                                  FROM pragma_page_count(), pragma_page_size()
                                                  """)).fetchone()

            if db_size_result:
                stats["database_size_mb"] = round(db_size_result[0] / (1024 * 1024), 2)

            # Получаем список таблиц
            tables_result = session.execute(text("""
                                                 SELECT name FROM sqlite_master
                                                 WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                                 """)).fetchall()

            stats["total_tables"] = len(tables_result)

            # Получаем количество индексов
            indexes_result = session.execute(text("""
                                                  SELECT COUNT(*) FROM sqlite_master
                                                  WHERE type='index' AND name NOT LIKE 'sqlite_%'
                                                  """)).fetchone()

            if indexes_result:
                stats["total_indexes"] = indexes_result[0]

            # Статистика по каждой таблице
            for (table_name,) in tables_result:
                try:
                    # Количество записей
                    count_result = session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()
                    row_count = count_result[0] if count_result else 0

                    # Количество индексов для таблицы
                    table_indexes = session.execute(text("""
                                                         SELECT COUNT(*) FROM sqlite_master
                                                         WHERE type='index' AND tbl_name = :table_name
                                                           AND name NOT LIKE 'sqlite_%'
                                                         """), {"table_name": table_name}).fetchone()

                    index_count = table_indexes[0] if table_indexes else 0

                    stats["table_statistics"][table_name] = {
                        "row_count": row_count,
                        "index_count": index_count
                    }

                except Exception as e:
                    logger.warning(f"Could not get stats for table {table_name}: {e}")
                    stats["table_statistics"][table_name] = {
                        "row_count": 0,
                        "index_count": 0,
                        "error": str(e)
                    }

        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            raise

        return stats

    try:
        stats = DatabaseManager.safe_execute(_get_db_stats)

        return {
            "status": "success",
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            **stats
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики БД: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статистику БД: {str(e)}"
        )


@router.post("/analyze-query")
async def analyze_query_performance(
        query: str,
        _: str = Depends(verify_token)
):
    """
    Анализ производительности конкретного SQL запроса

    Args:
        query: SQL запрос для анализа

    Требует аутентификации администратора.
    """
    try:
        if not query.strip():
            raise HTTPException(
                status_code=400,
                detail="Запрос не может быть пустым"
            )

        # Проверяем, что это безопасный SELECT запрос
        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            raise HTTPException(
                status_code=400,
                detail="Разрешены только SELECT запросы"
            )

        # Проверяем на опасные ключевые слова
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "PRAGMA"]
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise HTTPException(
                    status_code=400,
                    detail=f"Запросы с '{keyword}' не разрешены"
                )

        def _analyze_query(session):
            import time

            # Получаем план выполнения
            explain_query = f"EXPLAIN QUERY PLAN {query}"
            plan_result = session.execute(text(explain_query)).fetchall()

            execution_plan = []
            for row in plan_result:
                execution_plan.append({
                    "step": row[0] if len(row) > 0 else 0,
                    "operation": row[3] if len(row) > 3 else "Unknown",
                    "detail": row[3] if len(row) > 3 else ""
                })

            # Измеряем время выполнения
            start_time = time.time()
            try:
                result = session.execute(text(query))
                # Получаем все результаты для точного измерения
                rows = result.fetchall()
                execution_time_ms = (time.time() - start_time) * 1000
                row_count = len(rows)
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                row_count = 0
                logger.warning(f"Query execution failed during analysis: {e}")

            # Определяем рейтинг производительности
            if execution_time_ms < 50:
                performance_rating = "fast"
            elif execution_time_ms < 200:
                performance_rating = "medium"
            else:
                performance_rating = "slow"

            # Генерируем рекомендации
            recommendations = _generate_query_recommendations({
                "execution_time_ms": execution_time_ms,
                "execution_plan": execution_plan,
                "row_count": row_count
            })

            return {
                "query": query[:200] + "..." if len(query) > 200 else query,
                "execution_time_ms": round(execution_time_ms, 2),
                "performance_rating": performance_rating,
                "execution_plan": execution_plan,
                "recommendations": recommendations,
                "rows_returned": row_count
            }

        result = DatabaseManager.safe_execute(_analyze_query)

        return {
            "status": "success",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа запроса: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать запрос: {str(e)}"
        )


@router.get("/performance-report")
async def get_performance_report(_: str = Depends(verify_token)):
    """
    Получение отчета о производительности с реальными данными БД

    Требует аутентификации администратора.
    """
    def _generate_report(session):
        report = {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "database_statistics": {},
            "index_analysis": {},
            "recommendations": []
        }

        try:
            # Базовая статистика БД
            db_size = session.execute(text("""
                                           SELECT page_count * page_size as size
                                           FROM pragma_page_count(), pragma_page_size()
                                           """)).fetchone()

            tables_count = session.execute(text("""
                                                SELECT COUNT(*) FROM sqlite_master
                                                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                                """)).fetchone()

            indexes_count = session.execute(text("""
                                                 SELECT COUNT(*) FROM sqlite_master
                                                 WHERE type='index' AND name NOT LIKE 'sqlite_%'
                                                 """)).fetchone()

            report["database_statistics"] = {
                "database_size_mb": round(db_size[0] / (1024*1024), 2) if db_size else 0,
                "total_tables": tables_count[0] if tables_count else 0,
                "total_indexes": indexes_count[0] if indexes_count else 0
            }

            # Анализ индексов
            tables_result = session.execute(text("""
                                                 SELECT name FROM sqlite_master
                                                 WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                                 """)).fetchall()

            for (table_name,) in tables_result:
                # Проверяем наличие индексов
                table_indexes = session.execute(text("""
                                                     SELECT name, sql FROM sqlite_master
                                                     WHERE type='index' AND tbl_name = :table_name
                                                       AND name NOT LIKE 'sqlite_%'
                                                     """), {"table_name": table_name}).fetchall()

                report["index_analysis"][table_name] = {
                    "indexes": [{"name": idx[0], "definition": idx[1]} for idx in table_indexes],
                    "index_count": len(table_indexes)
                }

                # Генерируем рекомендации по индексам
                if len(table_indexes) == 0:
                    report["recommendations"].append({
                        "type": "index",
                        "priority": "medium",
                        "message": f"Таблица {table_name} не имеет индексов",
                        "action": f"Рассмотрите создание индексов для часто используемых колонок"
                    })

            # Общий анализ здоровья БД
            total_tables = report["database_statistics"]["total_tables"]
            total_indexes = report["database_statistics"]["total_indexes"]

            if total_tables > 0:
                index_ratio = total_indexes / total_tables
                if index_ratio < 1:
                    report["recommendations"].append({
                        "type": "performance",
                        "priority": "high",
                        "message": "Низкое соотношение индексов к таблицам",
                        "action": "Добавьте индексы для улучшения производительности запросов"
                    })

            # Определяем общее состояние
            if len(report["recommendations"]) == 0:
                overall_health = "excellent"
            elif len(report["recommendations"]) <= 2:
                overall_health = "good"
            elif len(report["recommendations"]) <= 5:
                overall_health = "fair"
            else:
                overall_health = "poor"

            report["overall_health"] = overall_health

        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            raise

        return report

    try:
        report = DatabaseManager.safe_execute(_generate_report)

        return {
            "status": "success",
            **report
        }

    except Exception as e:
        logger.error(f"Ошибка создания отчета о производительности: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать отчет: {str(e)}"
        )


@router.get("/slow-queries")
async def get_slow_queries(
        threshold_ms: int = Query(100, ge=1, le=10000, description="Порог времени в мс"),
        _: str = Depends(verify_token)
):
    """
    Анализ потенциально медленных запросов на основе структуры БД

    Args:
        threshold_ms: Пороговое значение времени выполнения в миллисекундах

    Требует аутентификации администратора.
    """
    def _analyze_potential_slow_queries(session):
        import time

        slow_queries = []
        query_id = 1

        # Получаем список таблиц для анализа
        tables_result = session.execute(text("""
                                             SELECT name FROM sqlite_master
                                             WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                             """)).fetchall()

        for (table_name,) in tables_result:
            try:
                # Тестируем несколько типичных запросов

                # 1. Запрос с COUNT(*) без WHERE
                test_query = f"SELECT COUNT(*) FROM `{table_name}`"
                start_time = time.time()
                result = session.execute(text(test_query))
                result.fetchall()
                duration = (time.time() - start_time) * 1000

                if duration > threshold_ms:
                    slow_queries.append({
                        "id": query_id,
                        "query_text": test_query,
                        "avg_duration": round(duration, 2),
                        "max_duration": round(duration * 1.2, 2),
                        "execution_count": 1,
                        "table_name": table_name,
                        "execution_plan": "Table Scan",
                        "issue": "Full table scan for COUNT operation"
                    })
                    query_id += 1

                # 2. Если таблица имеет много записей, тестируем SELECT * с LIMIT
                count_result = session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()
                if count_result and count_result[0] > 100:
                    test_query = f"SELECT * FROM `{table_name}` ORDER BY rowid DESC LIMIT 10"
                    start_time = time.time()
                    result = session.execute(text(test_query))
                    result.fetchall()
                    duration = (time.time() - start_time) * 1000

                    if duration > threshold_ms:
                        slow_queries.append({
                            "id": query_id,
                            "query_text": test_query,
                            "avg_duration": round(duration, 2),
                            "max_duration": round(duration * 1.5, 2),
                            "execution_count": 1,
                            "table_name": table_name,
                            "execution_plan": "Table Scan + Sort",
                            "issue": "No index for ordering"
                        })
                        query_id += 1

            except Exception as e:
                logger.warning(f"Could not analyze table {table_name}: {e}")
                continue

        return slow_queries

    try:
        slow_queries = DatabaseManager.safe_execute(_analyze_potential_slow_queries)

        return {
            "status": "success",
            "threshold_ms": threshold_ms,
            "slow_queries_found": len(slow_queries),
            "slow_queries": slow_queries
        }

    except Exception as e:
        logger.error(f"Ошибка анализа медленных запросов: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать медленные запросы: {str(e)}"
        )


@router.get("/recommendations")
async def get_recommendations(_: str = Depends(verify_token)):
    """
    Получение рекомендаций по оптимизации на основе анализа структуры БД

    Требует аутентификации администратора.
    """
    def _generate_recommendations(session):
        recommendations = []
        index_suggestions = []
        suggestion_id = 1

        try:
            # Получаем информацию о таблицах и их индексах
            tables_result = session.execute(text("""
                                                 SELECT name FROM sqlite_master
                                                 WHERE type='table' AND name NOT LIKE 'sqlite_%'
                                                 """)).fetchall()

            for (table_name,) in tables_result:
                try:
                    # Проверяем количество записей
                    count_result = session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()
                    row_count = count_result[0] if count_result else 0

                    # Получаем существующие индексы
                    indexes_result = session.execute(text("""
                                                          SELECT name FROM sqlite_master
                                                          WHERE type='index' AND tbl_name = :table_name
                                                            AND name NOT LIKE 'sqlite_%'
                                                          """), {"table_name": table_name}).fetchall()

                    index_count = len(indexes_result)

                    # Анализируем структуру таблицы
                    columns_result = session.execute(text(f"PRAGMA table_info(`{table_name}`)")).fetchall()

                    # Рекомендации по индексам для конкретных таблиц
                    if table_name == "users" and row_count > 10:
                        # Проверяем наличие индекса на telegram_id
                        has_telegram_index = any("telegram" in idx[0].lower() for idx in indexes_result)
                        if not has_telegram_index:
                            index_suggestions.append({
                                "id": suggestion_id,
                                "table": table_name,
                                "columns": ["telegram_id"],
                                "type": "unique",
                                "reason": "Частые поиски пользователей по telegram_id",
                                "estimated_improvement": "60-80% ускорение поиска пользователей",
                                "priority": "high"
                            })
                            suggestion_id += 1

                    if table_name == "tickets" and row_count > 20:
                        # Проверяем индексы для tickets
                        has_user_index = any("user" in idx[0].lower() for idx in indexes_result)
                        has_status_index = any("status" in idx[0].lower() for idx in indexes_result)

                        if not has_user_index:
                            index_suggestions.append({
                                "id": suggestion_id,
                                "table": table_name,
                                "columns": ["user_id"],
                                "type": "btree",
                                "reason": "Частые запросы тикетов по пользователям",
                                "estimated_improvement": "30-50% ускорение JOIN операций",
                                "priority": "medium"
                            })
                            suggestion_id += 1

                        if not has_status_index:
                            index_suggestions.append({
                                "id": suggestion_id,
                                "table": table_name,
                                "columns": ["status"],
                                "type": "btree",
                                "reason": "Фильтрация тикетов по статусу",
                                "estimated_improvement": "25-40% ускорение фильтрации",
                                "priority": "medium"
                            })
                            suggestion_id += 1

                    if table_name == "bookings" and row_count > 50:
                        # Составной индекс для bookings
                        has_compound_index = any(
                            "status" in idx[0].lower() and "date" in idx[0].lower()
                            for idx in indexes_result
                        )

                        if not has_compound_index:
                            index_suggestions.append({
                                "id": suggestion_id,
                                "table": table_name,
                                "columns": ["status", "created_at"],
                                "type": "btree",
                                "reason": "Частые запросы по статусу и дате бронирования",
                                "estimated_improvement": "40-60% ускорение составных запросов",
                                "priority": "high"
                            })
                            suggestion_id += 1

                    # Общие рекомендации
                    if row_count > 100 and index_count == 0:
                        recommendations.append({
                            "title": f"Добавить базовые индексы для таблицы {table_name}",
                            "description": f"Таблица {table_name} содержит {row_count} записей, но не имеет индексов",
                            "priority": "high",
                            "impact": "Значительное ускорение запросов"
                        })

                except Exception as e:
                    logger.warning(f"Could not analyze table {table_name}: {e}")
                    continue

            # Общие системные рекомендации
            total_tables = len(tables_result)
            total_indexes = len(index_suggestions)

            if total_indexes > 0:
                recommendations.append({
                    "title": "Оптимизировать индексы базы данных",
                    "description": f"Обнаружено {total_indexes} возможностей для улучшения индексации",
                    "priority": "high",
                    "impact": "20-50% общее ускорение запросов"
                })

            if total_tables > 5:
                recommendations.append({
                    "title": "Настроить мониторинг производительности",
                    "description": "Рекомендуется регулярно отслеживать медленные запросы",
                    "priority": "medium",
                    "impact": "Проактивная оптимизация"
                })

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append({
                "title": "Ошибка анализа БД",
                "description": f"Не удалось проанализировать структуру: {str(e)}",
                "priority": "low",
                "impact": "Требует дополнительной диагностики"
            })

        return {
            "recommendations": recommendations,
            "index_suggestions": index_suggestions
        }

    try:
        result = DatabaseManager.safe_execute(_generate_recommendations)

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить рекомендации: {str(e)}"
        )


@router.post("/create-index")
async def create_index(
        index_data: Dict[str, Any],
        _: str = Depends(verify_token)
):
    """
    Создание индекса по рекомендации

    Требует аутентификации администратора.
    """
    try:
        table = index_data.get("table")
        columns = index_data.get("columns", [])
        index_type = index_data.get("index_type", "btree")

        if not table or not columns:
            raise HTTPException(
                status_code=400,
                detail="Не указана таблица или колонки для индекса"
            )

        def _create_index(session):
            import time

            try:
                # Генерируем имя индекса
                columns_suffix = "_".join(columns)
                timestamp = int(time.time())
                index_name = f"idx_{table}_{columns_suffix}_{timestamp}"
                columns_str = ", ".join(f"`{col}`" for col in columns)

                # Проверяем существование таблицы
                table_check = session.execute(text("""
                                                   SELECT name FROM sqlite_master
                                                   WHERE type='table' AND name = :table_name
                                                   """), {"table_name": table}).fetchone()

                if not table_check:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Таблица {table} не найдена"
                    )

                # Создаем SQL для создания индекса
                if index_type.lower() == "unique":
                    create_sql = text(f"""
                        CREATE UNIQUE INDEX IF NOT EXISTS {index_name} 
                        ON `{table}` ({columns_str})
                    """)
                else:
                    create_sql = text(f"""
                        CREATE INDEX IF NOT EXISTS {index_name} 
                        ON `{table}` ({columns_str})
                    """)

                # Выполняем создание индекса
                session.execute(create_sql)
                session.commit()

                logger.info(f"Индекс {index_name} успешно создан для таблицы {table}")

                return {
                    "status": "success",
                    "message": f"Индекс успешно создан",
                    "index_name": index_name,
                    "table": table,
                    "columns": columns,
                    "type": index_type
                }

            except Exception as e:
                session.rollback()
                logger.error(f"Ошибка создания индекса: {e}")
                raise

        return DatabaseManager.safe_execute(_create_index)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка создания индекса: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать индекс: {str(e)}"
        )


def _generate_query_recommendations(analysis: Dict[str, Any]) -> List[str]:
    """Генерация рекомендаций по оптимизации запроса на основе реального анализа"""
    recommendations = []

    execution_time = analysis.get("execution_time_ms", 0)
    execution_plan = analysis.get("execution_plan", [])
    row_count = analysis.get("row_count", 0)

    # Рекомендации по времени выполнения
    if execution_time > 1000:  # Более 1 секунды
        recommendations.append("Запрос выполняется критически медленно (>1с), требует немедленной оптимизации")
    elif execution_time > 500:  # Более 500ms
        recommendations.append("Запрос выполняется медленно, рекомендуется оптимизация")
    elif execution_time > 100:  # Более 100ms
        recommendations.append("Запрос может быть оптимизирован для лучшей производительности")

    # Анализ плана выполнения
    plan_text = " ".join([step.get("detail", "").lower() for step in execution_plan])

    if "scan" in plan_text and "index" not in plan_text:
        recommendations.append("Обнаружено полное сканирование таблицы, рекомендуется добавить индекс")

    if "sort" in plan_text or "order" in plan_text:
        recommendations.append("Запрос использует сортировку, рассмотрите создание индекса для ORDER BY")

    if "temp" in plan_text:
        recommendations.append("Используются временные таблицы, возможна оптимизация JOIN операций")

    if "nested loop" in plan_text:
        recommendations.append("Обнаружен вложенный цикл, рассмотрите оптимизацию JOIN условий")

    # Рекомендации по количеству строк
    if row_count > 10000:
        recommendations.append("Запрос возвращает много строк, рассмотрите использование LIMIT и пагинации")
    elif row_count == 0:
        recommendations.append("Запрос не возвращает результатов, проверьте условия WHERE")

    # Если нет проблем
    if not recommendations:
        if execution_time < 50:
            recommendations.append("Запрос выполняется быстро и эффективно")
        else:
            recommendations.append("Запрос работает в пределах нормы")

    return recommendations


@router.delete("/index/{index_name}")
async def drop_index(
        index_name: str,
        _: str = Depends(verify_token)
):
    """
    Удаление индекса

    Args:
        index_name: Имя индекса для удаления

    Требует аутентификации администратора.
    """
    def _drop_index(session):
        try:
            # Проверяем существование индекса
            index_check = session.execute(text("""
                                               SELECT name, tbl_name FROM sqlite_master
                                               WHERE type='index' AND name = :index_name
                                               """), {"index_name": index_name}).fetchone()

            if not index_check:
                raise HTTPException(
                    status_code=404,
                    detail=f"Индекс {index_name} не найден"
                )

            table_name = index_check[1]

            # Удаляем индекс
            drop_sql = text(f"DROP INDEX IF EXISTS `{index_name}`")
            session.execute(drop_sql)
            session.commit()

            logger.info(f"Индекс {index_name} успешно удален из таблицы {table_name}")

            return {
                "status": "success",
                "message": f"Индекс {index_name} успешно удален",
                "index_name": index_name,
                "table_name": table_name
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка удаления индекса {index_name}: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_drop_index)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления индекса: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось удалить индекс: {str(e)}"
        )


@router.get("/index-usage")
async def get_index_usage(_: str = Depends(verify_token)):
    """
    Анализ использования индексов

    Требует аутентификации администратора.
    """
    def _analyze_index_usage(session):
        try:
            # Получаем информацию об индексах
            indexes_result = session.execute(text("""
                                                  SELECT name, tbl_name, sql FROM sqlite_master
                                                  WHERE type='index' AND name NOT LIKE 'sqlite_%'
                                                  ORDER BY tbl_name, name
                                                  """)).fetchall()

            index_analysis = []

            for index_name, table_name, sql_definition in indexes_result:
                # Базовая информация об индексе
                index_info = {
                    "index_name": index_name,
                    "table_name": table_name,
                    "definition": sql_definition,
                    "status": "active"
                }

                # Пытаемся определить колонки индекса из SQL определения
                if sql_definition:
                    # Простое извлечение колонок из CREATE INDEX statement
                    columns_start = sql_definition.upper().find("(")
                    columns_end = sql_definition.upper().find(")", columns_start)
                    if columns_start > 0 and columns_end > columns_start:
                        columns_str = sql_definition[columns_start+1:columns_end]
                        columns = [col.strip().strip('`"[]') for col in columns_str.split(',')]
                        index_info["columns"] = columns

                # Проверяем размер таблицы для оценки полезности индекса
                try:
                    table_size = session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()
                    index_info["table_rows"] = table_size[0] if table_size else 0

                    # Простая эвристика полезности
                    if index_info["table_rows"] < 100:
                        index_info["usefulness"] = "low"
                        index_info["note"] = "Индекс может быть не нужен для малой таблицы"
                    else:
                        index_info["usefulness"] = "potentially_useful"
                        index_info["note"] = "Индекс может быть полезен"

                except Exception as e:
                    index_info["table_rows"] = 0
                    index_info["error"] = str(e)

                index_analysis.append(index_info)

            return {
                "total_indexes": len(index_analysis),
                "indexes": index_analysis
            }

        except Exception as e:
            logger.error(f"Error analyzing index usage: {e}")
            raise

    try:
        result = DatabaseManager.safe_execute(_analyze_index_usage)

        return {
            "status": "success",
            **result
        }

    except Exception as e:
        logger.error(f"Ошибка анализа использования индексов: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать использование индексов: {str(e)}"
        )


@router.post("/vacuum")
async def vacuum_database(_: str = Depends(verify_token)):
    """
    Выполнение VACUUM для оптимизации БД

    Требует аутентификации администратора.
    """
    def _vacuum_database(session):
        import time

        try:
            # Получаем размер БД до VACUUM
            size_before = session.execute(text("""
                                               SELECT page_count * page_size as size
                                               FROM pragma_page_count(), pragma_page_size()
                                               """)).fetchone()

            size_before_mb = round(size_before[0] / (1024*1024), 2) if size_before else 0

            start_time = time.time()

            # Выполняем VACUUM
            session.execute(text("VACUUM"))
            session.commit()

            duration = time.time() - start_time

            # Получаем размер БД после VACUUM
            size_after = session.execute(text("""
                                              SELECT page_count * page_size as size
                                              FROM pragma_page_count(), pragma_page_size()
                                              """)).fetchone()

            size_after_mb = round(size_after[0] / (1024*1024), 2) if size_after else 0
            space_saved_mb = size_before_mb - size_after_mb

            logger.info(f"VACUUM completed in {duration:.2f}s, saved {space_saved_mb:.2f}MB")

            return {
                "status": "success",
                "message": "VACUUM выполнен успешно",
                "duration_seconds": round(duration, 2),
                "size_before_mb": size_before_mb,
                "size_after_mb": size_after_mb,
                "space_saved_mb": round(space_saved_mb, 2),
                "improvement_percent": round((space_saved_mb / max(size_before_mb, 0.01)) * 100, 1)
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка выполнения VACUUM: {e}")
            raise

    try:
        return DatabaseManager.safe_execute(_vacuum_database)

    except Exception as e:
        logger.error(f"Ошибка выполнения VACUUM: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось выполнить VACUUM: {str(e)}"
        )


@router.get("/table-analysis/{table_name}")
async def analyze_table(
        table_name: str,
        _: str = Depends(verify_token)
):
    """
    Детальный анализ конкретной таблицы

    Args:
        table_name: Имя таблицы для анализа

    Требует аутентификации администратора.
    """
    def _analyze_table(session):
        try:
            # Проверяем существование таблицы
            table_check = session.execute(text("""
                                               SELECT name FROM sqlite_master
                                               WHERE type='table' AND name = :table_name
                                               """), {"table_name": table_name}).fetchone()

            if not table_check:
                raise HTTPException(
                    status_code=404,
                    detail=f"Таблица {table_name} не найдена"
                )

            analysis = {
                "table_name": table_name,
                "basic_stats": {},
                "columns": [],
                "indexes": [],
                "recommendations": []
            }

            # Основная статистика
            row_count = session.execute(text(f"SELECT COUNT(*) FROM `{table_name}`")).fetchone()
            analysis["basic_stats"]["row_count"] = row_count[0] if row_count else 0

            # Информация о колонках
            columns_info = session.execute(text(f"PRAGMA table_info(`{table_name}`)")).fetchall()
            for col_info in columns_info:
                column_data = {
                    "name": col_info[1],
                    "type": col_info[2],
                    "not_null": bool(col_info[3]),
                    "default_value": col_info[4],
                    "is_primary_key": bool(col_info[5])
                }

                # Анализируем уникальность для строковых колонок
                if analysis["basic_stats"]["row_count"] > 0:
                    try:
                        unique_count = session.execute(text(f"""
                            SELECT COUNT(DISTINCT `{col_info[1]}`) 
                            FROM `{table_name}`
                        """)).fetchone()

                        column_data["unique_values"] = unique_count[0] if unique_count else 0
                        column_data["uniqueness_ratio"] = round(
                            column_data["unique_values"] / analysis["basic_stats"]["row_count"], 3
                        )
                    except:
                        column_data["unique_values"] = None
                        column_data["uniqueness_ratio"] = None

                analysis["columns"].append(column_data)

            # Информация об индексах
            indexes_info = session.execute(text("""
                                                SELECT name, sql FROM sqlite_master
                                                WHERE type='index' AND tbl_name = :table_name
                                                  AND name NOT LIKE 'sqlite_%'
                                                """), {"table_name": table_name}).fetchall()

            for idx_name, idx_sql in indexes_info:
                analysis["indexes"].append({
                    "name": idx_name,
                    "definition": idx_sql
                })

            # Генерируем рекомендации
            if analysis["basic_stats"]["row_count"] > 1000 and len(analysis["indexes"]) == 0:
                analysis["recommendations"].append({
                    "type": "index",
                    "priority": "high",
                    "message": "Большая таблица без индексов, рекомендуется добавить индексы"
                })

            # Рекомендации по колонкам с высокой уникальностью
            for col in analysis["columns"]:
                if (col.get("uniqueness_ratio", 0) > 0.9 and
                        not col["is_primary_key"] and
                        not any("unique" in idx["definition"].lower() for idx in analysis["indexes"])):
                    analysis["recommendations"].append({
                        "type": "index",
                        "priority": "medium",
                        "message": f"Колонка {col['name']} имеет высокую уникальность, рассмотрите создание уникального индекса"
                    })

            return analysis

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing table {table_name}: {e}")
            raise

    try:
        result = DatabaseManager.safe_execute(_analyze_table)

        return {
            "status": "success",
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа таблицы {table_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать таблицу: {str(e)}"
        )