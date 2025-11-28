# ================== routes/payments.py ==================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dependencies import get_db, verify_token
from utils.external_api import (
    create_yookassa_payment,
    check_yookassa_payment_status,
    cancel_yookassa_payment,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])
# router = APIRouter(tags=["payments"])


@router.post("")
async def create_payment(payment_data: dict, db: Session = Depends(get_db)):
    """Создание платежа через YooKassa. Используется ботом."""
    try:
        from models.models import User, Tariff

        user_id = payment_data.get("user_id")
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден в системе")

        tariff_id = payment_data.get("tariff_id")
        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            raise HTTPException(status_code=404, detail="Тариф не найден в системе")

        result = await create_yookassa_payment(payment_data)
        return result

    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать платеж. Проверьте настройки YooKassa")


@router.get("/{payment_id}/status")
async def check_payment_status_api(payment_id: str, _: str = Depends(verify_token)):
    """Проверка статуса платежа."""
    try:
        result = await check_yookassa_payment_status(payment_id)
        return result
    except Exception as e:
        logger.error(f"Ошибка проверки платежа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось проверить статус платежа. Попробуйте позже")


@router.post("/{payment_id}/cancel")
async def cancel_payment_api(payment_id: str, _: str = Depends(verify_token)):
    """Отмена платежа."""
    try:
        result = await cancel_yookassa_payment(payment_id)
        return result
    except Exception as e:
        logger.error(f"Ошибка отмены платежа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось отменить платеж. Попробуйте позже")
