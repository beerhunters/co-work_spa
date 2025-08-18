# middleware.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import traceback

from utils.logger import get_logger
from utils.database_maintenance import check_db_health
from models.models import DatabaseManager
from sqlalchemy import text

logger = get_logger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware для обработки ошибок."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as exc:
            # HTTP исключения пропускаем как есть
            raise exc
        except Exception as exc:
            # Логируем неожиданные ошибки
            logger.error(f"Неожиданная ошибка: {exc}")
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )


class DatabaseMaintenanceMiddleware(BaseHTTPMiddleware):
    """Middleware для автоматического обслуживания БД."""

    async def dispatch(self, request: Request, call_next):
        # Выполняем обслуживание только для определенных запросов
        maintenance_paths = ["/dashboard/stats", "/health/database"]

        if request.url.path in maintenance_paths:
            # Простая проверка и оптимизация при необходимости
            try:

                def _check_db_health(session):
                    # Проверяем размер WAL файла
                    result = session.execute(
                        text("PRAGMA wal_checkpoint(PASSIVE)")
                    ).fetchall()
                    return result

                # Выполняем легкую оптимизацию
                DatabaseManager.safe_execute(_check_db_health, max_retries=1)
            except Exception as e:
                logger.debug(f"Не удалось выполнить обслуживание БД: {e}")

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Логируем запрос
        logger.debug(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)

        # Логируем время выполнения
        process_time = time.time() - start_time
        if process_time > 1.0:  # Логируем медленные запросы
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.2f}s"
            )

        return response
