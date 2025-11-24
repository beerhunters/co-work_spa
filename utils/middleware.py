"""
Middleware для FastAPI приложения
"""

import time
import uuid
from typing import Callable
from datetime import datetime

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from utils.rate_limiter import get_rate_limiter
from utils.logger import get_logger
import config
import logging

logger = get_logger(__name__)


# ===================================
# Sensitive Data Filtering
# ===================================

def sanitize_headers(headers: dict) -> dict:
    """
    Фильтрует sensitive данные из headers для безопасного логирования.

    Args:
        headers: Словарь headers

    Returns:
        Словарь headers с замаскированными sensitive значениями
    """
    sensitive_headers = {
        'authorization',
        'cookie',
        'x-api-key',
        'x-csrf-token',
        'x-auth-token',
        'proxy-authorization',
    }

    sanitized = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in sensitive_headers:
            # Показываем только первые 10 символов
            sanitized[key] = value[:10] + '***' if len(value) > 10 else '***'
        else:
            sanitized[key] = value

    return sanitized


def sanitize_query_params(params: dict) -> dict:
    """
    Фильтрует sensitive данные из query parameters.

    Args:
        params: Словарь query parameters

    Returns:
        Словарь с замаскированными sensitive значениями
    """
    sensitive_params = {
        'password',
        'token',
        'secret',
        'api_key',
        'access_token',
        'refresh_token',
    }

    sanitized = {}
    for key, value in params.items():
        key_lower = key.lower()
        if key_lower in sensitive_params:
            sanitized[key] = '***'
        else:
            sanitized[key] = value

    return sanitized


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

    def _is_internal_request(self, request: Request) -> bool:
        """Проверяет, является ли запрос внутренним (от Docker контейнера)"""
        client_ip = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Docker внутренние IP
        internal_ips = ["172.", "127.0.0.1", "localhost"]
        is_internal_ip = any(client_ip.startswith(ip) for ip in internal_ips)
        
        # Python requests из бота
        is_bot_request = "python" in user_agent or "aiohttp" in user_agent
        
        return is_internal_ip and is_bot_request

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or self._should_skip_rate_limit(request.url.path):
            return await call_next(request)

        # Пропускаем rate limiting для внутренних запросов
        if self._is_internal_request(request):
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

        except HTTPException as e:
            # Rate limit exceeded - правильно возвращаем 429
            if e.status_code == 429:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=429,
                    content=e.detail,
                    headers=getattr(e, 'headers', {})
                )
            else:
                # Другая HTTPException - пробрасываем дальше
                raise
        except Exception as e:
            # Непредвиденная ошибка - логируем и продолжаем
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
        # Базовые паттерны для статических файлов
        static_patterns = [
            "/static",
            "/assets",
            "/favicon.ico",
        ]

        # Проверяем статические файлы
        if any(path.startswith(pattern) for pattern in static_patterns):
            return True

        # Проверяем настраиваемые исключения из config
        for excluded_path in config.EXCLUDE_PATHS_FROM_LOGGING:
            excluded_path = excluded_path.strip()
            if excluded_path and path.startswith(excluded_path):
                return True

        return False

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
        is_debug = self._is_debug_enabled()

        # Получаем уровень логирования из config
        log_level = getattr(logging, config.MIDDLEWARE_LOG_LEVEL, logging.INFO)

        # Минимальные данные для INFO/WARNING логов
        minimal_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "client_ip": client_ip,
        }

        # Дополнительные данные только для DEBUG (с фильтрацией sensitive data)
        if is_debug:
            minimal_data.update({
                "query": sanitize_query_params(dict(request.query_params)) if request.query_params else None,
                "user_agent": request.headers.get("User-Agent", "")[:100],
                "headers": sanitize_headers(dict(request.headers)),
            })

        # Используем соответствующий метод logger в зависимости от уровня
        if log_level == logging.WARNING:
            logger.warning(f"{request.method} {request.url.path}", extra=minimal_data)
        else:  # INFO или DEBUG
            logger.info(f"{request.method} {request.url.path}", extra=minimal_data)

        try:
            # Выполняем запрос
            response = await call_next(request)

            # Время выполнения
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)

            # Отслеживаем метрики производительности
            try:
                from routes import monitoring
                monitoring.track_request(
                    endpoint=request.url.path,
                    status_code=response.status_code,
                    response_time_ms=duration_ms
                )
            except Exception as metric_error:
                # Не прерываем выполнение запроса если метрики не работают
                logger.debug(f"Failed to track request metrics: {metric_error}")

            # Логируем ответ (используем формат похожий на nginx)
            response_data = {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            }

            # Форматируем сообщение в стиле nginx
            log_message = f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)"

            # Используем соответствующий метод logger в зависимости от уровня
            if log_level == logging.WARNING:
                logger.warning(log_message, extra=response_data)
            else:  # INFO или DEBUG
                logger.info(log_message, extra=response_data)

            # Добавляем заголовок с request ID для отладки
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Время выполнения до ошибки
            duration = time.time() - start_time
            duration_ms = round(duration * 1000, 2)

            # Логируем ошибку
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
                exc_info=True,
            )

            # Отслеживаем метрики для failed запросов
            try:
                from routes import monitoring
                monitoring.track_request(
                    endpoint=request.url.path,
                    status_code=500,  # Internal server error
                    response_time_ms=duration_ms
                )
            except Exception as metric_error:
                logger.debug(f"Failed to track error metrics: {metric_error}")

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
        # Получаем порог из config (в миллисекундах), конвертируем в секунды
        self.slow_request_threshold = config.LOG_SLOW_REQUEST_THRESHOLD_MS / 1000.0

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
                    f"Slow request detected: {request.method} {request.url.path} took {round(duration * 1000, 2)}ms",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "query": str(request.query_params) if request.query_params else None,
                        "duration_ms": round(duration * 1000, 2),
                        "threshold_ms": config.LOG_SLOW_REQUEST_THRESHOLD_MS,
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


class IPBanMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки забаненных IP адресов
    Блокирует запросы от забаненных IP с кодом 403
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

        return request.client.host if request.client else ""

    def _should_skip_check(self, path: str) -> bool:
        """
        Проверка, нужно ли пропустить проверку бана для данного пути
        Некоторые пути должны быть доступны всегда (health checks и т.д.)
        """
        skip_patterns = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        return any(path.startswith(pattern) for pattern in skip_patterns)

    async def dispatch(self, request: Request, call_next: Callable):
        """Обработка запроса"""
        if not self.enabled:
            return await call_next(request)

        # Пропускаем проверку для определенных путей
        if self._should_skip_check(request.url.path):
            return await call_next(request)

        try:
            # Получаем IP клиента
            client_ip = self._get_client_ip(request)

            if not client_ip:
                # Если не удалось получить IP, пропускаем запрос
                return await call_next(request)

            # Проверяем забанен ли IP
            from utils.ip_ban_manager import get_ip_ban_manager
            ban_manager = get_ip_ban_manager()

            is_banned = await ban_manager.is_banned(client_ip)

            if is_banned:
                # Получаем информацию о бане для заголовков
                ban_info = await ban_manager.get_ban_info(client_ip)

                # Формируем response с 403 Forbidden
                headers = {
                    "X-Banned": "true",
                    "X-Ban-Reason": ban_info.get("reason", "Suspicious activity") if ban_info else "Suspicious activity",
                }

                # Добавляем время разбана если доступно
                if ban_info and "unbanned_at" in ban_info:
                    headers["X-Banned-Until"] = ban_info["unbanned_at"]

                logger.warning(
                    f"Blocked request from banned IP: {client_ip} "
                    f"(path: {request.url.path}, method: {request.method})"
                )

                return Response(
                    content="Access denied: Your IP address has been banned due to suspicious activity",
                    status_code=403,
                    headers=headers
                )

            # IP не забанен, продолжаем обработку
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Error in IPBanMiddleware: {e}")
            # При ошибке пропускаем запрос (fail-open для доступности)
            return await call_next(request)
