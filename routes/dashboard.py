# ================== routes/dashboard.py ==================
from fastapi import APIRouter, Depends
from sqlalchemy import text
from fastapi import HTTPException
from models.models import DatabaseManager
from dependencies import verify_token
from utils.logger import get_logger

logger = get_logger(__name__)
# router = APIRouter(prefix="/dashboard", tags=["dashboard"])
router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats")
async def get_dashboard_stats(_: str = Depends(verify_token)):
    """Получение статистики для дашборда."""

    def _get_stats(session):
        total_users = session.execute(text("SELECT COUNT(*) FROM users")).scalar()
        total_bookings = session.execute(text("SELECT COUNT(*) FROM bookings")).scalar()
        open_tickets = session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE status != 'CLOSED'")
        ).scalar()
        active_tariffs = session.execute(
            text("SELECT COUNT(*) FROM tariffs WHERE is_active = 1")
        ).scalar()

        return {
            "total_users": total_users,
            "total_bookings": total_bookings,
            "open_tickets": open_tickets,
            "active_tariffs": active_tariffs,
        }

    try:
        return DatabaseManager.safe_execute(_get_stats)
    except Exception as e:
        logger.error(f"Ошибка в get_dashboard_stats: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")
