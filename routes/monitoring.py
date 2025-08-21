"""
Endpoints для мониторинга и метрик приложения
"""
import os
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from config import MOSCOW_TZ, DATA_DIR
from dependencies import verify_token
from models.models import DatabaseManager, get_db_health, ConnectionPoolMonitor
from utils.structured_logging import get_metrics, get_structured_logger
from utils.rate_limiter import get_rate_limiter

logger = get_structured_logger(__name__)
router = APIRouter(prefix="/monitoring", tags=["monitoring"])

@router.get("/health/detailed")
async def detailed_health_check():
    """Детальная проверка здоровья системы"""
    start_time = time.time()
    
    health_status = {
        "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        "status": "healthy",
        "checks": {},
        "response_time_ms": 0
    }
    
    # 1. Database Health
    try:
        db_health = get_db_health()
        health_status["checks"]["database"] = {
            "status": "healthy" if db_health.get("connection_ok", False) else "unhealthy",
            "details": db_health
        }
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # 2. System Resources
    try:
        # Memory
        memory = psutil.virtual_memory()
        disk_usage = psutil.disk_usage(str(DATA_DIR))
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Определяем статус на основе использования ресурсов
        memory_status = "healthy" if memory.percent < 85 else "warning" if memory.percent < 95 else "critical"
        disk_status = "healthy" if (disk_usage.used / disk_usage.total * 100) < 85 else "warning"
        cpu_status = "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 95 else "critical"
        
        health_status["checks"]["system_resources"] = {
            "status": "healthy" if all(s == "healthy" for s in [memory_status, disk_status, cpu_status]) else "warning",
            "memory": {
                "total_mb": round(memory.total / (1024**2)),
                "used_mb": round(memory.used / (1024**2)),
                "available_mb": round(memory.available / (1024**2)),
                "percent": memory.percent,
                "status": memory_status
            },
            "disk": {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent": round(disk_usage.used / disk_usage.total * 100, 1),
                "status": disk_status
            },
            "cpu": {
                "percent": cpu_percent,
                "status": cpu_status
            }
        }
        
        if health_status["checks"]["system_resources"]["status"] == "warning":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["system_resources"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # 3. Rate Limiter Status
    try:
        rate_limiter = get_rate_limiter()
        rl_stats = rate_limiter.get_stats()
        health_status["checks"]["rate_limiter"] = {
            "status": "healthy",
            "details": rl_stats
        }
    except Exception as e:
        health_status["checks"]["rate_limiter"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # 4. Application Metrics Summary
    try:
        metrics = get_metrics()
        metrics_summary = metrics.get_metrics_summary()
        
        # Простая проверка - если много ошибок, статус degraded
        error_rate = metrics_summary["counters"].get("errors_total", 0) / max(metrics_summary["counters"].get("requests_total", 1), 1)
        if error_rate > 0.1:  # Более 10% ошибок
            health_status["status"] = "degraded"
        
        health_status["checks"]["metrics"] = {
            "status": "healthy" if error_rate <= 0.1 else "degraded",
            "error_rate": round(error_rate * 100, 2),
            "summary": metrics_summary
        }
    except Exception as e:
        health_status["checks"]["metrics"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    # Логируем результат health check
    logger.info(
        f"Health check completed",
        extra={
            "health_status": health_status["status"],
            "response_time_ms": health_status["response_time_ms"],
            "checks_count": len(health_status["checks"])
        }
    )
    
    return health_status

@router.get("/metrics")
async def get_application_metrics(
    summary: bool = Query(True, description="Возвращать сводку или полные метрики")
):
    """Получение метрик приложения"""
    metrics = get_metrics()
    
    if summary:
        return metrics.get_metrics_summary()
    else:
        return metrics.get_metrics()

@router.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Метрики в формате Prometheus"""
    metrics = get_metrics()
    metrics_data = metrics.get_metrics_summary()
    
    prometheus_output = []
    
    # Добавляем counters
    for metric_name, value in metrics_data["counters"].items():
        prometheus_output.append(f"# HELP {metric_name} Application counter metric")
        prometheus_output.append(f"# TYPE {metric_name} counter")
        prometheus_output.append(f"{metric_name} {value}")
        prometheus_output.append("")
    
    # Добавляем histograms
    for metric_name, histogram in metrics_data["histograms"].items():
        base_name = metric_name.replace("_histogram", "")
        prometheus_output.append(f"# HELP {base_name} Application histogram metric")
        prometheus_output.append(f"# TYPE {base_name} histogram")
        prometheus_output.append(f"{base_name}_count {histogram['count']}")
        prometheus_output.append(f"{base_name}_sum {histogram['mean'] * histogram['count']}")
        prometheus_output.append(f"{base_name}_bucket{{le=\"+Inf\"}} {histogram['count']}")
        prometheus_output.append("")
    
    return "\n".join(prometheus_output)

@router.get("/database/stats")
async def get_database_statistics(_: str = Depends(verify_token)):
    """Подробная статистика базы данных"""
    
    def _get_table_stats(session):
        """Получение статистики таблиц"""
        tables_info = []
        
        # Получаем список таблиц
        tables_result = session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        ).fetchall()
        
        for (table_name,) in tables_result:
            # Количество записей
            count_result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            
            # Размер таблицы (приблизительно)
            try:
                size_result = session.execute(
                    text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                ).scalar()
            except:
                size_result = 0
            
            tables_info.append({
                "table_name": table_name,
                "record_count": count_result,
                "estimated_size_kb": round(size_result / 1024, 2) if size_result else 0
            })
        
        return tables_info
    
    try:
        # Статистика пула соединений
        pool_stats = ConnectionPoolMonitor.get_pool_status()
        
        # Статистика таблиц
        table_stats = DatabaseManager.safe_execute(_get_table_stats)
        
        # Database file info
        db_path = DATA_DIR / "coworking.db"
        db_size = db_path.stat().st_size if db_path.exists() else 0
        
        return {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "database_file": {
                "path": str(db_path),
                "size_mb": round(db_size / (1024**2), 2),
                "exists": db_path.exists()
            },
            "connection_pool": pool_stats,
            "tables": table_stats,
            "total_records": sum(table["record_count"] for table in table_stats)
        }
        
    except Exception as e:
        logger.error(f"Error getting database statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database statistics error: {str(e)}")

@router.get("/performance/slow-queries")
async def get_slow_queries(
    limit: int = Query(50, ge=1, le=500),
    _: str = Depends(verify_token)
):
    """Получение информации о медленных запросах"""
    # В реальном приложении здесь была бы логика сбора медленных запросов
    # Пока возвращаем заглушку
    return {
        "message": "Slow queries monitoring not implemented yet",
        "note": "This would require query logging and analysis",
        "timestamp": datetime.now(MOSCOW_TZ).isoformat()
    }

@router.get("/alerts")
async def get_system_alerts(_: str = Depends(verify_token)):
    """Получение системных предупреждений"""
    alerts = []
    current_time = datetime.now(MOSCOW_TZ)
    
    try:
        # Проверяем ресурсы системы
        memory = psutil.virtual_memory()
        disk_usage = psutil.disk_usage(str(DATA_DIR))
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory alerts
        if memory.percent > 90:
            alerts.append({
                "id": "high_memory_usage",
                "severity": "critical" if memory.percent > 95 else "warning",
                "title": "Высокое использование памяти",
                "message": f"Использование памяти: {memory.percent}%",
                "timestamp": current_time.isoformat(),
                "value": memory.percent,
                "threshold": 90
            })
        
        # Disk alerts
        disk_percent = disk_usage.used / disk_usage.total * 100
        if disk_percent > 85:
            alerts.append({
                "id": "high_disk_usage",
                "severity": "critical" if disk_percent > 95 else "warning",
                "title": "Высокое использование диска",
                "message": f"Использование диска: {disk_percent:.1f}%",
                "timestamp": current_time.isoformat(),
                "value": round(disk_percent, 1),
                "threshold": 85
            })
        
        # CPU alerts
        if cpu_percent > 85:
            alerts.append({
                "id": "high_cpu_usage",
                "severity": "critical" if cpu_percent > 95 else "warning",
                "title": "Высокая загрузка CPU",
                "message": f"Загрузка CPU: {cpu_percent}%",
                "timestamp": current_time.isoformat(),
                "value": cpu_percent,
                "threshold": 85
            })
        
        # Error rate alerts
        metrics = get_metrics()
        metrics_summary = metrics.get_metrics_summary()
        error_rate = metrics_summary["counters"].get("errors_total", 0) / max(metrics_summary["counters"].get("requests_total", 1), 1)
        
        if error_rate > 0.05:  # Более 5% ошибок
            alerts.append({
                "id": "high_error_rate",
                "severity": "critical" if error_rate > 0.1 else "warning",
                "title": "Высокий уровень ошибок",
                "message": f"Процент ошибок: {error_rate * 100:.1f}%",
                "timestamp": current_time.isoformat(),
                "value": round(error_rate * 100, 1),
                "threshold": 5.0
            })
        
        # Rate limiting alerts
        rate_limit_count = metrics_summary["counters"].get("rate_limits_exceeded", 0)
        if rate_limit_count > 10:  # Более 10 превышений rate limit
            alerts.append({
                "id": "high_rate_limiting",
                "severity": "warning",
                "title": "Частые превышения rate limit",
                "message": f"Превышений rate limit: {rate_limit_count}",
                "timestamp": current_time.isoformat(),
                "value": rate_limit_count,
                "threshold": 10
            })
        
        return {
            "timestamp": current_time.isoformat(),
            "alerts_count": len(alerts),
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"Error generating alerts: {e}", exc_info=True)
        return {
            "timestamp": current_time.isoformat(),
            "alerts_count": 0,
            "alerts": [],
            "error": str(e)
        }

@router.post("/metrics/reset")
async def reset_metrics(_: str = Depends(verify_token)):
    """Сброс метрик приложения"""
    metrics = get_metrics()
    metrics.metrics.clear()
    
    # Инициализируем базовые метрики
    metrics.metrics.update({
        "requests_total": 0,
        "requests_by_endpoint": {},
        "requests_by_status": {},
        "response_times": [],
        "errors_total": 0,
        "auth_failures": 0,
        "rate_limits_exceeded": 0,
        "active_sessions": 0,
    })
    
    logger.info("Application metrics reset by admin")
    
    return {
        "message": "Метрики успешно сброшены",
        "timestamp": datetime.now(MOSCOW_TZ).isoformat()
    }