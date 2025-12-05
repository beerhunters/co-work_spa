# routes/tariffs.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from models.models import Tariff
from dependencies import get_db, verify_token
from schemas.tariff_schemas import TariffBase, TariffCreate, TariffUpdate
from utils.logger import get_logger
from utils.cache_manager import cache_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/tariffs", tags=["tariffs"])


@router.get("/active")
async def get_active_tariffs(db: Session = Depends(get_db)):
    """Получение активных тарифов. Используется ботом."""
    cache_key = cache_manager.get_cache_key("tariffs", "active")
    
    async def fetch_tariffs():
        try:
            tariffs = db.query(Tariff).filter_by(is_active=True).all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "price": t.price,
                    "purpose": t.purpose,
                    "service_id": t.service_id if t.service_id is not None else 0,
                    "is_active": t.is_active,
                    "color": t.color if hasattr(t, 'color') and t.color else "#3182CE",
                }
                for t in tariffs
            ]
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении активных тарифов: {e}")
            raise HTTPException(status_code=500, detail="Ошибка базы данных")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении активных тарифов: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
    
    return await cache_manager.get_or_set(cache_key, fetch_tariffs, ttl=600)


@router.get("", response_model=List[TariffBase])
async def get_tariffs(db: Session = Depends(get_db), _: str = Depends(verify_token)):
    """Получение всех тарифов."""
    try:
        tariffs = db.query(Tariff).order_by(Tariff.id.desc()).all()
        # Преобразуем в словарь для корректной сериализации
        result = []
        for t in tariffs:
            result.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "price": t.price,
                    "purpose": t.purpose,
                    "service_id": t.service_id if t.service_id is not None else 0,
                    "is_active": t.is_active,
                    "color": t.color if hasattr(t, 'color') and t.color else "#3182CE",
                }
            )
        return result
    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при получении тарифов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении тарифов: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{tariff_id}")
async def get_tariff(tariff_id: int, db: Session = Depends(get_db)):
    """Получение тарифа по ID."""
    try:
        if tariff_id <= 0:
            raise HTTPException(
                status_code=400, detail="ID тарифа должен быть положительным числом"
            )

        tariff = db.query(Tariff).get(tariff_id)
        if not tariff:
            raise HTTPException(status_code=404, detail="Тариф не найден")

        return {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price": tariff.price,
            "purpose": tariff.purpose,
            "service_id": tariff.service_id if tariff.service_id is not None else 0,
            "is_active": tariff.is_active,
            "color": tariff.color if hasattr(tariff, 'color') and tariff.color else "#3182CE",
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при получении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("", response_model=TariffBase)
async def create_tariff(
    tariff_data: TariffCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Создание нового тарифа."""
    try:
        # Валидация
        if not tariff_data.name or len(tariff_data.name.strip()) < 3:
            raise HTTPException(
                status_code=400,
                detail="Название тарифа должно содержать минимум 3 символа",
            )

        if len(tariff_data.name) > 64:
            raise HTTPException(
                status_code=400, detail="Название тарифа не должно превышать 64 символа"
            )

        if not tariff_data.description or len(tariff_data.description.strip()) < 1:
            raise HTTPException(status_code=400, detail="Описание тарифа обязательно")

        if tariff_data.price < 0:
            raise HTTPException(
                status_code=400, detail="Цена не может быть отрицательной"
            )

        # Убеждаемся, что service_id не None, иначе устанавливаем 0
        service_id = tariff_data.service_id if tariff_data.service_id is not None else 0

        tariff = Tariff(
            name=tariff_data.name.strip(),
            description=tariff_data.description.strip(),
            price=tariff_data.price,
            purpose=tariff_data.purpose,
            service_id=service_id,
            is_active=tariff_data.is_active,
            color=tariff_data.color if hasattr(tariff_data, 'color') and tariff_data.color else "#3182CE",
        )

        db.add(tariff)
        db.commit()
        db.refresh(tariff)

        logger.info(f"Создан тариф: {tariff.name} ({tariff.price}₽)")

        # Возвращаем в правильном формате
        return {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price": tariff.price,
            "purpose": tariff.purpose,
            "service_id": tariff.service_id if tariff.service_id is not None else 0,
            "is_active": tariff.is_active,
            "color": tariff.color if hasattr(tariff, 'color') and tariff.color else "#3182CE",
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при создании тарифа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать тариф")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при создании тарифа: {e}")
        raise HTTPException(status_code=500, detail="Не удалось создать тариф")


@router.put("/{tariff_id}", response_model=TariffBase)
async def update_tariff(
    tariff_id: int,
    tariff_data: TariffUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление тарифа."""
    try:
        if tariff_id <= 0:
            raise HTTPException(
                status_code=400, detail="ID тарифа должен быть положительным числом"
            )

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
                raise HTTPException(
                    status_code=400, detail="Описание тарифа обязательно"
                )
            update_data["description"] = update_data["description"].strip()

        if "price" in update_data and update_data["price"] < 0:
            raise HTTPException(
                status_code=400, detail="Цена не может быть отрицательной"
            )

        # Обработка service_id
        if "service_id" in update_data and update_data["service_id"] is None:
            update_data["service_id"] = 0

        for field, value in update_data.items():
            setattr(tariff, field, value)

        db.commit()
        db.refresh(tariff)

        logger.info(f"Обновлен тариф: {tariff.name}")

        # Возвращаем в правильном формате
        return {
            "id": tariff.id,
            "name": tariff.name,
            "description": tariff.description,
            "price": tariff.price,
            "purpose": tariff.purpose,
            "service_id": tariff.service_id if tariff.service_id is not None else 0,
            "is_active": tariff.is_active,
            "color": tariff.color if hasattr(tariff, 'color') and tariff.color else "#3182CE",
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при обновлении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить тариф")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при обновлении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось обновить тариф")


@router.delete("/{tariff_id}")
async def delete_tariff(
    tariff_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление тарифа."""
    try:
        if tariff_id <= 0:
            raise HTTPException(
                status_code=400, detail="ID тарифа должен быть положительным числом"
            )

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

        tariff_name = tariff.name
        db.delete(tariff)
        db.commit()

        logger.info(f"Удален тариф: {tariff_name}")
        return {"message": f"Тариф '{tariff_name}' удален"}

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при удалении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить тариф")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при удалении тарифа {tariff_id}: {e}")
        raise HTTPException(status_code=500, detail="Не удалось удалить тариф")
