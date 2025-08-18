# routes/tariffs.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models.models import Tariff
from dependencies import get_db, verify_token
from schemas.tariff_schemas import TariffBase, TariffCreate, TariffUpdate
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("/active")
async def get_active_tariffs(db: Session = Depends(get_db)):
    """Получение активных тарифов. Используется ботом."""
    tariffs = db.query(Tariff).filter_by(is_active=True).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "price": t.price,
            "purpose": t.purpose,
            "service_id": t.service_id,
            "is_active": t.is_active,
        }
        for t in tariffs
    ]


@router.get("", response_model=List[TariffBase])
async def get_tariffs(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение всех тарифов."""
    tariffs = db.query(Tariff).order_by(Tariff.id.desc()).all()
    return tariffs


@router.get("/{tariff_id}")
async def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    """Получение тарифа по ID."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    return {
        "id": tariff.id,
        "name": tariff.name,
        "description": tariff.description,
        "price": tariff.price,
        "purpose": tariff.purpose,
        "service_id": tariff.service_id,
        "is_active": tariff.is_active,
    }


@router.post("", response_model=TariffBase)
async def create_tariff(
    tariff_data: TariffCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создание нового тарифа."""
    # Валидация
    if not tariff_data.name or len(tariff_data.name.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Название тарифа должно содержать минимум 3 символа"
        )

    if len(tariff_data.name) > 64:
        raise HTTPException(
            status_code=400, detail="Название тарифа не должно превышать 64 символа"
        )

    if not tariff_data.description or len(tariff_data.description.strip()) < 1:
        raise HTTPException(status_code=400, detail="Описание тарифа обязательно")

    if tariff_data.price < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")

    try:
        tariff = Tariff(
            name=tariff_data.name.strip(),
            description=tariff_data.description.strip(),
            price=tariff_data.price,
            purpose=tariff_data.purpose,
            service_id=tariff_data.service_id,
            is_active=tariff_data.is_active,
        )

        db.add(tariff)
        db.commit()
        db.refresh(tariff)

        logger.info(f"Создан тариф: {tariff.name} ({tariff.price}₽)")
        return tariff

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания тарифа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать тариф")


@router.put("/{tariff_id}", response_model=TariffBase)
async def update_tariff(
    tariff_id: int,
    tariff_data: TariffUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление тарифа."""
    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    update_data = tariff_data.dict(exclude_unset=True)

    # Валидация
    if "name" in update_data:
        if not update_data["name"] or len(update_data["name"].strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Название тарифа должно содержать минимум 3 символа",
            )
        update_data["name"] = update_data["name"].strip()

    if "description" in update_data:
        if (
            not update_data["description"]
            or len(update_data["description"].strip()) < 1
        ):
            raise HTTPException(status_code=400, detail="Описание тарифа обязательно")
        update_data["description"] = update_data["description"].strip()

    if "price" in update_data and update_data["price"] < 0:
        raise HTTPException(status_code=400, detail="Цена не может быть отрицательной")

    try:
        for field, value in update_data.items():
            setattr(tariff, field, value)

        db.commit()
        db.refresh(tariff)

        logger.info(f"Обновлен тариф: {tariff.name}")
        return tariff

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить тариф")


@router.delete("/{tariff_id}")
async def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тарифа."""
    from models.models import Booking

    tariff = db.query(Tariff).get(tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не найден")

    # Проверяем, используется ли тариф в активных бронированиях
    active_bookings = db.query(Booking).filter_by(tariff_id=tariff_id).count()
    if active_bookings > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить тариф. Он используется в {active_bookings} бронированиях.",
        )

    try:
        tariff_name = tariff.name
        db.delete(tariff)
        db.commit()

        logger.info(f"Удален тариф: {tariff_name}")
        return {"message": f"Тариф '{tariff_name}' удален"}

    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить тариф")
