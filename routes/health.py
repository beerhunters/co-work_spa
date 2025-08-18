# ================== routes/health.py ==================
import time
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from datetime import datetime
from models.models import DatabaseManager
from dependencies import verify_token
from config import DATA_DIR, MOSCOW_TZ
from utils.database_maintenance import get_database_stats, optimize_database
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/database")
async def database_health(_: str = Depends(verify_token)):
    """Проверяет состояние базы данных."""
    try:

        def _test_connection(session):
            result = session.execute(text("SELECT 1")).scalar()
            return result == 1

        start_time = time.time()
        connection_ok = DatabaseManager.safe_execute(_test_connection)
        connection_time = time.time() - start_time

        db_stats = get_database_stats()

        return {
            "status": (
                "healthy" if connection_ok and connection_time < 2.0 else "degraded"
            ),
            "connection_ok": connection_ok,
            "connection_time": round(connection_time, 3),
            "database_stats": db_stats,
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка проверки здоровья БД: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }


@router.post("/database/optimize")
async def optimize_database_endpoint(_: str = Depends(verify_token)):
    """Оптимизирует базу данных."""
    try:
        optimize_database()
        return {
            "status": "success",
            "message": "Оптимизация базы данных завершена",
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }
    except Exception as e:
        logger.error(f"Ошибка оптимизации БД: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }


@router.get("/database/status")
async def get_database_status(_: str = Depends(verify_token)):
    """Получение подробного статуса базы данных."""
    try:
        stats = get_database_stats()
        return {
            **stats,
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }
    except Exception as e:
        logger.error(f"Ошибка получения статуса БД: {e}")
        return {"error": str(e), "timestamp": datetime.now(MOSCOW_TZ).isoformat()}


@router.get("/system")
async def system_health():
    """Общее состояние системы."""
    import shutil
    import psutil

    try:
        # Информация о дисковом пространстве
        disk_usage = shutil.disk_usage(DATA_DIR)

        # Информация о памяти
        memory = psutil.virtual_memory()

        # Информация о процессоре
        cpu_percent = psutil.cpu_percent(interval=1)

        return {
            "status": "healthy",
            "disk": {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round((disk_usage.total - disk_usage.free) / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "usage_percent": round(
                    ((disk_usage.total - disk_usage.free) / disk_usage.total) * 100, 1
                ),
            },
            "memory": {
                "total_mb": round(memory.total / (1024**2), 2),
                "available_mb": round(memory.available / (1024**2), 2),
                "usage_percent": memory.percent,
            },
            "cpu": {
                "usage_percent": cpu_percent,
            },
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка получения системной информации: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(MOSCOW_TZ).isoformat(),
        }
