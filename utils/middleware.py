"""
Middleware для FastAPI приложения
"""

import time
import uuid
from typing import Callable
from datetime import datetime

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from utils.rate_limiter import get_rate_limiter
from utils.logger import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического применения rate limiting
    """

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.rate_limiter = get_rate_limiter()

        # Mapping путей к правилам rate limiting
        self.path_rules = {
            # Аутентификация - самые строгие ограничения
            "/auth/login": "auth:login",
            "/auth/register": "auth:login",  # Тоже строго
            # Admin endpoints - средние ограничения
            "/admin": "api:admin",
            "/admins": "api:admin",
            # Файловые операции
            "/newsletters/send": "api:newsletter",
            "/upload": "api:upload",
            # Health checks - мягкие ограничения
            "/health": "health",
            "/": "health",  # Root endpoint
        }

    def _get_rule_key(self, path: str, method: str) -> str:
        """Определение ключа правила rate limiting на основе пути и метода"""

        # Exact path matches
        if path in self.path_rules:
            return self.path_rules[path]

        # Pattern matching для API endpoints
        if path.startswith("/admin") or path.startswith("/admins"):
            return "api:admin"
        elif path.startswith("/auth"):
            return "auth:login"
        elif path.startswith("/newsletters") and method == "POST":
            return "api:newsletter"
        elif path.startswith("/health") or path == "/":
            return "health"
        elif "upload" in path:
            return "api:upload"
        elif ("photo" in path and method == "POST") or ("photo" in path and "upload" in path):
            # Только POST запросы для загрузки фото или пути с upload используют upload лимит
            return "api:upload"
        elif ("photo" in path and ("base64" in path or method == "GET")) or "avatar" in path:
            # GET запросы для просмотра фото (base64) используют более мягкий лимит
            return "api:general"

        # Default rule for all API endpoints
        return "api:general"

    def _should_skip_rate_limit(self, path: str) -> bool:
        """Проверка, нужно ли пропустить rate limiting для данного пути"""
        skip_patterns = [
            "/static",
            "/assets",
            "/favicon.ico",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        return any(path.startswith(pattern) for pattern in skip_patterns)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or self._should_skip_rate_limit(request.url.path):
            return await call_next(request)

        # Определяем правило rate limiting
        rule_key = self._get_rule_key(request.url.path, request.method)

        try:
            # Проверяем rate limit
            rate_info = await self.rate_limiter.check_limit(request, rule_key)

            # Выполняем запрос
            response = await call_next(request)

            # Добавляем заголовки rate limiting к успешному ответу
            response.headers["X-RateLimit-Limit"] = str(
                self.rate_limiter.rules[rule_key].requests
            )
            response.headers["X-RateLimit-Remaining"] = str(
                rate_info.requests_remaining
            )
            response.headers["X-RateLimit-Reset"] = str(int(rate_info.reset_time))

            return response

        except Exception as e:
            # Rate limit exceeded или другая ошибка
            if hasattr(e, "status_code") and e.status_code == 429:
                # Это HTTPException от rate limiter
                raise
            else:
                # Другая ошибка - логируем и продолжаем
                logger.error(f"Rate limit middleware error: {e}")
                return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования запросов и ответов
    """

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    def _get_client_ip(self, request: Request) -> str:
        """Получение IP адреса клиента"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _should_skip_logging(self, path: str) -> bool:
        """Проверка, нужно ли пропустить логирование для данного пути"""
        skip_patterns = [
            "/static",
            "/assets",
            "/favicon.ico",
            "/health",  # Health checks очень частые
        ]

        return any(path.startswith(pattern) for pattern in skip_patterns)

    def _is_debug_enabled(self) -> bool:
        """Проверка, включен ли DEBUG уровень логирования"""
        try:
            # Пытаемся получить доступ к уровню логирования
            if hasattr(logger, "level"):
                return logger.level <= 10  # DEBUG = 10
            elif hasattr(logger, "logger") and hasattr(logger.logger, "isEnabledFor"):
                return logger.logger.isEnabledFor(10)
            else:
                return False
        except:
            return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or self._should_skip_logging(request.url.path):
            return await call_next(request)

        # Генерируем уникальный ID для запроса
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Время начала
        start_time = time.time()

        # Информация о запросе
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:100]  # Обрезаем для логов

        # Логируем входящий запрос
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
                "client_ip": client_ip,
                "user_agent": user_agent,
                "headers": dict(request.headers) if self._is_debug_enabled() else None,
            },
        )

        try:
            # Выполняем запрос
            response = await call_next(request)

            # Время выполнения
            duration = time.time() - start_time

            # Логируем ответ
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": client_ip,
                },
            )

            # Добавляем заголовок с request ID для отладки
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Время выполнения до ошибки
            duration = time.time() - start_time

            # Логируем ошибку
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": client_ip,
                },
                exc_info=True,
            )

            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware для добавления security headers
    """

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if self.enabled:
            # Добавляем security headers
            for header, value in self.security_headers.items():
                response.headers[header] = value

            # Content Security Policy для API
            if request.url.path.startswith("/api") or request.url.path.startswith(
                "/admin"
            ):
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'"
                )

        return response


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware для мониторинга производительности
    """

    def __init__(self, app: ASGIApp, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.slow_request_threshold = 1.0  # секунды

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)

        start_time = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Логируем медленные запросы
            if duration > self.slow_request_threshold:
                logger.warning(
                    f"Slow request detected",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration * 1000, 2),
                        "status_code": response.status_code,
                        "client_ip": (
                            request.client.host if request.client else "unknown"
                        ),
                    },
                )

            # Добавляем заголовок с временем выполнения
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Request error",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise
