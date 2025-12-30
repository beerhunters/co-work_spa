# routes/offices.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import delete

from models.models import Office, office_tenants, OfficeTenantReminder, OfficePaymentHistory, User, Permission, ReminderType
from dependencies import get_db, verify_token, verify_token_with_permissions, CachedAdmin
from schemas.office_schemas import OfficeBase, OfficeCreate, OfficeUpdate, OfficeTenantBase, TenantReminderSetting, OfficePaymentRecord, OfficePaymentButtonStatus
from utils.logger import get_logger
from utils.cache_manager import cache_manager
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import asyncio
from config import MOSCOW_TZ, ADMIN_TELEGRAM_ID

logger = get_logger(__name__)
router = APIRouter(prefix="/offices", tags=["offices"])


@router.get("/active")
async def get_active_offices(db: Session = Depends(get_db)):
    """Получение активных офисов. С кэшированием."""
    cache_key = cache_manager.get_cache_key("offices", "active")

    async def fetch_offices():
        try:
            offices = db.query(Office).filter_by(is_active=True).all()
            result = []
            for o in offices:
                office_dict = {
                    "id": o.id,
                    "office_number": o.office_number,
                    "floor": o.floor,
                    "capacity": o.capacity,
                    "price_per_month": o.price_per_month,
                    "payment_day": o.payment_day,
                    "admin_reminder_enabled": o.admin_reminder_enabled,
                    "admin_reminder_days": o.admin_reminder_days,
                    "tenant_reminder_enabled": o.tenant_reminder_enabled,
                    "tenant_reminder_days": o.tenant_reminder_days,
                    "comment": o.comment,
                    "is_active": o.is_active,
                    "created_at": o.created_at,
                    "updated_at": o.updated_at,
                    "tenants": [
                        {
                            "id": t.id,
                            "telegram_id": t.telegram_id,
                            "full_name": t.full_name or "Нет имени"
                        }
                        for t in o.tenants
                    ],
                    "tenant_reminder_settings": []
                }
                result.append(office_dict)
            return result
        except SQLAlchemyError as e:
            logger.error(f"Ошибка базы данных при получении активных офисов: {e}")
            raise HTTPException(status_code=500, detail="Ошибка базы данных")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении активных офисов: {e}")
            raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

    return await cache_manager.get_or_set(cache_key, fetch_offices, ttl=600)


@router.get("", response_model=List[OfficeBase])
async def get_offices(
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_OFFICES]))
):
    """Получение всех офисов."""
    try:
        offices = db.query(Office).order_by(Office.id.desc()).all()
        result = []
        for o in offices:
            # Получаем настройки напоминаний для постояльцев
            tenant_reminder_settings = []
            for tr in o.tenant_reminders:
                tenant_reminder_settings.append({
                    "user_id": tr.user_id,
                    "is_enabled": tr.is_enabled
                })

            office_dict = {
                "id": o.id,
                "office_number": o.office_number,
                "floor": o.floor,
                "capacity": o.capacity,
                "price_per_month": o.price_per_month,
                "duration_months": o.duration_months,
                "rental_start_date": o.rental_start_date,
                "rental_end_date": o.rental_end_date,
                "payment_day": o.payment_day,
                "admin_reminder_enabled": o.admin_reminder_enabled,
                "admin_reminder_days": o.admin_reminder_days,
                "admin_reminder_type": o.admin_reminder_type.value if o.admin_reminder_type else None,
                "admin_reminder_datetime": o.admin_reminder_datetime,
                "tenant_reminder_enabled": o.tenant_reminder_enabled,
                "tenant_reminder_days": o.tenant_reminder_days,
                "tenant_reminder_type": o.tenant_reminder_type.value if o.tenant_reminder_type else None,
                "tenant_reminder_datetime": o.tenant_reminder_datetime,
                "payment_type": o.payment_type,
                "last_payment_date": o.last_payment_date,
                "next_payment_date": o.next_payment_date,
                "payment_status": o.payment_status,
                "payment_notes": o.payment_notes,
                "comment": o.comment,
                "is_active": o.is_active,
                "created_at": o.created_at,
                "updated_at": o.updated_at,
                "tenants": [
                    {
                        "id": t.id,
                        "telegram_id": t.telegram_id,
                        "full_name": t.full_name or "Нет имени"
                    }
                    for t in o.tenants
                ],
                "tenant_reminder_settings": tenant_reminder_settings
            }
            result.append(office_dict)

        return result
    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при получении офисов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении офисов: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{office_id}")
async def get_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_OFFICES]))
):
    """Получение офиса по ID."""
    if office_id <= 0:
        raise HTTPException(status_code=400, detail="ID должен быть положительным числом")

    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")

        # Получаем настройки напоминаний
        tenant_reminder_settings = []
        for tr in office.tenant_reminders:
            tenant_reminder_settings.append({
                "user_id": tr.user_id,
                "is_enabled": tr.is_enabled
            })

        return {
            "id": office.id,
            "office_number": office.office_number,
            "floor": office.floor,
            "capacity": office.capacity,
            "price_per_month": office.price_per_month,
            "duration_months": office.duration_months,
            "rental_start_date": office.rental_start_date,
            "rental_end_date": office.rental_end_date,
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "admin_reminder_type": office.admin_reminder_type.value if office.admin_reminder_type else None,
            "admin_reminder_datetime": office.admin_reminder_datetime,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
            "tenant_reminder_type": office.tenant_reminder_type.value if office.tenant_reminder_type else None,
            "tenant_reminder_datetime": office.tenant_reminder_datetime,
            "payment_type": office.payment_type,
            "last_payment_date": office.last_payment_date,
            "next_payment_date": office.next_payment_date,
            "payment_status": office.payment_status,
            "payment_notes": office.payment_notes,
            "comment": office.comment,
            "is_active": office.is_active,
            "created_at": office.created_at,
            "updated_at": office.updated_at,
            "tenants": [
                {
                    "id": t.id,
                    "telegram_id": t.telegram_id,
                    "full_name": t.full_name or "Нет имени"
                }
                for t in office.tenants
            ],
            "tenant_reminder_settings": tenant_reminder_settings
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при получении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("", response_model=OfficeBase)
async def create_office(
    office_data: OfficeCreate,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.CREATE_OFFICES]))
):
    """Создание нового офиса."""
    try:
        # Валидация
        if not office_data.office_number or len(office_data.office_number.strip()) < 1:
            raise HTTPException(status_code=400, detail="Номер офиса обязателен")

        if office_data.floor < 0:
            raise HTTPException(status_code=400, detail="Этаж не может быть отрицательным")

        if office_data.capacity < 1:
            raise HTTPException(status_code=400, detail="Вместимость должна быть минимум 1")

        if office_data.price_per_month <= 0:
            raise HTTPException(status_code=400, detail="Стоимость должна быть больше 0")

        # Проверка уникальности номера офиса
        existing = db.query(Office).filter_by(office_number=office_data.office_number.strip()).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Офис с номером '{office_data.office_number}' уже существует")

        # Проверка существования пользователей
        if office_data.tenant_ids:
            for user_id in office_data.tenant_ids:
                user = db.query(User).filter_by(id=user_id).first()
                if not user:
                    raise HTTPException(status_code=400, detail=f"Пользователь с ID {user_id} не найден")

        # Создание офиса
        office = Office(
            office_number=office_data.office_number.strip(),
            floor=office_data.floor,
            capacity=office_data.capacity,
            price_per_month=office_data.price_per_month,
            duration_months=office_data.duration_months,
            rental_start_date=office_data.rental_start_date,
            rental_end_date=office_data.rental_end_date,
            payment_day=office_data.payment_day,
            admin_reminder_enabled=office_data.admin_reminder_enabled,
            admin_reminder_days=office_data.admin_reminder_days,
            tenant_reminder_enabled=office_data.tenant_reminder_enabled,
            tenant_reminder_days=office_data.tenant_reminder_days,
            comment=office_data.comment,
            payment_type=office_data.payment_type,
            payment_notes=office_data.payment_notes,
            is_active=office_data.is_active
        )

        db.add(office)
        db.flush()  # Получаем ID офиса

        # Вычислить дату окончания аренды, если указаны длительность и дата начала
        if office_data.duration_months and office_data.rental_start_date:
            from dateutil.relativedelta import relativedelta
            office.rental_end_date = office_data.rental_start_date + relativedelta(months=office_data.duration_months)

        # Добавление постояльцев
        if office_data.tenant_ids:
            for user_id in office_data.tenant_ids:
                user = db.query(User).filter_by(id=user_id).first()
                if user:
                    office.tenants.append(user)

        # Создание настроек напоминаний для выбранных постояльцев
        if office_data.tenant_reminder_settings:
            for setting in office_data.tenant_reminder_settings:
                # Проверяем, что пользователь есть среди постояльцев
                if setting.user_id in office_data.tenant_ids:
                    reminder = OfficeTenantReminder(
                        office_id=office.id,
                        user_id=setting.user_id,
                        is_enabled=setting.is_enabled
                    )
                    db.add(reminder)

        # Инициализация платежной системы, если добавлены постояльцы
        if office_data.tenant_ids and office_data.rental_start_date:
            office.payment_type = office_data.payment_type or 'monthly'
            office.payment_status = 'pending'

            if office.payment_type == 'one_time':
                office.next_payment_date = office.rental_end_date
            else:  # monthly
                office.next_payment_date = office_data.rental_start_date + relativedelta(months=1)

        # Планируем задачи напоминаний
        _schedule_office_reminders(office, db)

        db.commit()
        db.refresh(office)

        logger.info(f"Создан офис: {office.office_number} (ID: {office.id}) администратором {current_admin.login}")

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        # Формируем ответ
        tenant_reminder_settings = []
        for tr in office.tenant_reminders:
            tenant_reminder_settings.append({
                "user_id": tr.user_id,
                "is_enabled": tr.is_enabled
            })

        return {
            "id": office.id,
            "office_number": office.office_number,
            "floor": office.floor,
            "capacity": office.capacity,
            "price_per_month": office.price_per_month,
            "duration_months": office.duration_months,
            "rental_start_date": office.rental_start_date,
            "rental_end_date": office.rental_end_date,
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "admin_reminder_type": office.admin_reminder_type.value if office.admin_reminder_type else None,
            "admin_reminder_datetime": office.admin_reminder_datetime,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
            "tenant_reminder_type": office.tenant_reminder_type.value if office.tenant_reminder_type else None,
            "tenant_reminder_datetime": office.tenant_reminder_datetime,
            "payment_type": office.payment_type,
            "last_payment_date": office.last_payment_date,
            "next_payment_date": office.next_payment_date,
            "payment_status": office.payment_status,
            "payment_notes": office.payment_notes,
            "comment": office.comment,
            "is_active": office.is_active,
            "created_at": office.created_at,
            "updated_at": office.updated_at,
            "tenants": [
                {
                    "id": t.id,
                    "telegram_id": t.telegram_id,
                    "full_name": t.full_name or "Нет имени"
                }
                for t in office.tenants
            ],
            "tenant_reminder_settings": tenant_reminder_settings
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Ошибка уникальности при создании офиса: {e}")
        raise HTTPException(status_code=400, detail="Офис с таким номером уже существует")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при создании офиса: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при создании офиса: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/{office_id}", response_model=OfficeBase)
async def update_office(
    office_id: int,
    office_data: OfficeUpdate,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_OFFICES]))
):
    """Обновление офиса."""
    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")

        update_data = office_data.dict(exclude_unset=True)

        # Валидация обновляемых полей
        if "office_number" in update_data:
            office_number = update_data["office_number"].strip()
            if not office_number:
                raise HTTPException(status_code=400, detail="Номер офиса не может быть пустым")

            # Проверка уникальности если номер изменился
            if office_number != office.office_number:
                existing = db.query(Office).filter_by(office_number=office_number).first()
                if existing:
                    raise HTTPException(status_code=400, detail=f"Офис с номером '{office_number}' уже существует")

            update_data["office_number"] = office_number

        if "floor" in update_data and update_data["floor"] < 0:
            raise HTTPException(status_code=400, detail="Этаж не может быть отрицательным")

        if "capacity" in update_data and update_data["capacity"] < 1:
            raise HTTPException(status_code=400, detail="Вместимость должна быть минимум 1")

        if "price_per_month" in update_data and update_data["price_per_month"] <= 0:
            raise HTTPException(status_code=400, detail="Стоимость должна быть больше 0")

        # Пересчет rental_end_date при изменении duration_months или rental_start_date
        if "duration_months" in update_data or "rental_start_date" in update_data:
            # Берем новое значение или существующее
            duration = update_data.get("duration_months") if "duration_months" in update_data else office.duration_months
            start_date = update_data.get("rental_start_date") if "rental_start_date" in update_data else office.rental_start_date

            if duration and start_date:
                from dateutil.relativedelta import relativedelta
                update_data["rental_end_date"] = start_date + relativedelta(months=duration)
                logger.info(f"Recalculated rental_end_date for office {office.id}: {update_data['rental_end_date']}")

        # Обновление постояльцев
        if "tenant_ids" in update_data:
            tenant_ids = update_data.pop("tenant_ids")

            # Проверка существования пользователей
            for user_id in tenant_ids:
                user = db.query(User).filter_by(id=user_id).first()
                if not user:
                    raise HTTPException(status_code=400, detail=f"Пользователь с ID {user_id} не найден")

            # Удаляем старых постояльцев
            office.tenants.clear()

            # Добавляем новых
            for user_id in tenant_ids:
                user = db.query(User).filter_by(id=user_id).first()
                if user:
                    office.tenants.append(user)

            # Автоматическая установка payment_day при добавлении первого постояльца
            if tenant_ids and len(tenant_ids) > 0 and not office.payment_day:
                from datetime import datetime
                from config import MOSCOW_TZ
                office.payment_day = datetime.now(MOSCOW_TZ).day
                logger.info(f"Auto-set payment_day to {office.payment_day} for office {office.id}")

        # Обновление настроек напоминаний
        if "tenant_reminder_settings" in update_data:
            settings = update_data.pop("tenant_reminder_settings")

            # Удаляем старые настройки
            db.query(OfficeTenantReminder).filter_by(office_id=office_id).delete()

            # Добавляем новые
            for setting in settings:
                # Проверяем, что пользователь среди постояльцев
                user_id = setting['user_id'] if isinstance(setting, dict) else setting.user_id
                is_enabled = setting['is_enabled'] if isinstance(setting, dict) else setting.is_enabled

                is_tenant = any(t.id == user_id for t in office.tenants)
                if is_tenant:
                    reminder = OfficeTenantReminder(
                        office_id=office.id,
                        user_id=user_id,
                        is_enabled=is_enabled
                    )
                    db.add(reminder)

        # Обновление остальных полей
        logger.info(f"Updating office {office.id} with data: {update_data}")
        for field, value in update_data.items():
            logger.info(f"Setting {field} = {value} (type: {type(value)})")
            setattr(office, field, value)

        # Пересчет next_payment_date при изменении важных полей
        recalc_payment = ("tenant_ids" in office_data.dict(exclude_unset=True) or
                         "rental_start_date" in update_data or
                         "payment_type" in update_data or
                         "duration_months" in update_data)

        if recalc_payment and office.tenants and office.rental_start_date:
            if office.payment_type == 'one_time':
                office.next_payment_date = office.rental_end_date
            else:  # monthly
                if not office.last_payment_date:
                    office.next_payment_date = office.rental_start_date + relativedelta(months=1)
                # Если уже были платежи, не перезаписываем next_payment_date

            # Установить payment_status в pending если еще не установлен
            if not office.payment_status:
                office.payment_status = 'pending'

        # Планируем задачи напоминаний (отменяет старые и создает новые)
        _schedule_office_reminders(office, db)

        db.commit()
        db.refresh(office)

        logger.info(f"Office after update - admin_reminder_type: {office.admin_reminder_type}, admin_reminder_datetime: {office.admin_reminder_datetime}")
        logger.info(f"Обновлен офис: {office.office_number} (ID: {office.id}) администратором {current_admin.login}")

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        # Формируем ответ
        tenant_reminder_settings = []
        for tr in office.tenant_reminders:
            tenant_reminder_settings.append({
                "user_id": tr.user_id,
                "is_enabled": tr.is_enabled
            })

        return {
            "id": office.id,
            "office_number": office.office_number,
            "floor": office.floor,
            "capacity": office.capacity,
            "price_per_month": office.price_per_month,
            "duration_months": office.duration_months,
            "rental_start_date": office.rental_start_date,
            "rental_end_date": office.rental_end_date,
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "admin_reminder_type": office.admin_reminder_type.value if office.admin_reminder_type else None,
            "admin_reminder_datetime": office.admin_reminder_datetime,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
            "tenant_reminder_type": office.tenant_reminder_type.value if office.tenant_reminder_type else None,
            "tenant_reminder_datetime": office.tenant_reminder_datetime,
            "payment_type": office.payment_type,
            "last_payment_date": office.last_payment_date,
            "next_payment_date": office.next_payment_date,
            "payment_status": office.payment_status,
            "payment_notes": office.payment_notes,
            "comment": office.comment,
            "is_active": office.is_active,
            "created_at": office.created_at,
            "updated_at": office.updated_at,
            "tenants": [
                {
                    "id": t.id,
                    "telegram_id": t.telegram_id,
                    "full_name": t.full_name or "Нет имени"
                }
                for t in office.tenants
            ],
            "tenant_reminder_settings": tenant_reminder_settings
        }

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Ошибка уникальности при обновлении офиса {office_id}: {e}")
        raise HTTPException(status_code=400, detail="Офис с таким номером уже существует")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при обновлении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при обновлении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/{office_id}")
async def delete_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.DELETE_OFFICES]))
):
    """Удаление офиса."""
    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")

        office_number = office.office_number

        db.delete(office)
        db.commit()

        logger.info(f"Удален офис: {office_number} (ID: {office_id}) администратором {current_admin.login}")

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        return {"success": True, "message": f"Офис '{office_number}' успешно удален"}

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при удалении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при удалении офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/{office_id}/clear")
async def clear_office(
    office_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_OFFICES]))
):
    """
    Очистка офиса - удаляет постояльцев, дату платежа, напоминания и комментарий.
    Сохраняет только базовые данные: номер офиса, этаж, стоимость, вместимость.
    """
    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")

        # Удалить постояльцев
        db.execute(delete(office_tenants).where(office_tenants.c.office_id == office_id))

        # Удалить настройки напоминаний
        db.query(OfficeTenantReminder).filter_by(office_id=office_id).delete()

        # Очистить ВСЕ поля кроме базовых (номер офиса, этаж, вместимость, стоимость)
        office.duration_months = None
        office.rental_start_date = None
        office.rental_end_date = None
        office.payment_day = None
        office.payment_type = None
        office.last_payment_date = None
        office.next_payment_date = None
        office.payment_status = None
        office.payment_notes = None
        office.admin_reminder_enabled = False
        office.admin_reminder_days = 5
        office.admin_reminder_type = 'days_before'
        office.admin_reminder_datetime = None
        office.tenant_reminder_enabled = False
        office.tenant_reminder_days = 5
        office.tenant_reminder_type = 'days_before'
        office.tenant_reminder_datetime = None
        office.comment = None

        db.commit()

        logger.info(f"Очищен офис: {office.office_number} (ID: {office.id}) администратором {current_admin.login}")

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        return {
            "success": True,
            "message": f"Офис '{office.office_number}' успешно очищен. Сохранены только базовые данные: номер, этаж, вместимость, стоимость."
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при очистке офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при очистке офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/{source_office_id}/relocate/{target_office_id}")
async def relocate_office(
    source_office_id: int,
    target_office_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_OFFICES]))
):
    """
    Переселение всех сотрудников из одного офиса в другой.
    Копирует информацию о платеже, напоминаниях и настройках уведомлений постояльцев.
    Исходный офис очищается.
    """
    try:
        # Получить оба офиса
        source_office = db.query(Office).filter_by(id=source_office_id).first()
        target_office = db.query(Office).filter_by(id=target_office_id).first()

        if not source_office:
            raise HTTPException(status_code=404, detail="Исходный офис не найден")
        if not target_office:
            raise HTTPException(status_code=404, detail="Целевой офис не найден")

        # Проверить, что в исходном офисе есть постояльцы
        if not source_office.tenants or len(source_office.tenants) == 0:
            raise HTTPException(status_code=400, detail="В исходном офисе нет постояльцев для переселения")

        # Проверить вместимость целевого офиса
        current_tenants_count = len(target_office.tenants) if target_office.tenants else 0
        relocating_tenants_count = len(source_office.tenants)

        if current_tenants_count + relocating_tenants_count > target_office.capacity:
            raise HTTPException(
                status_code=400,
                detail=f"Целевой офис не вмещает всех постояльцев. Вместимость: {target_office.capacity}, "
                       f"текущих постояльцев: {current_tenants_count}, переселяемых: {relocating_tenants_count}"
            )

        # Сохранить список постояльцев для переноса
        tenants_to_relocate = list(source_office.tenants)
        tenant_ids = [t.id for t in tenants_to_relocate]

        # Получить настройки напоминаний постояльцев из исходного офиса
        source_reminder_settings = db.query(OfficeTenantReminder).filter_by(office_id=source_office_id).all()

        # Удалить постояльцев из исходного офиса
        db.execute(delete(office_tenants).where(office_tenants.c.office_id == source_office_id))

        # Добавить постояльцев в целевой офис
        for tenant in tenants_to_relocate:
            # Проверить, что постоялец еще не в целевом офисе
            if tenant not in target_office.tenants:
                target_office.tenants.append(tenant)

        # Перенести настройки напоминаний постояльцев
        db.query(OfficeTenantReminder).filter_by(office_id=source_office_id).delete()

        for reminder in source_reminder_settings:
            new_reminder = OfficeTenantReminder(
                office_id=target_office_id,
                user_id=reminder.user_id,
                is_enabled=reminder.is_enabled
            )
            db.add(new_reminder)

        # Скопировать информацию о платеже и напоминаниях, если в целевом офисе она не установлена
        if not target_office.payment_day and source_office.payment_day:
            target_office.payment_day = source_office.payment_day

        if not target_office.admin_reminder_enabled and source_office.admin_reminder_enabled:
            target_office.admin_reminder_enabled = source_office.admin_reminder_enabled
            target_office.admin_reminder_days = source_office.admin_reminder_days

        if not target_office.tenant_reminder_enabled and source_office.tenant_reminder_enabled:
            target_office.tenant_reminder_enabled = source_office.tenant_reminder_enabled
            target_office.tenant_reminder_days = source_office.tenant_reminder_days

        # Очистить исходный офис
        source_office.payment_day = None
        source_office.admin_reminder_enabled = False
        source_office.tenant_reminder_enabled = False
        source_office.comment = None

        db.commit()

        logger.info(
            f"Переселение выполнено: {relocating_tenants_count} постояльцев из офиса '{source_office.office_number}' (ID: {source_office_id}) "
            f"в офис '{target_office.office_number}' (ID: {target_office_id}) администратором {current_admin.login}"
        )

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        return {
            "success": True,
            "message": f"Успешно переселено {relocating_tenants_count} постояльцев из офиса '{source_office.office_number}' "
                       f"в офис '{target_office.office_number}'",
            "relocated_tenants": [{"id": t.id, "full_name": t.full_name} for t in tenants_to_relocate],
            "source_office": source_office.office_number,
            "target_office": target_office.office_number
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка базы данных при переселении из офиса {source_office_id} в {target_office_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при переселении из офиса {source_office_id} в {target_office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

# ===== PAYMENT ENDPOINTS =====

@router.post("/{office_id}/pay", response_model=OfficeBase)
async def record_office_payment(
    office_id: int,
    payment_data: OfficePaymentRecord,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_OFFICES]))
):
    """
    Записать платеж по офису.
    
    Логика:
    1. Проверить наличие постояльцев
    2. Создать запись в OfficePaymentHistory
    3. Обновить last_payment_date, payment_status = 'paid'
    4. Рассчитать next_payment_date:
       - monthly: +1 месяц от текущего next_payment_date
       - one_time: = rental_end_date
    5. Отправить уведомления в Telegram
    """
    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")
        
        # Валидация: должны быть постояльцы
        if not office.tenants or len(office.tenants) == 0:
            raise HTTPException(
                status_code=400, 
                detail="Невозможно записать платеж для офиса без постояльцев"
            )
        
        # Валидация: должен быть установлен тип платежа
        if not office.payment_type:
            raise HTTPException(
                status_code=400,
                detail="Тип платежа не установлен. Отредактируйте офис и укажите тип платежа."
            )
        
        # Определяем параметры платежа
        payment_date = payment_data.payment_date or datetime.now(MOSCOW_TZ)
        amount = payment_data.amount or office.price_per_month
        
        # Определяем период, за который производится оплата
        if office.payment_type == 'one_time':
            # Одноразовый платеж покрывает весь период аренды
            period_start = office.rental_start_date or payment_date
            period_end = office.rental_end_date
            
            if not period_end:
                raise HTTPException(
                    status_code=400,
                    detail="Для одноразового платежа необходимо указать дату окончания аренды"
                )
        else:  # monthly
            # Месячный платеж
            if office.last_payment_date:
                # Следующий месяц от последнего платежа
                period_start = office.last_payment_date
                period_end = period_start + relativedelta(months=1)
            else:
                # Первый платеж
                period_start = office.rental_start_date or payment_date
                period_end = period_start + relativedelta(months=1)
        
        # Создаем запись в истории платежей
        payment_history = OfficePaymentHistory(
            office_id=office.id,
            payment_date=payment_date,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            payment_type=office.payment_type,
            recorded_by_admin_id=current_admin.id,
            notes=payment_data.notes
        )
        db.add(payment_history)
        
        # Обновляем офис
        office.last_payment_date = payment_date
        office.payment_status = 'paid'

        # Обновление даты начала аренды если требуется
        if payment_data.update_rental_start_date and payment_date != office.rental_start_date:
            logger.info(f"Updating rental_start_date from {office.rental_start_date} to {payment_date}")
            office.rental_start_date = payment_date

            # Пересчитать rental_end_date
            if office.duration_months:
                office.rental_end_date = payment_date + relativedelta(months=office.duration_months)
                logger.info(f"Recalculated rental_end_date to {office.rental_end_date}")

        # Рассчитываем следующую дату платежа
        if office.payment_type == 'one_time':
            # Для одноразового платежа следующий платеж - окончание аренды
            office.next_payment_date = office.rental_end_date
        else:  # monthly
            office.next_payment_date = period_end

            # Проверяем, не выходит ли следующий платеж за рамки аренды
            if office.rental_end_date:
                # Приводим даты к aware (с часовым поясом) для корректного сравнения
                # Если next_payment_date не имеет таймзоны, добавляем её
                check_next_date = office.next_payment_date
                if check_next_date.tzinfo is None:
                    check_next_date = check_next_date.replace(tzinfo=MOSCOW_TZ)

                # Если rental_end_date не имеет таймзоны, добавляем её
                check_end_date = office.rental_end_date
                if check_end_date.tzinfo is None:
                    check_end_date = check_end_date.replace(tzinfo=MOSCOW_TZ)

                # Сравниваем даты с одинаковыми настройками таймзоны
                if check_next_date > check_end_date:
                    office.next_payment_date = office.rental_end_date
        
        db.commit()
        db.refresh(office)
        
        logger.info(
            f"Платеж записан для офиса {office.office_number} "
            f"(ID: {office.id}) администратором {current_admin.login}. "
            f"Сумма: {amount}, Период: {period_start} - {period_end}"
        )
        
        # Отправляем уведомления
        await _send_payment_notifications(office, amount, period_start, period_end, current_admin, db)
        
        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))
        
        # Формируем ответ
        tenant_reminder_settings = []
        for tr in office.tenant_reminders:
            tenant_reminder_settings.append({
                "user_id": tr.user_id,
                "is_enabled": tr.is_enabled
            })
        
        return {
            "id": office.id,
            "office_number": office.office_number,
            "floor": office.floor,
            "capacity": office.capacity,
            "price_per_month": office.price_per_month,
            "duration_months": office.duration_months,
            "rental_start_date": office.rental_start_date,
            "rental_end_date": office.rental_end_date,
            "payment_day": office.payment_day,
            "payment_type": office.payment_type,
            "last_payment_date": office.last_payment_date,
            "next_payment_date": office.next_payment_date,
            "payment_status": office.payment_status,
            "payment_notes": office.payment_notes,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "admin_reminder_type": office.admin_reminder_type.value if office.admin_reminder_type else "days_before",
            "admin_reminder_datetime": office.admin_reminder_datetime,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
            "tenant_reminder_type": office.tenant_reminder_type.value if office.tenant_reminder_type else "days_before",
            "tenant_reminder_datetime": office.tenant_reminder_datetime,
            "comment": office.comment,
            "is_active": office.is_active,
            "created_at": office.created_at,
            "updated_at": office.updated_at,
            "tenants": [
                {
                    "id": t.id,
                    "telegram_id": t.telegram_id,
                    "full_name": t.full_name or "Нет имени"
                }
                for t in office.tenants
            ],
            "tenant_reminder_settings": tenant_reminder_settings
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка записи платежа для офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/{office_id}/payment-status", response_model=OfficePaymentButtonStatus)
async def get_office_payment_button_status(
    office_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_OFFICES]))
):
    """
    Проверить, должна ли отображаться кнопка "Оплатить" для офиса.
    
    Кнопка показывается если:
    1. Есть постояльцы
    2. next_payment_date установлен
    3. Текущая дата >= (next_payment_date - admin_reminder_days)
    4. payment_status != 'paid' для текущего периода
    """
    try:
        office = db.query(Office).filter_by(id=office_id).first()
        if not office:
            raise HTTPException(status_code=404, detail="Офис не найден")
        
        # Базовые проверки
        has_tenants = office.tenants and len(office.tenants) > 0
        
        if not has_tenants or not office.next_payment_date:
            return OfficePaymentButtonStatus(
                show_button=False,
                days_until_due=None,
                next_payment_date=office.next_payment_date,
                payment_status=office.payment_status,
                can_pay_early=False
            )
        
        # Рассчитываем дни до платежа
        today = datetime.now(MOSCOW_TZ)
        next_payment_aware = office.next_payment_date.replace(tzinfo=MOSCOW_TZ) if office.next_payment_date.tzinfo is None else office.next_payment_date
        days_until_due = (next_payment_aware - today).days
        
        # Кнопка показывается за N дней до платежа (admin_reminder_days)
        reminder_days = office.admin_reminder_days or 5
        show_button = days_until_due <= reminder_days
        
        # Также проверяем статус платежа
        if office.payment_status == 'paid' and days_until_due > 0:
            # Уже оплачен текущий период
            show_button = False
        
        return OfficePaymentButtonStatus(
            show_button=show_button,
            days_until_due=days_until_due,
            next_payment_date=office.next_payment_date,
            payment_status=office.payment_status,
            can_pay_early=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка проверки статуса кнопки оплаты для офиса {office_id}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


def _schedule_office_reminders(office: Office, db: Session) -> None:
    """
    Планирование задач напоминаний для офиса.
    Отменяет старые задачи и создает новые при необходимости.

    Теперь с синхронизацией в БД для полной видимости задач.
    """
    from tasks.office_tasks import send_office_reminder
    from celery_app import celery_app
    from celery.result import AsyncResult
    from datetime import time as time_type
    from models.models import ScheduledTask, TaskType, TaskStatus

    now = datetime.now(MOSCOW_TZ)

    # Админ напоминание
    if office.admin_reminder_enabled and office.next_payment_date:
        # Удаляем старую задачу из БД и Celery
        if office.admin_reminder_task_id:
            try:
                # Находим задачу в БД
                old_task = db.query(ScheduledTask).filter(
                    ScheduledTask.celery_task_id == office.admin_reminder_task_id
                ).first()

                # Отменяем в Celery
                result = AsyncResult(office.admin_reminder_task_id, app=celery_app)
                result.revoke(terminate=True)
                logger.info(f"Revoked old admin reminder task {office.admin_reminder_task_id} for office #{office.id}")

                # Удаляем из БД или обновляем статус
                if old_task:
                    old_task.status = TaskStatus.CANCELLED
                    old_task.executed_at = now
                    logger.info(f"Cancelled old task #{old_task.id} in DB")

            except Exception as e:
                logger.error(f"Error cancelling old admin task: {e}")
            office.admin_reminder_task_id = None

        # Вычисляем дату/время напоминания
        payment_date = office.next_payment_date
        if payment_date.tzinfo is None:
            payment_date = payment_date.replace(tzinfo=MOSCOW_TZ)

        if office.admin_reminder_type == ReminderType.days_before:
            # За N дней до платежа
            reminder_date = payment_date.date() - timedelta(days=office.admin_reminder_days)
            reminder_datetime = datetime.combine(reminder_date, time_type(10, 0))  # 10:00 утра
            reminder_datetime = MOSCOW_TZ.localize(reminder_datetime) if reminder_datetime.tzinfo is None else reminder_datetime
        elif office.admin_reminder_type == ReminderType.specific_datetime and office.admin_reminder_datetime:
            # В конкретное время
            reminder_datetime = office.admin_reminder_datetime
            if reminder_datetime.tzinfo is None:
                reminder_datetime = reminder_datetime.replace(tzinfo=MOSCOW_TZ)
        else:
            reminder_datetime = None

        # Создаем задачу если дата в будущем
        if reminder_datetime and reminder_datetime > now:
            try:
                # 1. Создаем запись в БД
                scheduled_task = ScheduledTask(
                    task_type=TaskType.OFFICE_REMINDER_ADMIN,
                    office_id=office.id,
                    scheduled_datetime=reminder_datetime,
                    created_by='system',
                    status=TaskStatus.PENDING,
                    params={
                        'office_number': office.office_number,
                        'floor': office.floor,
                        'reminder_type': 'admin'
                    }
                )
                db.add(scheduled_task)
                db.flush()  # Получаем ID

                # 2. Создаем задачу в Celery
                task_result = send_office_reminder.apply_async(
                    args=[office.id, 'admin'],
                    eta=reminder_datetime
                )

                # 3. Сохраняем celery_task_id в БД и office
                scheduled_task.celery_task_id = task_result.id
                office.admin_reminder_task_id = task_result.id

                logger.info(
                    f"📅 Запланировано admin напоминание для офиса #{office.id} "
                    f"на {reminder_datetime.strftime('%d.%m.%Y %H:%M')} "
                    f"(task_id: {task_result.id}, db_id: {scheduled_task.id})"
                )
            except Exception as e:
                logger.error(f"Error scheduling admin reminder for office #{office.id}: {e}", exc_info=True)

    # Постояльцы напоминание
    if office.tenant_reminder_enabled and office.next_payment_date:
        # Удаляем старую задачу из БД и Celery
        if office.tenant_reminder_task_id:
            try:
                # Находим задачу в БД
                old_task = db.query(ScheduledTask).filter(
                    ScheduledTask.celery_task_id == office.tenant_reminder_task_id
                ).first()

                # Отменяем в Celery
                result = AsyncResult(office.tenant_reminder_task_id, app=celery_app)
                result.revoke(terminate=True)
                logger.info(f"Revoked old tenant reminder task {office.tenant_reminder_task_id} for office #{office.id}")

                # Обновляем статус в БД
                if old_task:
                    old_task.status = TaskStatus.CANCELLED
                    old_task.executed_at = now
                    logger.info(f"Cancelled old task #{old_task.id} in DB")

            except Exception as e:
                logger.error(f"Error revoking old tenant task: {e}")
            office.tenant_reminder_task_id = None

        # Вычисляем дату/время напоминания
        payment_date = office.next_payment_date
        if payment_date.tzinfo is None:
            payment_date = payment_date.replace(tzinfo=MOSCOW_TZ)

        if office.tenant_reminder_type == ReminderType.days_before:
            # За N дней до платежа
            reminder_date = payment_date.date() - timedelta(days=office.tenant_reminder_days)
            reminder_datetime = datetime.combine(reminder_date, time_type(10, 0))  # 10:00 утра
            reminder_datetime = MOSCOW_TZ.localize(reminder_datetime) if reminder_datetime.tzinfo is None else reminder_datetime
        elif office.tenant_reminder_type == ReminderType.specific_datetime and office.tenant_reminder_datetime:
            # В конкретное время
            reminder_datetime = office.tenant_reminder_datetime
            if reminder_datetime.tzinfo is None:
                reminder_datetime = reminder_datetime.replace(tzinfo=MOSCOW_TZ)
        else:
            reminder_datetime = None

        # Создаем задачу если дата в будущем
        if reminder_datetime and reminder_datetime > now:
            try:
                # 1. Создаем запись в БД
                scheduled_task = ScheduledTask(
                    task_type=TaskType.OFFICE_REMINDER_TENANT,
                    office_id=office.id,
                    scheduled_datetime=reminder_datetime,
                    created_by='system',
                    status=TaskStatus.PENDING,
                    params={
                        'office_number': office.office_number,
                        'floor': office.floor,
                        'reminder_type': 'tenant'
                    }
                )
                db.add(scheduled_task)
                db.flush()  # Получаем ID

                # 2. Создаем задачу в Celery
                task_result = send_office_reminder.apply_async(
                    args=[office.id, 'tenant'],
                    eta=reminder_datetime
                )

                # 3. Сохраняем celery_task_id в БД и office
                scheduled_task.celery_task_id = task_result.id
                office.tenant_reminder_task_id = task_result.id

                logger.info(
                    f"📅 Запланировано tenant напоминание для офиса #{office.id} "
                    f"на {reminder_datetime.strftime('%d.%m.%Y %H:%M')} "
                    f"(task_id: {task_result.id}, db_id: {scheduled_task.id})"
                )
            except Exception as e:
                logger.error(f"Error scheduling tenant reminder for office #{office.id}: {e}", exc_info=True)

    db.flush()  # Сохраняем изменения task_id


async def _send_payment_notifications(
    office: Office,
    amount: float,
    period_start: datetime,
    period_end: datetime,
    admin: CachedAdmin,
    db: Session
):
    """Отправка уведомлений о платеже в Telegram."""
    from utils.bot_instance import get_bot

    bot = get_bot()
    
    # Уведомление администратору
    try:
        # Формируем строку с информацией о следующем платеже
        next_payment_info = 'Аренда полностью оплачена'
        if office.payment_type != 'one_time' and office.next_payment_date:
            next_payment_info = f'Следующий платеж: {office.next_payment_date.strftime("%d.%m.%Y")}'

        admin_message = (
            f"✅ Платеж за офис записан\n\n"
            f"Офис: {office.office_number} (этаж {office.floor})\n"
            f"Сумма: {amount} ₽\n"
            f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n"
            f"Тип платежа: {'Разовый' if office.payment_type == 'one_time' else 'Ежемесячный'}\n"
            f"Записал: {admin.login}\n\n"
            f"{next_payment_info}"
        )
        await bot.send_message(ADMIN_TELEGRAM_ID, admin_message)
        logger.info(f"Отправлено уведомление админу о платеже для офиса {office.office_number}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")
    
    # Уведомления постояльцам
    if office.tenant_reminder_enabled:
        # Получаем постояльцев с включенными напоминаниями
        tenant_reminders = db.query(OfficeTenantReminder).filter(
            OfficeTenantReminder.office_id == office.id,
            OfficeTenantReminder.is_enabled == True
        ).all()
        
        for tr in tenant_reminders:
            try:
                user = tr.user

                # Формируем строку с информацией о следующем платеже для постояльца
                payment_info = 'Аренда полностью оплачена'
                if office.payment_type == 'one_time' and office.rental_end_date:
                    payment_info = f'Аренда полностью оплачена до {office.rental_end_date.strftime("%d.%m.%Y")}'
                elif office.payment_type != 'one_time' and office.next_payment_date:
                    payment_info = f'Следующий платеж: {office.next_payment_date.strftime("%d.%m.%Y")}'

                tenant_message = (
                    f"✅ Платеж принят\n\n"
                    f"Офис: {office.office_number} (этаж {office.floor})\n"
                    f"Сумма: {amount} ₽\n"
                    f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n\n"
                    f"{payment_info}"
                )
                await bot.send_message(user.telegram_id, tenant_message)
                logger.info(f"Отправлено уведомление пользователю {user.telegram_id} о платеже")

                await asyncio.sleep(0.3)  # Rate limiting
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления постояльцу: {e}")
