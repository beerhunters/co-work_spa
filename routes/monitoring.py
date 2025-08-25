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
from utils.rate_limiter import get_rate_limiter
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# Глобальная переменная для хранения метрик (должна быть заменена на Redis/базу)
# TODO: Заменить на постоянное хранилище метрик
_metrics_storage = {
    "requests_total": 0,
    "errors_total": 0,
    "requests_by_endpoint": {},
    "requests_by_status": {},
    "response_times": [],
    "auth_failures": 0,
    "rate_limits_exceeded": 0,
    "active_sessions": 0,
}


def increment_metric(metric_name: str, value: int = 1):
    """Увеличить значение метрики"""
    global _metrics_storage
    if metric_name in _metrics_storage:
        _metrics_storage[metric_name] += value


def record_response_time(time_ms: float):
    """Записать время ответа"""
    global _metrics_storage
    _metrics_storage["response_times"].append(time_ms)
    # Ограничиваем размер массива временами ответа
    if len(_metrics_storage["response_times"]) > 1000:
        _metrics_storage["response_times"] = _metrics_storage["response_times"][-1000:]


def record_endpoint_request(endpoint: str):
    """Записать запрос к endpoint"""
    global _metrics_storage
    if endpoint not in _metrics_storage["requests_by_endpoint"]:
        _metrics_storage["requests_by_endpoint"][endpoint] = 0
    _metrics_storage["requests_by_endpoint"][endpoint] += 1


def record_status_code(status_code: int):
    """Записать статус код ответа"""
    global _metrics_storage
    status_str = str(status_code)
    if status_str not in _metrics_storage["requests_by_status"]:
        _metrics_storage["requests_by_status"][status_str] = 0
    _metrics_storage["requests_by_status"][status_str] += 1


def get_metrics_summary():
    """Возвращает сводку метрик"""
    global _metrics_storage

    avg_response_time = (
        sum(_metrics_storage["response_times"]) / len(_metrics_storage["response_times"])
        if _metrics_storage["response_times"] else 0
    )

    return {
        "counters": {
            "requests_total": _metrics_storage["requests_total"],
            "errors_total": _metrics_storage["errors_total"],
            "auth_failures": _metrics_storage["auth_failures"],
            "rate_limits_exceeded": _metrics_storage["rate_limits_exceeded"],
            "active_sessions": _metrics_storage["active_sessions"],
        },
        "histograms": {
            "response_times_histogram": {
                "count": len(_metrics_storage["response_times"]),
                "mean": round(avg_response_time, 2),
                "max": max(_metrics_storage["response_times"]) if _metrics_storage["response_times"] else 0,
                "min": min(_metrics_storage["response_times"]) if _metrics_storage["response_times"] else 0,
            }
        },
        "by_endpoint": _metrics_storage["requests_by_endpoint"],
        "by_status": _metrics_storage["requests_by_status"],
    }


@router.get("/health/detailed")
async def detailed_health_check():
    """Детальная проверка здоровья системы"""
    start_time = time.time()

    health_status = {
        "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        "status": "healthy",
        "checks": {},
        "response_time_ms": 0,
    }

    # 1. Database Health
    try:
        db_health = get_db_health()
        health_status["checks"]["database"] = {
            "status": (
                "healthy" if db_health.get("connection_ok", False) else "unhealthy"
            ),
            "details": db_health,
        }

        if not db_health.get("connection_ok", False):
            health_status["status"] = "unhealthy"

    except Exception as e:
        health_status["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"

    # 2. System Resources
    try:
        # Memory
        memory = psutil.virtual_memory()
        disk_usage = psutil.disk_usage(str(DATA_DIR))
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Определяем статус на основе использования ресурсов
        memory_status = (
            "healthy"
            if memory.percent < 85
            else "warning" if memory.percent < 95 else "critical"
        )
        disk_status = (
            "healthy" if (disk_usage.used / disk_usage.total * 100) < 85 else "warning"
        )
        cpu_status = (
            "healthy"
            if cpu_percent < 80
            else "warning" if cpu_percent < 95 else "critical"
        )

        resource_status = "healthy"
        if any(s == "critical" for s in [memory_status, disk_status, cpu_status]):
            resource_status = "critical"
            health_status["status"] = "unhealthy"
        elif any(s == "warning" for s in [memory_status, disk_status, cpu_status]):
            resource_status = "warning"
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"

        health_status["checks"]["system_resources"] = {
            "status": resource_status,
            "memory": {
                "total_mb": round(memory.total / (1024**2)),
                "used_mb": round(memory.used / (1024**2)),
                "available_mb": round(memory.available / (1024**2)),
                "percent": round(memory.percent, 1),
                "status": memory_status,
            },
            "disk": {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent": round(disk_usage.used / disk_usage.total * 100, 1),
                "status": disk_status,
            },
            "cpu": {"percent": round(cpu_percent, 1), "status": cpu_status},
        }

    except Exception as e:
        health_status["checks"]["system_resources"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "unhealthy"

    # 3. Rate Limiter Status
    try:
        rate_limiter = get_rate_limiter()
        rl_stats = rate_limiter.get_stats()
        health_status["checks"]["rate_limiter"] = {
            "status": "healthy",
            "details": rl_stats,
        }
    except Exception as e:
        health_status["checks"]["rate_limiter"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # 4. Application Metrics Summary
    try:
        metrics_summary = get_metrics_summary()

        # Проверка на высокий уровень ошибок
        total_requests = metrics_summary["counters"].get("requests_total", 0)
        total_errors = metrics_summary["counters"].get("errors_total", 0)

        if total_requests > 0:
            error_rate = total_errors / total_requests
            metrics_status = "healthy" if error_rate <= 0.05 else "degraded"

            if error_rate > 0.05 and health_status["status"] == "healthy":
                health_status["status"] = "degraded"
        else:
            error_rate = 0
            metrics_status = "healthy"

        health_status["checks"]["metrics"] = {
            "status": metrics_status,
            "error_rate_percent": round(error_rate * 100, 2),
            "total_requests": total_requests,
            "total_errors": total_errors,
        }
    except Exception as e:
        health_status["checks"]["metrics"] = {"status": "unhealthy", "error": str(e)}

    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    # Логируем результат health check
    logger.info(
        f"Health check completed",
        extra={
            "health_status": health_status["status"],
            "response_time_ms": health_status["response_time_ms"],
            "checks_count": len(health_status["checks"]),
        },
    )

    return health_status


@router.get("/metrics")
async def get_application_metrics(
        summary: bool = Query(True, description="Возвращать сводку или полные метрики")
):
    """Получение метрик приложения"""
    if summary:
        return get_metrics_summary()
    else:
        return {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "metrics": _metrics_storage
        }


@router.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Метрики в формате Prometheus"""
    metrics_data = get_metrics_summary()
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
        prometheus_output.append(
            f"{base_name}_sum {histogram['mean'] * histogram['count']}"
        )
        prometheus_output.append(
            f"{base_name}_bucket{{le=\"+Inf\"}} {histogram['count']}"
        )
        prometheus_output.append("")

    return "\n".join(prometheus_output)


@router.get("/database/stats")
async def get_database_statistics(_: str = Depends(verify_token)):
    """Подробная статистика базы данных"""

    def _get_table_stats(session):
        """Получение статистики таблиц"""
        tables_info = []

        try:
            # Получаем список таблиц
            tables_result = session.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            ).fetchall()

            for (table_name,) in tables_result:
                try:
                    # Количество записей
                    count_result = session.execute(
                        text(f"SELECT COUNT(*) FROM `{table_name}`")
                    ).scalar()

                    tables_info.append(
                        {
                            "table_name": table_name,
                            "record_count": count_result or 0,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Could not get stats for table {table_name}: {e}")
                    tables_info.append(
                        {
                            "table_name": table_name,
                            "record_count": 0,
                            "error": str(e)
                        }
                    )

        except Exception as e:
            logger.error(f"Error getting table list: {e}")

        return tables_info

    try:
        # Статистика пула соединений
        pool_stats = ConnectionPoolMonitor.get_pool_status()

        # Статистика таблиц
        table_stats = DatabaseManager.safe_execute(_get_table_stats) or []

        # Database file info
        db_path = DATA_DIR / "coworking.db"
        db_size = db_path.stat().st_size if db_path.exists() else 0

        return {
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
            "database_file": {
                "path": str(db_path),
                "size_mb": round(db_size / (1024**2), 2),
                "exists": db_path.exists(),
            },
            "connection_pool": pool_stats,
            "tables": table_stats,
            "total_records": sum(
                table.get("record_count", 0) for table in table_stats
                if isinstance(table.get("record_count"), int)
            ),
        }

    except Exception as e:
        logger.error(f"Error getting database statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Database statistics error: {str(e)}"
        )


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
            alerts.append(
                {
                    "id": "high_memory_usage",
                    "severity": "critical" if memory.percent > 95 else "warning",
                    "title": "Высокое использование памяти",
                    "message": f"Использование памяти: {memory.percent:.1f}%",
                    "timestamp": current_time.isoformat(),
                    "value": round(memory.percent, 1),
                    "threshold": 90,
                }
            )

        # Disk alerts
        disk_percent = disk_usage.used / disk_usage.total * 100
        if disk_percent > 85:
            alerts.append(
                {
                    "id": "high_disk_usage",
                    "severity": "critical" if disk_percent > 95 else "warning",
                    "title": "Высокое использование диска",
                    "message": f"Использование диска: {disk_percent:.1f}%",
                    "timestamp": current_time.isoformat(),
                    "value": round(disk_percent, 1),
                    "threshold": 85,
                }
            )

        # CPU alerts
        if cpu_percent > 85:
            alerts.append(
                {
                    "id": "high_cpu_usage",
                    "severity": "critical" if cpu_percent > 95 else "warning",
                    "title": "Высокая загрузка CPU",
                    "message": f"Загрузка CPU: {cpu_percent:.1f}%",
                    "timestamp": current_time.isoformat(),
                    "value": round(cpu_percent, 1),
                    "threshold": 85,
                }
            )

        # Error rate alerts
        metrics_summary = get_metrics_summary()
        total_requests = metrics_summary["counters"].get("requests_total", 0)
        total_errors = metrics_summary["counters"].get("errors_total", 0)

        if total_requests > 0:
            error_rate = total_errors / total_requests
            if error_rate > 0.05:  # Более 5% ошибок
                alerts.append(
                    {
                        "id": "high_error_rate",
                        "severity": "critical" if error_rate > 0.1 else "warning",
                        "title": "Высокий уровень ошибок",
                        "message": f"Процент ошибок: {error_rate * 100:.1f}%",
                        "timestamp": current_time.isoformat(),
                        "value": round(error_rate * 100, 1),
                        "threshold": 5.0,
                    }
                )

        # Rate limiting alerts
        rate_limit_count = metrics_summary["counters"].get("rate_limits_exceeded", 0)
        if rate_limit_count > 10:  # Более 10 превышений rate limit
            alerts.append(
                {
                    "id": "high_rate_limiting",
                    "severity": "warning",
                    "title": "Частые превышения rate limit",
                    "message": f"Превышений rate limit: {rate_limit_count}",
                    "timestamp": current_time.isoformat(),
                    "value": rate_limit_count,
                    "threshold": 10,
                }
            )

        return {
            "timestamp": current_time.isoformat(),
            "alerts_count": len(alerts),
            "alerts": alerts,
        }

    except Exception as e:
        logger.error(f"Error generating alerts: {e}", exc_info=True)
        return {
            "timestamp": current_time.isoformat(),
            "alerts_count": 0,
            "alerts": [],
            "error": str(e),
        }


@router.post("/metrics/reset")
async def reset_metrics(_: str = Depends(verify_token)):
    """Сброс метрик приложения"""
    global _metrics_storage

    _metrics_storage.clear()
    _metrics_storage.update({
        "requests_total": 0,
        "errors_total": 0,
        "requests_by_endpoint": {},
        "requests_by_status": {},
        "response_times": [],
        "auth_failures": 0,
        "rate_limits_exceeded": 0,
        "active_sessions": 0,
    })

    logger.info("Application metrics reset by admin")

    return {
        "message": "Метрики успешно сброшены",
        "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
    }


# Функции для интеграции с middleware для сбора метрик
def track_request(endpoint: str, status_code: int, response_time_ms: float):
    """Функция для отслеживания запросов из middleware"""
    global _metrics_storage

    _metrics_storage["requests_total"] += 1
    record_endpoint_request(endpoint)
    record_status_code(status_code)
    record_response_time(response_time_ms)

    if status_code >= 400:
        _metrics_storage["errors_total"] += 1


def track_auth_failure():
    """Отслеживание неудачной аутентификации"""
    global _metrics_storage
    _metrics_storage["auth_failures"] += 1


def track_rate_limit_exceeded():
    """Отслеживание превышения rate limit"""
    global _metrics_storage
    _metrics_storage["rate_limits_exceeded"] += 1


def set_active_sessions(count: int):
    """Установить количество активных сессий"""
    global _metrics_storage
    _metrics_storage["active_sessions"] = count