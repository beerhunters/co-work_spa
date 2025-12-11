# routes/offices.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import delete

from models.models import Office, office_tenants, OfficeTenantReminder, User, Permission
from dependencies import get_db, verify_token, verify_token_with_permissions, CachedAdmin
from schemas.office_schemas import OfficeBase, OfficeCreate, OfficeUpdate, OfficeTenantBase, TenantReminderSetting
from utils.logger import get_logger
from utils.cache_manager import cache_manager

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
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
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
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
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
        for field, value in update_data.items():
            setattr(office, field, value)

        db.commit()
        db.refresh(office)

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
            "payment_day": office.payment_day,
            "admin_reminder_enabled": office.admin_reminder_enabled,
            "admin_reminder_days": office.admin_reminder_days,
            "tenant_reminder_enabled": office.tenant_reminder_enabled,
            "tenant_reminder_days": office.tenant_reminder_days,
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

        # Очистить поля
        office.payment_day = None
        office.admin_reminder_enabled = False
        office.tenant_reminder_enabled = False
        office.comment = None

        db.commit()

        logger.info(f"Очищен офис: {office.office_number} (ID: {office.id}) администратором {current_admin.login}")

        # Инвалидация кэша
        await cache_manager.delete(cache_manager.get_cache_key("offices", "active"))

        return {
            "success": True,
            "message": f"Офис '{office.office_number}' успешно очищен. Удалены постояльцы, дата платежа, напоминания и комментарий."
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
