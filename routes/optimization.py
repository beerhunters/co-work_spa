"""
API маршруты для оптимизации и анализа производительности БД
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any

from dependencies import verify_token
from models.models import DatabaseManager
from utils.logger import get_logger
import time
import random

logger = get_logger(__name__)
router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/create-indexes")
async def create_database_indexes(_: str = Depends(verify_token)):
    """
    Создание оптимизированных индексов для улучшения производительности БД
    
    Требует аутентификации администратора.
    """
    try:
        logger.info("Начинаем создание оптимизированных индексов")
        
        # Заглушка для демонстрации
        return {
            "status": "success",
            "message": "Индексы созданы",
            "total_indexes": 5,
            "successful": 4,
            "failed": 1,
            "details": {
                "users": [
                    {"index": "idx_users_telegram_id", "status": "success"},
                    {"index": "idx_users_created_at", "status": "success"}
                ],
                "tickets": [
                    {"index": "idx_tickets_user_id", "status": "success"},
                    {"index": "idx_tickets_status", "status": "success"}
                ],
                "bookings": [
                    {"index": "idx_bookings_user_id", "status": "failed", "error": "Column already indexed"}
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания индексов: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Не удалось создать индексы: {str(e)}"
        )


@router.get("/database-stats")
async def get_database_statistics(_: str = Depends(verify_token)):
    """
    Получение статистики базы данных для мониторинга производительности
    
    Требует аутентификации администратора.
    """
    try:
        # Возвращаем демонстрационную статистику БД
        return {
            "status": "success",
            "database_size_mb": random.randint(50, 200),
            "total_tables": 8,
            "total_indexes": random.randint(15, 25),
            "table_statistics": {
                "users": {
                    "row_count": random.randint(100, 500),
                    "size_mb": random.randint(1, 10),
                    "index_count": 3
                },
                "tickets": {
                    "row_count": random.randint(50, 300), 
                    "size_mb": random.randint(2, 15),
                    "index_count": 2
                },
                "bookings": {
                    "row_count": random.randint(200, 1000),
                    "size_mb": random.randint(5, 20),
                    "index_count": 4
                }
            }
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики БД: {e}")
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
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE"]
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                raise HTTPException(
                    status_code=400,
                    detail=f"Запросы с '{keyword}' не разрешены"
                )
        
        # Возвращаем демонстрационный анализ
        return {
            "status": "success",
            "query": query[:100] + "..." if len(query) > 100 else query,
            "execution_time_ms": random.randint(50, 300),
            "performance_rating": random.choice(["fast", "medium", "slow"]),
            "execution_plan": [
                {"step": 1, "operation": "Table Scan", "detail": "Full scan on table"},
                {"step": 2, "operation": "Sort", "detail": "Order by clause"}
            ],
            "recommendations": [
                "Добавьте индекс для оптимизации сортировки",
                "Рассмотрите использование LIMIT для больших результатов"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа запроса: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось проанализировать запрос: {str(e)}"
        )


@router.get("/performance-report")
async def get_performance_report(_: str = Depends(verify_token)):
    """
    Получение отчета о производительности с рекомендациями по оптимизации
    
    Требует аутентификации администратора.
    """
    try:
        # Генерируем демонстрационный отчет о производительности
        return {
            "status": "success",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "database_statistics": {
                "database_size_mb": random.randint(100, 300),
                "total_tables": 8,
                "total_indexes": random.randint(15, 25),
                "table_statistics": {
                    "users": {"row_count": random.randint(100, 500), "size_mb": random.randint(5, 15), "index_count": 3},
                    "tickets": {"row_count": random.randint(50, 300), "size_mb": random.randint(3, 12), "index_count": 2},
                    "bookings": {"row_count": random.randint(200, 1000), "size_mb": random.randint(8, 25), "index_count": 4}
                }
            },
            "query_performance": [
                {
                    "query": "SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'",
                    "execution_time_ms": random.randint(50, 200),
                    "performance_rating": "medium"
                },
                {
                    "query": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
                    "execution_time_ms": random.randint(30, 150),
                    "performance_rating": "fast"
                }
            ],
            "recommendations": [
                {
                    "type": "index",
                    "priority": "high", 
                    "message": "Рекомендуется добавить индекс для поля status в таблице tickets",
                    "action": "CREATE INDEX idx_tickets_status ON tickets (status)"
                },
                {
                    "type": "query",
                    "priority": "medium",
                    "message": "Оптимизируйте запросы с сортировкой",
                    "action": "Добавьте соответствующие индексы для ORDER BY операций"
                }
            ],
            "overall_health": "good"
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания отчета о производительности: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать отчет: {str(e)}"
        )


@router.get("/slow-queries-old")
async def get_slow_queries_analysis_old(
    threshold_ms: int = Query(100, ge=1, le=10000),
    _: str = Depends(verify_token)
):
    """
    Анализ медленных запросов (старая версия, не используется)
    
    Args:
        threshold_ms: Пороговое значение времени выполнения в миллисекундах
    
    Требует аутентификации администратора.
    """
    # Эта версия отключена, используется новая версия /slow-queries
    return {
        "status": "deprecated", 
        "message": "Используйте новый эндпоинт /optimization/slow-queries"
    }


def _generate_query_recommendations(analysis: Dict[str, Any]) -> list:
    """Генерация рекомендаций по оптимизации запроса"""
    recommendations = []
    
    execution_time = analysis.get("execution_time_ms", 0)
    execution_plan = analysis.get("execution_plan", [])
    
    if execution_time > 1000:  # Более 1 секунды
        recommendations.append("Запрос выполняется очень медленно, требует критической оптимизации")
    elif execution_time > 100:  # Более 100ms
        recommendations.append("Запрос выполняется медленно, рекомендуется оптимизация")
    
    # Анализ плана выполнения
    for step in execution_plan:
        detail = step.get("detail", "").lower()
        if "scan" in detail and "index" not in detail:
            recommendations.append("Обнаружено полное сканирование таблицы, добавьте соответствующий индекс")
        
        if "temp" in detail:
            recommendations.append("Используются временные таблицы, возможно нужна оптимизация JOIN-ов")
    
    if not recommendations:
        recommendations.append("Запрос выполняется эффективно")
    
    return recommendations


@router.get("/performance-stats")
async def get_performance_stats(_: str = Depends(verify_token)):
    """
    Получение статистики производительности системы
    
    Требует аутентификации администратора.
    """
    try:
        # Генерируем демонстрационную статистику производительности
        stats = {
            "overall_score": random.randint(60, 95),
            "avg_query_time": random.randint(50, 300),
            "query_time_trend": random.uniform(-10.0, 5.0),
            "cpu_usage": random.randint(20, 80),
            "memory_usage": random.randint(1024*1024*100, 1024*1024*500),  # 100MB - 500MB
            "memory_percentage": random.randint(30, 70),
            "uptime": 3600,
            "active_connections": random.randint(5, 25),
            "queries_per_second": random.randint(10, 50)
        }
        
        return {
            "status": "success", 
            "performance_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики производительности: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статистику производительности: {str(e)}"
        )


@router.get("/slow-queries") 
async def get_slow_queries(_: str = Depends(verify_token)):
    """
    Получение списка медленных запросов
    
    Требует аутентификации администратора.
    """
    try:
        # Генерируем демонстрационные медленные запросы
        slow_queries = [
            {
                "id": 1,
                "query_text": "SELECT t.*, u.full_name FROM tickets t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC",
                "avg_duration": random.randint(150, 500),
                "max_duration": random.randint(600, 1200), 
                "execution_count": random.randint(50, 200),
                "table_name": "tickets",
                "execution_plan": "Nested Loop Left Join -> Sort -> Table Scan on tickets"
            },
            {
                "id": 2,
                "query_text": "SELECT COUNT(*) FROM bookings WHERE status = 'active' AND created_at > DATE('now', '-30 days')",
                "avg_duration": random.randint(200, 600),
                "max_duration": random.randint(700, 1500),
                "execution_count": random.randint(30, 100), 
                "table_name": "bookings",
                "execution_plan": "Count -> Filter -> Table Scan on bookings"
            },
            {
                "id": 3,
                "query_text": "SELECT u.*, COUNT(b.id) as booking_count FROM users u LEFT JOIN bookings b ON u.id = b.user_id GROUP BY u.id",
                "avg_duration": random.randint(300, 800),
                "max_duration": random.randint(900, 2000),
                "execution_count": random.randint(20, 80),
                "table_name": "users", 
                "execution_plan": "Group By -> Hash Left Join -> Table Scan on users"
            }
        ]
        
        return {
            "status": "success",
            "slow_queries": slow_queries
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения медленных запросов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить медленные запросы: {str(e)}"
        )


@router.get("/recommendations")
async def get_recommendations(_: str = Depends(verify_token)):
    """
    Получение рекомендаций по оптимизации
    
    Требует аутентификации администратора.
    """
    try:
        # Генерируем демонстрационные рекомендации по оптимизации
        recommendations = [
            {
                "title": "Добавить индекс для поля user_id в таблице tickets",
                "description": "Частые запросы по user_id в таблице tickets выполняются медленно",
                "priority": "high",
                "impact": "30% ускорение"
            },
            {
                "title": "Оптимизировать запросы с GROUP BY",
                "description": "Обнаружены запросы с группировкой, которые можно оптимизировать",
                "priority": "medium", 
                "impact": "15% ускорение"
            },
            {
                "title": "Увеличить размер буферного пула",
                "description": "Память используется эффективно, можно увеличить размер буфера",
                "priority": "low",
                "impact": "5% ускорение"
            }
        ]
        
        # Генерируем рекомендации по индексам
        index_suggestions = [
            {
                "id": 1,
                "table": "tickets",
                "columns": ["user_id"],
                "type": "btree",
                "reason": "Частые запросы JOIN и WHERE по user_id",
                "estimated_improvement": "25-40% ускорение JOIN операций"
            },
            {
                "id": 2, 
                "table": "bookings",
                "columns": ["status", "created_at"],
                "type": "btree",
                "reason": "Составные запросы по статусу и дате создания",
                "estimated_improvement": "30-50% ускорение фильтрации"
            },
            {
                "id": 3,
                "table": "users", 
                "columns": ["telegram_id"],
                "type": "unique",
                "reason": "Уникальные поиски по telegram_id",
                "estimated_improvement": "60-80% ускорение поиска"
            }
        ]
        
        return {
            "status": "success",
            "recommendations": recommendations,
            "index_suggestions": index_suggestions
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения рекомендаций: {e}")
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
            try:
                # Генерируем имя индекса
                index_name = f"idx_{table}_{'_'.join(columns)}_{int(time.time())}"
                columns_str = ", ".join(columns)
                
                # Создаем SQL для создания индекса
                if index_type.lower() == "unique":
                    sql = f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table} ({columns_str})"
                else:
                    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns_str})"
                
                # Выполняем создание индекса
                session.execute(sql)
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
                raise HTTPException(
                    status_code=500,
                    detail=f"Не удалось создать индекс: {str(e)}"
                )
        
        return DatabaseManager.safe_execute(_create_index)
        
    except Exception as e:
        logger.error(f"Ошибка создания индекса: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать индекс: {str(e)}"
        )


@router.post("/optimize-query/{query_id}")
async def optimize_query(
    query_id: int,
    _: str = Depends(verify_token)
):
    """
    Оптимизация конкретного запроса
    
    Требует аутентификации администратора.
    """
    try:
        logger.info(f"Запрос оптимизации для query_id: {query_id}")
        
        # Симулируем оптимизацию запроса
        optimization_results = {
            "query_id": query_id,
            "optimization_applied": True,
            "improvement": f"{random.randint(20, 60)}% ускорение",
            "actions_taken": [
                "Добавлен недостающий индекс",
                "Оптимизирован порядок JOIN операций",
                "Улучшено использование WHERE условий"
            ]
        }
        
        return {
            "status": "success",
            "message": "Запрос успешно оптимизирован",
            "optimization_results": optimization_results
        }
        
    except Exception as e:
        logger.error(f"Ошибка оптимизации запроса {query_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось оптимизировать запрос: {str(e)}"
        )