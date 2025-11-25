"""
Модуль для реализации rate limiting с поддержкой Redis и in-memory storage
"""
import time
import json
import hashlib
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from threading import Lock
from datetime import datetime, timedelta

from fastapi import Request, HTTPException
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class RateLimitRule:
    """Правило rate limiting"""
    requests: int          # Количество запросов
    window: int           # Временное окно в секундах
    message: str = "Too many requests"
    status_code: int = 429

@dataclass
class RateLimitInfo:
    """Информация о rate limiting для клиента"""
    requests_made: int
    requests_remaining: int
    reset_time: float
    retry_after: Optional[int] = None

class InMemoryStore:
    """In-memory хранилище для rate limiting с TTL"""
    
    def __init__(self):
        self._store: Dict[str, deque] = defaultdict(deque)
        self._lock = Lock()
        self._last_cleanup = time.time()
    
    def _cleanup_expired(self, current_time: float):
        """Очистка истекших записей"""
        if current_time - self._last_cleanup < 60:  # Очистка раз в минуту
            return
            
        with self._lock:
            keys_to_remove = []
            for key, timestamps in self._store.items():
                # Удаляем старые временные метки
                while timestamps and timestamps[0] < current_time - 3600:  # Старше часа
                    timestamps.popleft()
                
                # Если очередь пуста, помечаем ключ для удаления
                if not timestamps:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._store[key]
            
            self._last_cleanup = current_time
    
    def add_request(self, key: str, timestamp: float):
        """Добавить запрос"""
        with self._lock:
            self._store[key].append(timestamp)
    
    def get_requests_in_window(self, key: str, window_start: float) -> int:
        """Получить количество запросов в временном окне"""
        with self._lock:
            if key not in self._store:
                return 0
            
            timestamps = self._store[key]
            # Удаляем старые запросы
            while timestamps and timestamps[0] < window_start:
                timestamps.popleft()
            
            return len(timestamps)
    
    def get_oldest_request(self, key: str) -> Optional[float]:
        """Получить время старейшего запроса"""
        with self._lock:
            if key not in self._store or not self._store[key]:
                return None
            return self._store[key][0]

class RateLimiter:
    """Основной класс rate limiter с поддержкой различных стратегий"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.memory_store = InMemoryStore()
        self.rules: Dict[str, RateLimitRule] = {}
        
        # Предустановленные правила
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Настройка правил по умолчанию"""
        self.rules = {
            # Аутентификация - строгие лимиты для защиты от brute force
            "auth:login": RateLimitRule(
                requests=5,
                window=300,  # 5 минут
                message="Слишком много попыток входа. Попробуйте через 5 минут.",
                status_code=429
            ),
            
            # API endpoints - средние ограничения
            "api:general": RateLimitRule(
                requests=100,
                window=60,  # 1 минута
                message="Превышен лимит запросов к API. Попробуйте позже.",
            ),
            
            # Критические операции
            "api:admin": RateLimitRule(
                requests=50,
                window=60,
                message="Превышен лимит административных операций.",
            ),
            
            # Рассылки и файлы
            "api:upload": RateLimitRule(
                requests=10,
                window=60,
                message="Превышен лимит загрузки файлов.",
            ),
            
            # Newsletter sending
            "api:newsletter": RateLimitRule(
                requests=5,
                window=300,  # 5 минут
                message="Превышен лимит отправки рассылок.",
            ),
            
            # Health checks - более мягкие ограничения
            "health": RateLimitRule(
                requests=300,
                window=60,
                message="Превышен лимит health check запросов.",
            ),
        }
    
    def add_rule(self, key: str, rule: RateLimitRule):
        """Добавить кастомное правило"""
        self.rules[key] = rule
        logger.info(f"Added rate limit rule: {key} -> {rule.requests}/{rule.window}s")
    
    def _get_client_key(self, request: Request, rule_key: str) -> str:
        """Генерация ключа клиента для rate limiting"""
        # Используем IP + User-Agent для более точной идентификации
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        
        # Для аутентифицированных пользователей можем использовать user_id
        user_info = getattr(request.state, "user", None)
        if user_info:
            identifier = f"user_{user_info.get('id', 'unknown')}"
        else:
            # Хеширование для сокрытия sensitive данных
            identifier = hashlib.md5(f"{client_ip}:{user_agent}".encode()).hexdigest()[:12]
        
        return f"{rule_key}:{identifier}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Получение IP адреса клиента с учетом прокси"""
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        return request.client.host if request.client else "unknown"
    
    async def _redis_check_limit(self, key: str, rule: RateLimitRule) -> Tuple[bool, RateLimitInfo]:
        """Проверка лимита через Redis (если доступен)"""
        current_time = time.time()
        window_start = current_time - rule.window
        
        try:
            # Lua скрипт для атомарной операции
            lua_script = """
            local key = KEYS[1]
            local window_start = tonumber(ARGV[1])
            local current_time = tonumber(ARGV[2])
            local max_requests = tonumber(ARGV[3])
            
            -- Удаляем старые записи
            redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
            
            -- Получаем текущее количество
            local current_count = redis.call('ZCARD', key)
            
            -- Проверяем лимит
            if current_count >= max_requests then
                local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
                local reset_time = oldest[2] and (oldest[2] + window) or current_time
                return {current_count, max_requests - current_count, reset_time, 1}
            end
            
            -- Добавляем новую запись
            redis.call('ZADD', key, current_time, current_time)
            redis.call('EXPIRE', key, window + 10)
            
            return {current_count + 1, max_requests - current_count - 1, current_time + window, 0}
            """
            
            result = await self.redis_client.eval(
                lua_script, 1, key, 
                window_start, current_time, rule.requests, rule.window
            )
            
            rate_limited = bool(result[3])
            info = RateLimitInfo(
                requests_made=result[0],
                requests_remaining=max(0, result[1]),
                reset_time=result[2],
                retry_after=int(result[2] - current_time) if rate_limited else None
            )
            
            return rate_limited, info
            
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}, falling back to memory")
            return await self._memory_check_limit(key, rule)
    
    async def _memory_check_limit(self, key: str, rule: RateLimitRule) -> Tuple[bool, RateLimitInfo]:
        """Проверка лимита через память"""
        current_time = time.time()
        window_start = current_time - rule.window
        
        # Очистка старых записей
        self.memory_store._cleanup_expired(current_time)
        
        # Получаем количество запросов в окне
        requests_in_window = self.memory_store.get_requests_in_window(key, window_start)
        
        if requests_in_window >= rule.requests:
            # Получаем время старейшего запроса для расчета reset_time
            oldest_request = self.memory_store.get_oldest_request(key)
            reset_time = (oldest_request + rule.window) if oldest_request else (current_time + rule.window)
            
            info = RateLimitInfo(
                requests_made=requests_in_window,
                requests_remaining=0,
                reset_time=reset_time,
                retry_after=int(reset_time - current_time)
            )
            return True, info
        
        # Добавляем новый запрос
        self.memory_store.add_request(key, current_time)
        
        info = RateLimitInfo(
            requests_made=requests_in_window + 1,
            requests_remaining=rule.requests - requests_in_window - 1,
            reset_time=current_time + rule.window
        )
        return False, info
    
    async def check_limit(self, request: Request, rule_key: str = "api:general") -> RateLimitInfo:
        """
        Основная функция проверки rate limit
        
        Args:
            request: FastAPI request объект
            rule_key: Ключ правила rate limiting
            
        Returns:
            RateLimitInfo: Информация о rate limiting
            
        Raises:
            HTTPException: Если лимит превышен
        """
        rule = self.rules.get(rule_key)
        if not rule:
            logger.warning(f"Rate limit rule not found: {rule_key}")
            rule = self.rules["api:general"]  # Fallback
        
        client_key = self._get_client_key(request, rule_key)
        
        # Выбираем storage backend
        if self.redis_client:
            rate_limited, info = await self._redis_check_limit(client_key, rule)
        else:
            rate_limited, info = await self._memory_check_limit(client_key, rule)
        
        if rate_limited:
            # Логируем превышение лимита
            client_ip = self._get_client_ip(request)
            logger.warning(
                f"Rate limit exceeded: {rule_key} for {client_ip}, "
                f"requests: {info.requests_made}/{rule.requests}, "
                f"retry_after: {info.retry_after}s"
            )
            
            # Добавляем заголовки rate limiting
            headers = {
                "X-RateLimit-Limit": str(rule.requests),
                "X-RateLimit-Remaining": str(info.requests_remaining),
                "X-RateLimit-Reset": str(int(info.reset_time)),
            }
            
            if info.retry_after:
                headers["Retry-After"] = str(info.retry_after)
            
            raise HTTPException(
                status_code=rule.status_code,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": rule.message,
                    "retry_after": info.retry_after,
                    "limit": rule.requests,
                    "window": rule.window,
                },
                headers=headers
            )
        
        return info
    
    def get_stats(self) -> Dict:
        """Получить статистику rate limiting"""
        return {
            "rules_count": len(self.rules),
            "rules": {key: asdict(rule) for key, rule in self.rules.items()},
            "backend": "redis" if self.redis_client else "memory",
            "memory_keys": len(self.memory_store._store) if hasattr(self.memory_store, '_store') else 0,
        }

# Глобальный экземпляр rate limiter
_rate_limiter = None

def get_rate_limiter() -> RateLimiter:
    """Получить глобальный экземпляр rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        # TODO: Добавить Redis клиент когда будет настроен
        _rate_limiter = RateLimiter()
        logger.info("Rate limiter initialized with memory backend")
    return _rate_limiter

def init_rate_limiter(redis_client=None):
    """Инициализация rate limiter с Redis клиентом"""
    global _rate_limiter
    _rate_limiter = RateLimiter(redis_client)
    backend = "redis" if redis_client else "memory"
    logger.info(f"Rate limiter initialized with {backend} backend")
    return _rate_limiter