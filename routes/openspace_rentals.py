# routes/openspace_rentals.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from models.models import (
    UserOpenspaceRental,
    OpenspacePaymentHistory,
    User,
    Tariff,
    RentalType,
    Permission,
    Booking,
    MOSCOW_TZ,
    DatabaseManager
)
from dependencies import get_db, verify_token_with_permissions, CachedAdmin
from schemas.openspace_schemas import (
    OpenspaceRentalBase,
    OpenspaceRentalCreate,
    OpenspaceRentalUpdate,
    OpenspacePaymentRecord,
    UserOpenspaceInfo
)
from utils.logger import get_logger
from config import ADMIN_TELEGRAM_ID
from utils.cache_invalidation import invalidate_user_cache
from utils.cache_manager import cache_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/openspace-rentals", tags=["openspace-rentals"])


def convert_rental(rental):
    """Конвертирует объект UserOpenspaceRental в dict с преобразованием enum."""
    if not rental:
        return None
    rental_dict = {
        "id": rental.id,
        "user_id": rental.user_id,
        "rental_type": rental.rental_type.value if hasattr(rental.rental_type, 'value') else rental.rental_type,
        "workplace_number": rental.workplace_number,
        "start_date": rental.start_date,
        "end_date": rental.end_date,
        "is_active": rental.is_active,
        "price": rental.price,
        "tariff_id": rental.tariff_id,
        "payment_status": rental.payment_status.value if rental.payment_status and hasattr(rental.payment_status, 'value') else rental.payment_status,
        "last_payment_date": rental.last_payment_date,
        "next_payment_date": rental.next_payment_date,
        "admin_reminder_enabled": rental.admin_reminder_enabled,
        "admin_reminder_days": rental.admin_reminder_days,
        "tenant_reminder_enabled": rental.tenant_reminder_enabled,
        "tenant_reminder_days": rental.tenant_reminder_days,
        "created_at": rental.created_at,
        "updated_at": rental.updated_at,
        "deactivated_at": rental.deactivated_at,
        "notes": rental.notes
    }
    return rental_dict


@router.get("/user/{user_id}/info", response_model=UserOpenspaceInfo)
async def get_user_openspace_info(
    user_id: int,
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.VIEW_USERS]))
):
    """Получение информации об аренде опенспейса для пользователя."""

    def _get_openspace_info(session):
        # Проверяем существование пользователя
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Получаем активную аренду
        active_rental = session.query(UserOpenspaceRental).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

        # Получаем всю историю аренд (последние 20)
        rental_history = session.query(UserOpenspaceRental).filter_by(
            user_id=user_id
        ).order_by(UserOpenspaceRental.created_at.desc()).limit(20).all()

        return {
            "has_active_rental": active_rental is not None,
            "active_rental": convert_rental(active_rental),
            "rental_history": [convert_rental(r) for r in rental_history]
        }

    try:
        return DatabaseManager.safe_execute(_get_openspace_info)
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Ошибка БД при получении информации об аренде для user_id={user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при получении информации об аренде: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/user/{user_id}/create", response_model=OpenspaceRentalBase)
async def create_openspace_rental(
    user_id: int,
    rental_data: OpenspaceRentalCreate,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_USERS]))
):
    """Создание новой аренды опенспейса для пользователя."""
    try:
        # Проверяем существование пользователя
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Проверяем наличие активной аренды
        existing_rental = db.query(UserOpenspaceRental).filter_by(
            user_id=user_id,
            is_active=True
        ).first()

        if existing_rental:
            # Если есть активная месячная аренда - запрещаем создание любой новой аренды
            if existing_rental.rental_type in [RentalType.MONTHLY_FIXED, RentalType.MONTHLY_FLOATING]:
                raise HTTPException(
                    status_code=400,
                    detail="У пользователя уже есть активная месячная аренда опенспейса"
                )

            # Если есть активная однодневная аренда
            if existing_rental.rental_type == RentalType.ONE_DAY:
                # Запрещаем создание еще одной однодневной аренды
                if rental_data.rental_type == "one_day":
                    raise HTTPException(
                        status_code=400,
                        detail="У пользователя уже есть активное однодневное посещение"
                    )

                # Разрешаем создание месячной аренды - автоматически деактивируем однодневную
                if rental_data.rental_type in ["monthly_fixed", "monthly_floating"]:
                    logger.info(f"Деактивация однодневной аренды rental_id={existing_rental.id} перед созданием месячной")
                    existing_rental.is_active = False
                    existing_rental.deactivated_at = datetime.now(MOSCOW_TZ)
                    existing_rental.updated_at = datetime.now(MOSCOW_TZ)

        # Вычисляем end_date в зависимости от типа аренды
        end_date = None
        if rental_data.rental_type == "one_day":
            # Конец текущего дня (23:59:59)
            end_date = rental_data.start_date.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        elif rental_data.rental_type in ["monthly_fixed", "monthly_floating"]:
            # Добавляем месяцы к дате начала
            if not rental_data.duration_months:
                raise HTTPException(
                    status_code=400,
                    detail="Для месячных тарифов необходимо указать длительность"
                )
            end_date = rental_data.start_date + relativedelta(months=rental_data.duration_months)

        # Создаем новую аренду
        new_rental = UserOpenspaceRental(
            user_id=user_id,
            rental_type=RentalType(rental_data.rental_type),
            workplace_number=rental_data.workplace_number,
            start_date=rental_data.start_date,
            end_date=end_date,
            is_active=True,
            price=rental_data.price,
            tariff_id=rental_data.tariff_id,
            admin_reminder_enabled=rental_data.admin_reminder_enabled,
            admin_reminder_days=rental_data.admin_reminder_days,
            tenant_reminder_enabled=rental_data.tenant_reminder_enabled,
            tenant_reminder_days=rental_data.tenant_reminder_days,
            notes=rental_data.notes
        )

        # Для месячных тарифов инициализируем платежную систему
        if rental_data.rental_type in ["monthly_fixed", "monthly_floating"]:
            new_rental.payment_status = "pending"
            new_rental.next_payment_date = rental_data.start_date + relativedelta(months=1)

        # Для разовой аренды автоматически создаем платеж
        elif rental_data.rental_type == "one_day":
            current_time = datetime.now(MOSCOW_TZ)
            new_rental.payment_status = "paid"
            new_rental.last_payment_date = current_time

        db.add(new_rental)
        db.flush()  # Получаем new_rental.id до commit

        # Создаем историю платежа для разовой аренды
        if rental_data.rental_type == "one_day":
            payment_history = OpenspacePaymentHistory(
                rental_id=new_rental.id,
                payment_date=new_rental.last_payment_date,
                amount=rental_data.price,
                period_start=rental_data.start_date,
                period_end=end_date,
                recorded_by_admin_id=current_admin.id,
                notes="Автоматическая оплата при создании разовой аренды"
            )
            db.add(payment_history)

            # Создаем запись в таблице бронирований для отображения в календаре
            # Проверяем наличие tariff_id
            if not rental_data.tariff_id:
                raise HTTPException(
                    status_code=400,
                    detail="Для однодневной аренды необходимо указать tariff_id"
                )

            booking = Booking(
                user_id=user_id,
                tariff_id=rental_data.tariff_id,
                visit_date=rental_data.start_date.date(),
                visit_time=None,  # Время не указано для опенспейса
                duration=None,  # Длительность не указана
                promocode_id=None,
                amount=rental_data.price,
                payment_id=None,
                paid=True,  # Автоматически оплачено
                rubitime_id=None,
                confirmed=True,  # Автоматически подтверждено
                comment=f"Опенспейс: {rental_data.notes or 'Разовая аренда'}"
            )
            db.add(booking)
            logger.info(f"Создана запись в bookings для опенспейс аренды rental_id={new_rental.id}")

        db.commit()
        db.refresh(new_rental)

        # Инвалидируем кэш пользователя
        await invalidate_user_cache(user_id)

        # Инвалидируем кэш календаря для разовых бронирований
        if rental_data.rental_type == "one_day":
            await cache_manager.clear_pattern("dashboard:bookings_calendar:*")
            logger.info(f"Инвалидирован кэш календаря для опенспейс аренды {new_rental.id}")

        # Отправляем уведомление администратору (опционально)
        try:
            from utils.bot_instance import get_bot_instance
            bot = get_bot_instance()
            if bot:
                rental_type_label = {
                    "one_day": "Один день",
                    "monthly_fixed": "Фикс месяц",
                    "monthly_floating": "Нефикс месяц"
                }.get(rental_data.rental_type, rental_data.rental_type)

                message = (
                    f"✅ Создана аренда опенспейса\n\n"
                    f"👤 Пользователь: {user.full_name or 'Нет имени'} (ID: {user_id})\n"
                    f"📋 Тип: {rental_type_label}\n"
                    f"💰 Цена: {rental_data.price} ₽\n"
                    f"📅 Период: {rental_data.start_date.strftime('%d.%m.%Y')} - "
                    f"{end_date.strftime('%d.%m.%Y') if end_date else 'Не указан'}"
                )

                if rental_data.workplace_number:
                    message += f"\n🪑 Место: {rental_data.workplace_number}"

                if rental_data.rental_type == "one_day":
                    message += "\n✅ Оплата: Автоматически записана"

                await bot.send_message(ADMIN_TELEGRAM_ID, message)
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление администратору: {e}")

        log_message = f"Создана аренда опенспейса для user_id={user_id}, rental_id={new_rental.id}"
        if rental_data.rental_type == "one_day":
            log_message += f", payment auto-recorded, amount={rental_data.price}"
        logger.info(log_message)
        return convert_rental(new_rental)

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка БД при создании аренды: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при создании аренды: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.put("/{rental_id}", response_model=OpenspaceRentalBase)
async def update_openspace_rental(
    rental_id: int,
    rental_update: OpenspaceRentalUpdate,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_USERS]))
):
    """Обновление аренды опенспейса."""
    try:
        rental = db.query(UserOpenspaceRental).filter_by(id=rental_id).first()
        if not rental:
            raise HTTPException(status_code=404, detail="Аренда не найдена")

        # Обновляем только переданные поля
        update_data = rental_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rental, field, value)

        rental.updated_at = datetime.now(MOSCOW_TZ)
        db.commit()
        db.refresh(rental)

        # Инвалидируем кэш пользователя
        await invalidate_user_cache(rental.user_id)

        # Инвалидируем кэш календаря для разовых бронирований
        if rental.rental_type == RentalType.ONE_DAY:
            await cache_manager.clear_pattern("dashboard:bookings_calendar:*")
            logger.info(f"Инвалидирован кэш календаря при обновлении опенспейс аренды {rental_id}")

        logger.info(f"Обновлена аренда rental_id={rental_id}")
        return convert_rental(rental)

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка БД при обновлении аренды rental_id={rental_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при обновлении аренды: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/{rental_id}/deactivate")
async def deactivate_openspace_rental(
    rental_id: int,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_USERS]))
):
    """Деактивация аренды опенспейса."""
    try:
        rental = db.query(UserOpenspaceRental).filter_by(id=rental_id).first()
        if not rental:
            raise HTTPException(status_code=404, detail="Аренда не найдена")

        if not rental.is_active:
            raise HTTPException(status_code=400, detail="Аренда уже деактивирована")

        rental.is_active = False
        rental.deactivated_at = datetime.now(MOSCOW_TZ)
        rental.updated_at = datetime.now(MOSCOW_TZ)

        db.commit()

        # Инвалидируем кэш пользователя
        await invalidate_user_cache(rental.user_id)

        # Инвалидируем кэш календаря для разовых бронирований
        if rental.rental_type == RentalType.ONE_DAY:
            await cache_manager.clear_pattern("dashboard:bookings_calendar:*")
            logger.info(f"Инвалидирован кэш календаря при деактивации опенспейс аренды {rental_id}")

        logger.info(f"Деактивирована аренда rental_id={rental_id}")
        return {"message": "Аренда успешно деактивирована", "rental_id": rental_id}

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка БД при деактивации аренды rental_id={rental_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при деактивации аренды: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/{rental_id}/pay")
async def record_openspace_payment(
    rental_id: int,
    payment_data: OpenspacePaymentRecord,
    db: Session = Depends(get_db),
    current_admin: CachedAdmin = Depends(verify_token_with_permissions([Permission.EDIT_USERS]))
):
    """Запись платежа по аренде опенспейса (для месячных тарифов)."""
    try:
        rental = db.query(UserOpenspaceRental).filter_by(id=rental_id).first()
        if not rental:
            raise HTTPException(status_code=404, detail="Аренда не найдена")

        # Проверяем, что это месячный тариф
        if rental.rental_type == RentalType.ONE_DAY:
            raise HTTPException(
                status_code=400,
                detail="Запись платежей доступна только для месячных тарифов"
            )

        # Используем переданную сумму или цену аренды
        amount = payment_data.amount if payment_data.amount else rental.price
        payment_date = payment_data.payment_date if payment_data.payment_date else datetime.now(MOSCOW_TZ)

        # Определяем период платежа
        if rental.last_payment_date:
            period_start = rental.last_payment_date
        else:
            period_start = rental.start_date

        period_end = period_start + relativedelta(months=1)

        # Создаем запись в истории платежей
        payment_history = OpenspacePaymentHistory(
            rental_id=rental_id,
            payment_date=payment_date,
            amount=amount,
            period_start=period_start,
            period_end=period_end,
            recorded_by_admin_id=current_admin.id,
            notes=payment_data.notes
        )
        db.add(payment_history)

        # Обновляем данные аренды
        rental.last_payment_date = payment_date
        rental.next_payment_date = period_end
        rental.payment_status = "paid"
        rental.updated_at = datetime.now(MOSCOW_TZ)

        db.commit()
        db.refresh(payment_history)

        # Инвалидируем кэш пользователя (асинхронно в фоне)
        # Кэш инвалидируется автоматически при следующем запросе
        pass

        # Отправляем уведомление пользователю
        try:
            from utils.bot_instance import get_bot_instance
            bot = get_bot_instance()
            user = db.query(User).filter_by(id=rental.user_id).first()

            if bot and user and rental.tenant_reminder_enabled:
                rental_type_label = {
                    "monthly_fixed": "Фикс месяц",
                    "monthly_floating": "Нефикс месяц"
                }.get(rental.rental_type.value, rental.rental_type.value)

                message = (
                    f"✅ Платеж принят\n\n"
                    f"📋 Тип аренды: {rental_type_label}\n"
                    f"💰 Сумма: {amount} ₽\n"
                    f"📅 Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n"
                    f"📆 Следующий платеж: {period_end.strftime('%d.%m.%Y')}"
                )

                if rental.workplace_number:
                    message += f"\n🪑 Ваше место: {rental.workplace_number}"

                await bot.send_message(user.telegram_id, message)
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю: {e}")

        logger.info(f"Записан платеж для rental_id={rental_id}, amount={amount}")
        return {
            "message": "Платеж успешно записан",
            "payment_id": payment_history.id,
            "next_payment_date": rental.next_payment_date
        }

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка БД при записи платежа rental_id={rental_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка базы данных")
    except Exception as e:
        db.rollback()
        logger.error(f"Неожиданная ошибка при записи платежа: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")
