"""
API endpoints для управления банами IP адресов
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, IPvAnyAddress

from dependencies import verify_token_with_permissions, CachedAdmin
from models.models import Permission
from utils.ip_ban_manager import get_ip_ban_manager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/ip-bans", tags=["ip-bans"])


# Pydantic схемы
class BanIPRequest(BaseModel):
    """Запрос на бан IP"""
    ip: str = Field(..., description="IP адрес для бана")
    reason: str = Field(default="Manual ban", description="Причина бана")
    duration: int = Field(default=86400, ge=60, le=2592000, description="Длительность бана в секундах (1 мин - 30 дней)")


class UnbanIPRequest(BaseModel):
    """Запрос на разбан IP"""
    ip: str = Field(..., description="IP адрес для разбана")


class IPBanInfo(BaseModel):
    """Информация о забаненном IP"""
    ip: str
    reason: str
    banned_at: str
    duration: int
    manual: bool
    admin: Optional[str] = None
    unbanned_at: Optional[str] = None
    seconds_remaining: Optional[int] = None


class IPBanStats(BaseModel):
    """Статистика системы банов"""
    redis_available: bool
    total_banned: int
    total_tracked: int
    ban_duration: Optional[int] = None
    tracking_window: Optional[int] = None
    max_suspicious_requests: Optional[int] = None
    error: Optional[str] = None


@router.get("/", response_model=List[IPBanInfo])
async def get_banned_ips(
    limit: int = 100,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Получает список всех забаненных IP адресов

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()
        banned_ips = await ban_manager.get_banned_ips(limit=limit)

        logger.info(f"Админ {current_admin.login} запросил список забаненных IP (найдено: {len(banned_ips)})")

        return banned_ips
    except Exception as e:
        logger.error(f"Ошибка получения списка забаненных IP: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve banned IPs")


@router.get("/{ip}/status", response_model=Optional[IPBanInfo])
async def get_ip_ban_status(
    ip: str,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Проверяет статус IP адреса

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()

        # Проверяем забанен ли IP
        is_banned = await ban_manager.is_banned(ip)

        if not is_banned:
            return None

        # Получаем информацию о бане
        ban_info = await ban_manager.get_ban_info(ip)

        logger.info(f"Админ {current_admin.login} проверил статус IP {ip}: {'забанен' if is_banned else 'не забанен'}")

        return ban_info
    except Exception as e:
        logger.error(f"Ошибка проверки статуса IP {ip}: {e}")
        raise HTTPException(status_code=500, detail="Failed to check IP status")


@router.post("/{ip}/ban")
async def ban_ip(
    ip: str,
    request: Optional[BanIPRequest] = None,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Забанить IP адрес вручную

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()

        # Используем данные из request или значения по умолчанию
        reason = request.reason if request else "Manual ban"
        duration = request.duration if request else 86400

        # Проверяем, не забанен ли уже
        if await ban_manager.is_banned(ip):
            raise HTTPException(status_code=400, detail=f"IP {ip} is already banned")

        # Баним IP
        success = await ban_manager.ban_ip(
            ip=ip,
            reason=reason,
            duration=duration,
            manual=True,
            admin=current_admin.login
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to ban IP")

        logger.info(f"Админ {current_admin.login} забанил IP {ip} на {duration}s. Причина: {reason}")

        return {
            "success": True,
            "message": f"IP {ip} has been banned for {duration} seconds",
            "ip": ip,
            "duration": duration,
            "reason": reason,
            "admin": current_admin.login
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка бана IP {ip}: {e}")
        raise HTTPException(status_code=500, detail="Failed to ban IP")


@router.post("/{ip}/unban")
async def unban_ip(
    ip: str,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Разбанить IP адрес

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()

        # Проверяем, забанен ли IP
        if not await ban_manager.is_banned(ip):
            raise HTTPException(status_code=404, detail=f"IP {ip} is not banned")

        # Разбаниваем IP
        success = await ban_manager.unban_ip(ip=ip, admin=current_admin.login)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to unban IP")

        logger.info(f"Админ {current_admin.login} разбанил IP {ip}")

        return {
            "success": True,
            "message": f"IP {ip} has been unbanned",
            "ip": ip,
            "admin": current_admin.login
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка разбана IP {ip}: {e}")
        raise HTTPException(status_code=500, detail="Failed to unban IP")


@router.get("/stats", response_model=IPBanStats)
async def get_ban_stats(
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Получает статистику системы банов

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()
        stats = await ban_manager.get_stats()

        logger.info(f"Админ {current_admin.login} запросил статистику банов")

        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики банов: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ban statistics")


@router.delete("/clear-all")
async def clear_all_bans(
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.MANAGE_LOGGING]))
):
    """
    Очищает все баны (только для отладки, использовать осторожно)

    Требуется разрешение: MANAGE_LOGGING
    """
    try:
        ban_manager = get_ip_ban_manager()

        # Получаем все забаненные IP
        banned_ips = await ban_manager.get_banned_ips(limit=1000)

        # Разбаниваем каждый
        unbanned_count = 0
        for ban_info in banned_ips:
            ip = ban_info.get("ip")
            if ip:
                success = await ban_manager.unban_ip(ip=ip, admin=current_admin.login)
                if success:
                    unbanned_count += 1

        logger.warning(f"Админ {current_admin.login} очистил все баны (разбанено: {unbanned_count})")

        return {
            "success": True,
            "message": f"Cleared {unbanned_count} bans",
            "unbanned_count": unbanned_count,
            "admin": current_admin.login
        }
    except Exception as e:
        logger.error(f"Ошибка очистки всех банов: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear bans")
