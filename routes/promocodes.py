# ================== routes/promocodes.py ==================
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import re

from models.models import Promocode
from dependencies import get_db, verify_token
from config import MOSCOW_TZ
from schemas.promocode_schemas import PromocodeBase, PromocodeCreate, PromocodeUpdate
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/promocodes", tags=["promocodes"])
# router = APIRouter(tags=["promocodes"])


@router.get("", response_model=List[PromocodeBase])
async def get_promocodes(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение всех промокодов."""
    promocodes = db.query(Promocode).order_by(Promocode.id.desc()).all()
    return promocodes


@router.get("/{promocode_id}", response_model=PromocodeBase)
async def get_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение промокода по ID."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")
    return promocode


@router.get("/by_name/{name}")
async def get_promocode_by_name(name: str, db: Session = Depends(get_db)):
    """Получение промокода по названию. Используется ботом."""
    promocode = db.query(Promocode).filter_by(name=name, is_active=True).first()
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    # Проверяем срок действия
    if promocode.expiration_date and promocode.expiration_date < datetime.now(
        MOSCOW_TZ
    ):
        raise HTTPException(status_code=410, detail="Promocode expired")

    # Проверяем количество использований
    if promocode.usage_quantity <= 0:
        raise HTTPException(status_code=410, detail="Promocode usage limit exceeded")

    return {
        "id": promocode.id,
        "name": promocode.name,
        "discount": promocode.discount,
        "usage_quantity": promocode.usage_quantity,
        "expiration_date": promocode.expiration_date,
        "is_active": promocode.is_active,
    }


@router.post("", response_model=PromocodeBase)
async def create_promocode(
    promocode_data: PromocodeCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создание нового промокода."""
    # Валидация
    if not promocode_data.name or len(promocode_data.name.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Название промокода должно содержать минимум 3 символа",
        )

    if not re.match(r"^[A-Za-z0-9_-]+$", promocode_data.name):
        raise HTTPException(
            status_code=400,
            detail="Название может содержать только латинские буквы, цифры, дефис и подчеркивание",
        )

    # Проверяем уникальность
    existing = db.query(Promocode).filter_by(name=promocode_data.name.upper()).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Промокод с названием '{promocode_data.name}' уже существует",
        )

    if promocode_data.discount < 1 or promocode_data.discount > 100:
        raise HTTPException(status_code=400, detail="Скидка должна быть от 1% до 100%")

    try:
        promocode = Promocode(
            name=promocode_data.name.upper(),
            discount=promocode_data.discount,
            usage_quantity=promocode_data.usage_quantity,
            expiration_date=promocode_data.expiration_date,
            is_active=promocode_data.is_active,
        )

        db.add(promocode)
        db.commit()
        db.refresh(promocode)

        logger.info(f"Создан промокод: {promocode.name} ({promocode.discount}%)")
        return promocode

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания промокода: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать промокод")


@router.put("/{promocode_id}", response_model=PromocodeBase)
async def update_promocode(
    promocode_id: int,
    promocode_data: PromocodeUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление промокода."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    # Валидация названия если оно изменяется
    if promocode_data.name and promocode_data.name != promocode.name:
        if len(promocode_data.name.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Название промокода должно содержать минимум 3 символа",
            )

        if not re.match(r"^[A-Za-z0-9_-]+$", promocode_data.name):
            raise HTTPException(
                status_code=400,
                detail="Название может содержать только латинские буквы, цифры, дефис и подчеркивание",
            )

        # Проверяем уникальность нового названия
        existing = db.query(Promocode).filter_by(name=promocode_data.name.upper()).first()
        if existing and existing.id != promocode_id:
            raise HTTPException(
                status_code=400,
                detail=f"Промокод с названием '{promocode_data.name}' уже существует",
            )

    # Валидация скидки
    if promocode_data.discount is not None:
        if promocode_data.discount < 1 or promocode_data.discount > 100:
            raise HTTPException(status_code=400, detail="Скидка должна быть от 1% до 100%")

    try:
        # Обновляем только переданные поля
        if promocode_data.name:
            promocode.name = promocode_data.name.upper()
        if promocode_data.discount is not None:
            promocode.discount = promocode_data.discount
        if promocode_data.usage_quantity is not None:
            promocode.usage_quantity = promocode_data.usage_quantity
        if promocode_data.expiration_date is not None:
            promocode.expiration_date = promocode_data.expiration_date
        if promocode_data.is_active is not None:
            promocode.is_active = promocode_data.is_active

        db.commit()
        db.refresh(promocode)

        logger.info(f"Обновлен промокод: {promocode.name} ({promocode.discount}%)")
        return promocode

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить промокод")


@router.post("/{promocode_id}/use")
async def use_promocode(promocode_id: int, db: Session = Depends(get_db)):
    """Использование промокода (уменьшение счетчика)."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    if not promocode.is_active:
        raise HTTPException(status_code=400, detail="Promocode is not active")

    if promocode.expiration_date and promocode.expiration_date < datetime.now(
        MOSCOW_TZ
    ):
        raise HTTPException(status_code=410, detail="Promocode expired")

    if promocode.usage_quantity <= 0:
        raise HTTPException(status_code=410, detail="Promocode usage limit exceeded")

    try:
        promocode.usage_quantity -= 1
        db.commit()

        logger.info(
            f"Использован промокод {promocode.name}. Осталось использований: {promocode.usage_quantity}"
        )

        return {
            "message": "Promocode used successfully",
            "remaining_uses": promocode.usage_quantity,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка использования промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to use promocode")


@router.delete("/{promocode_id}")
async def delete_promocode(
    promocode_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление промокода."""
    promocode = db.query(Promocode).get(promocode_id)
    if not promocode:
        raise HTTPException(status_code=404, detail="Promocode not found")

    # Проверяем, используется ли промокод в активных бронированиях
    from models.models import Booking

    active_bookings = db.query(Booking).filter_by(promocode_id=promocode_id).count()
    if active_bookings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить промокод. Он используется в {active_bookings} бронированиях.",
        )

    try:
        promocode_name = promocode.name
        db.delete(promocode)
        db.commit()

        logger.info(f"Удален промокод: {promocode_name}")
        return {"message": f"Промокод '{promocode_name}' удален"}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления промокода {promocode_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить промокод")
