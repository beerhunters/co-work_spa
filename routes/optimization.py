"""
API маршруты для оптимизации и анализа производительности БД
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any

from dependencies import verify_token
from models.models import DatabaseManager
from utils.sql_optimization import SQLOptimizer
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
        try:
            logger.info("Начинаем создание оптимизированных индексов")
            results = SQLOptimizer.create_optimized_indexes(session)
            
            # Подсчитываем статистику
            total_indexes = 0
            successful_indexes = 0
            failed_indexes = 0
            
            for table_name, table_results in results.items():
                for result in table_results:
                    total_indexes += 1
                    if result["status"] == "success":
                        successful_indexes += 1
                    else:
                        failed_indexes += 1
            
            logger.info(f"Создание индексов завершено: {successful_indexes}/{total_indexes} успешно")
            
            return {
                "message": "Индексы созданы",
                "total_indexes": total_indexes,
                "successful": successful_indexes,
                "failed": failed_indexes,
                "details": results
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания индексов: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Не удалось создать индексы: {str(e)}"
            )
    
    return DatabaseManager.safe_execute(_create_indexes)


@router.get("/database-stats")
async def get_database_statistics(_: str = Depends(verify_token)):
    """
    Получение статистики базы данных для мониторинга производительности
    
    Требует аутентификации администратора.
    """
    def _get_db_stats(session):
        try:
            return SQLOptimizer.get_database_statistics(session)
        except Exception as e:
            logger.error(f"Ошибка получения статистики БД: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось получить статистику БД: {str(e)}"
            )
    
    return DatabaseManager.safe_execute(_get_db_stats)


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
    def _analyze_query(session):
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
            
            return SQLOptimizer.analyze_query_performance(session, query)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ошибка анализа запроса: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось проанализировать запрос: {str(e)}"
            )
    
    return DatabaseManager.safe_execute(_analyze_query)


@router.get("/performance-report")
async def get_performance_report(_: str = Depends(verify_token)):
    """
    Получение отчета о производительности с рекомендациями по оптимизации
    
    Требует аутентификации администратора.
    """
    def _get_performance_report(session):
        try:
            # Получаем статистику БД
            db_stats = SQLOptimizer.get_database_statistics(session)
            
            # Анализируем типичные запросы
            common_queries = [
                "SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'",
                "SELECT * FROM users ORDER BY created_at DESC LIMIT 10",
                "SELECT t.*, u.full_name FROM tickets t LEFT JOIN users u ON t.user_id = u.id LIMIT 10"
            ]
            
            query_analyses = []
            for query in common_queries:
                try:
                    analysis = SQLOptimizer.analyze_query_performance(session, query)
                    query_analyses.append(analysis)
                except Exception as e:
                    logger.warning(f"Не удалось проанализировать запрос '{query}': {e}")
            
            # Генерируем рекомендации
            recommendations = []
            
            # Рекомендации по таблицам с большим количеством записей
            for table_name, stats in db_stats.get("table_statistics", {}).items():
                if stats["row_count"] > 10000 and stats["index_count"] < 3:
                    recommendations.append({
                        "type": "index",
                        "priority": "high",
                        "message": f"Таблица {table_name} содержит {stats['row_count']} записей, но только {stats['index_count']} индексов. Рекомендуется добавить индексы.",
                        "action": f"Создайте индексы для часто используемых полей в таблице {table_name}"
                    })
            
            # Рекомендации по медленным запросам
            slow_queries = [q for q in query_analyses if q.get("performance_rating") in ["slow", "very_slow"]]
            if slow_queries:
                recommendations.append({
                    "type": "query",
                    "priority": "medium",
                    "message": f"Обнаружено {len(slow_queries)} медленных запросов",
                    "action": "Оптимизируйте медленные запросы или добавьте соответствующие индексы"
                })
            
            return {
                "timestamp": logger._formatTime(logger.formatter.converter(None)),
                "database_statistics": db_stats,
                "query_performance": query_analyses,
                "recommendations": recommendations,
                "overall_health": "good" if not recommendations else "needs_optimization"
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания отчета о производительности: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось создать отчет: {str(e)}"
            )
    
    return DatabaseManager.safe_execute(_get_performance_report)


@router.get("/slow-queries")
async def get_slow_queries_analysis(
    threshold_ms: int = Query(100, ge=1, le=10000),
    _: str = Depends(verify_token)
):
    """
    Анализ медленных запросов
    
    Args:
        threshold_ms: Пороговое значение времени выполнения в миллисекундах
    
    Требует аутентификации администратора.
    """
    def _analyze_slow_queries(session):
        try:
            # Список критически важных запросов для анализа
            critical_queries = [
                {
                    "name": "Dashboard Stats",
                    "query": """
                        SELECT 
                            (SELECT COUNT(*) FROM users) as total_users,
                            (SELECT COUNT(*) FROM bookings) as total_bookings,
                            (SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED') as open_tickets
                    """
                },
                {
                    "name": "Tickets with Users",
                    "query": """
                        SELECT t.*, u.full_name, u.telegram_id 
                        FROM tickets t 
                        LEFT JOIN users u ON t.user_id = u.id 
                        ORDER BY t.created_at DESC 
                        LIMIT 20
                    """
                },
                {
                    "name": "User Bookings Count",
                    "query": """
                        SELECT u.id, u.full_name, COUNT(b.id) as booking_count
                        FROM users u
                        LEFT JOIN bookings b ON u.id = b.user_id
                        GROUP BY u.id, u.full_name
                        ORDER BY booking_count DESC
                        LIMIT 10
                    """
                }
            ]
            
            slow_queries = []
            for query_info in critical_queries:
                analysis = SQLOptimizer.analyze_query_performance(session, query_info["query"])
                
                if analysis.get("execution_time_ms", 0) > threshold_ms:
                    slow_queries.append({
                        "name": query_info["name"],
                        "execution_time_ms": analysis.get("execution_time_ms"),
                        "performance_rating": analysis.get("performance_rating"),
                        "execution_plan": analysis.get("execution_plan", []),
                        "recommendations": _generate_query_recommendations(analysis)
                    })
            
            return {
                "threshold_ms": threshold_ms,
                "total_queries_analyzed": len(critical_queries),
                "slow_queries_found": len(slow_queries),
                "slow_queries": slow_queries
            }
            
        except Exception as e:
            logger.error(f"Ошибка анализа медленных запросов: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось проанализировать медленные запросы: {str(e)}"
            )
    
    return DatabaseManager.safe_execute(_analyze_slow_queries)


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