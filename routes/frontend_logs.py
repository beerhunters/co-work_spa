"""
API endpoint для получения логов от frontend
"""
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from utils.logger import get_logger
from utils.error_notifier import notify_error

logger = get_logger(__name__)
router = APIRouter(prefix="", tags=["frontend-logs"])

class FrontendLogEntry(BaseModel):
    """Схема для получения логов от frontend"""
    timestamp: str
    level: str = Field(..., description="Log level (DEBUG, INFO, WARN, ERROR)")
    context: str = Field(..., description="Frontend component/module name")
    message: str = Field(..., description="Log message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional log data")
    user_agent: Optional[str] = Field(None, description="Browser user agent")
    url: Optional[str] = Field(None, description="Current page URL")
    stack: Optional[str] = Field(None, description="Stack trace for errors")
    environment: Optional[str] = Field(None, description="Frontend environment")

@router.post("/frontend-logs")
async def receive_frontend_logs(
    log_entry: FrontendLogEntry,
    request: Request
):
    """
    Endpoint для получения логов от frontend приложения
    """
    try:
        # Получаем IP адрес клиента
        client_ip = request.client.host
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # Определяем уровень логирования на backend
        level_mapping = {
            "DEBUG": logger.debug,
            "INFO": logger.info,
            "WARN": logger.warning,
            "ERROR": logger.error
        }
        
        log_func = level_mapping.get(log_entry.level.upper(), logger.info)
        
        # Формируем сообщение
        message = f"Frontend [{log_entry.context}]: {log_entry.message}"
        
        # Дополнительные данные для логирования
        extra_data = {
            "frontend_log": True,
            "client_ip": client_ip,
            "user_agent": log_entry.user_agent,
            "url": log_entry.url,
            "environment": log_entry.environment,
            "frontend_timestamp": log_entry.timestamp,
            "context": log_entry.context
        }
        
        # Добавляем данные из frontend если есть
        if log_entry.data:
            extra_data["frontend_data"] = log_entry.data
        
        # Добавляем stack trace для ошибок
        if log_entry.stack and log_entry.level.upper() == "ERROR":
            extra_data["frontend_stack"] = log_entry.stack
        
        # Логируем на backend ОДИН раз, объединяя все данные
        if log_entry.level.upper() == "ERROR":
            # Для ошибок добавляем дополнительную информацию
            extra_data.update({
                "event_type": "frontend_error",
                "error_data": log_entry.data,
                "frontend_stack": log_entry.stack if log_entry.stack else None
            })
        
        # Для ERROR уровня отправляем через централизованную систему
        if log_entry.level.upper() == "ERROR":
            # Отправляем ОДНО уведомление через централизованную систему
            notify_error(
                exc_info=None,
                message=f"Frontend [{log_entry.context}]: {log_entry.message}",
                context={
                    "source": "frontend",
                    "client_ip": client_ip,
                    "user_agent": log_entry.user_agent,
                    "url": log_entry.url,
                    "component": log_entry.context,
                    "frontend_data": log_entry.data,
                    "frontend_stack": log_entry.stack
                }
            )
        
        # Логируем локально БЕЗ отправки в Telegram для всех уровней
        log_func(message, extra={**extra_data, "telegram_skip": True})
        
        return {"status": "logged", "level": log_entry.level}
        
    except Exception as e:
        logger.error(f"Error processing frontend log: {e}", exc_info=True)
        # Не возвращаем ошибку клиенту, чтобы не нарушать работу frontend
        return {"status": "error", "message": "Failed to process log"}

@router.get("/frontend-logs/status")
async def frontend_logs_status():
    """
    Статус endpoint для проверки доступности логирования
    """
    return {
        "status": "available",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Frontend logging endpoint is available"
    }