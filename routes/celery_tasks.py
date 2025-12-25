"""
API endpoints for Celery tasks monitoring (Superadmin only)
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from celery.result import AsyncResult
from celery_app import celery_app
from dependencies import require_super_admin, CachedAdmin
from models.models import Booking, DatabaseManager, User, Tariff
from utils.logger import get_logger
from config import MOSCOW_TZ

logger = get_logger(__name__)
router = APIRouter(prefix="/celery-tasks", tags=["celery-tasks"])


@router.get("/list")
async def get_celery_tasks(
    status_filter: Optional[str] = None,  # active, scheduled, revoked, all
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить список Celery задач (только для Суперадмина).

    Args:
        status_filter: Фильтр по статусу (active, scheduled, revoked, all)

    Returns:
        Dict с задачами, сгруппированными по статусам
    """
    try:
        logger.info(f"Получение списка Celery задач администратором {current_admin.login}")

        # Получаем информацию из Celery inspect
        inspect = celery_app.control.inspect()

        # Активные задачи (выполняются прямо сейчас)
        active_tasks = []
        active_raw = inspect.active()
        if active_raw:
            for worker, tasks in active_raw.items():
                for task in tasks:
                    active_tasks.append({
                        'task_id': task.get('id'),
                        'name': task.get('name'),
                        'args': str(task.get('args', [])),
                        'kwargs': str(task.get('kwargs', {})),
                        'worker': worker,
                        'status': 'ACTIVE',
                        'time_start': task.get('time_start'),
                    })

        # Запланированные задачи (в очереди, будут выполнены позже)
        scheduled_tasks = []
        scheduled_raw = inspect.scheduled()
        if scheduled_raw:
            for worker, tasks in scheduled_raw.items():
                for task in tasks:
                    # task - это dict с информацией о запланированной задаче
                    request = task.get('request', {})
                    eta_timestamp = task.get('eta')

                    scheduled_tasks.append({
                        'task_id': request.get('id'),
                        'name': request.get('name'),
                        'args': str(request.get('args', [])),
                        'kwargs': str(request.get('kwargs', {})),
                        'worker': worker,
                        'status': 'SCHEDULED',
                        'eta': eta_timestamp,
                        'priority': task.get('priority', 0),
                    })

        # Reserved задачи (получены worker, но еще не выполняются)
        reserved_tasks = []
        reserved_raw = inspect.reserved()
        if reserved_raw:
            for worker, tasks in reserved_raw.items():
                for task in tasks:
                    reserved_tasks.append({
                        'task_id': task.get('id'),
                        'name': task.get('name'),
                        'args': str(task.get('args', [])),
                        'kwargs': str(task.get('kwargs', {})),
                        'worker': worker,
                        'status': 'RESERVED',
                    })

        # Revoked задачи
        revoked_tasks = []
        revoked_raw = inspect.revoked()
        if revoked_raw:
            for worker, task_ids in revoked_raw.items():
                for task_id in task_ids:
                    revoked_tasks.append({
                        'task_id': task_id,
                        'name': 'Unknown',
                        'worker': worker,
                        'status': 'REVOKED',
                    })

        # Получаем информацию о задачах из БД (связанные с бронированиями)
        def _get_booking_tasks(session):
            bookings = session.query(Booking).filter(
                (Booking.expiration_task_id.isnot(None)) |
                (Booking.reminder_task_id.isnot(None))
            ).all()

            booking_tasks_info = []
            for booking in bookings:
                if booking.expiration_task_id:
                    booking_tasks_info.append({
                        'task_id': booking.expiration_task_id,
                        'booking_id': booking.id,
                        'task_type': 'expiration_notification',
                        'user_id': booking.user_id,
                        'visit_date': booking.visit_date.isoformat() if booking.visit_date else None,
                    })

                if booking.reminder_task_id:
                    booking_tasks_info.append({
                        'task_id': booking.reminder_task_id,
                        'booking_id': booking.id,
                        'task_type': 'rental_reminder',
                        'user_id': booking.user_id,
                        'visit_date': booking.visit_date.isoformat() if booking.visit_date else None,
                    })

            return booking_tasks_info

        booking_tasks = DatabaseManager.safe_execute(_get_booking_tasks)

        # Создаем мапу task_id -> booking_info для быстрого поиска
        task_to_booking = {task['task_id']: task for task in booking_tasks}

        # Обогащаем задачи информацией о бронированиях
        def enrich_task(task):
            task_id = task.get('task_id')
            if task_id and task_id in task_to_booking:
                booking_info = task_to_booking[task_id]
                task['booking_id'] = booking_info['booking_id']
                task['booking_task_type'] = booking_info['task_type']
                task['booking_user_id'] = booking_info['user_id']
                task['booking_visit_date'] = booking_info['visit_date']
            return task

        # Обогащаем все задачи
        active_tasks = [enrich_task(task) for task in active_tasks]
        scheduled_tasks = [enrich_task(task) for task in scheduled_tasks]
        reserved_tasks = [enrich_task(task) for task in reserved_tasks]
        revoked_tasks = [enrich_task(task) for task in revoked_tasks]

        # Применяем фильтр, если указан
        # Total считается без отмененных задач (только активные + запланированные + зарезервированные)
        result = {
            'active': active_tasks,
            'scheduled': scheduled_tasks,
            'reserved': reserved_tasks,
            'revoked': revoked_tasks,
            'total': len(active_tasks) + len(scheduled_tasks) + len(reserved_tasks),
            'timestamp': datetime.now(MOSCOW_TZ).isoformat(),
        }

        if status_filter and status_filter != 'all':
            filter_map = {
                'active': 'active',
                'scheduled': 'scheduled',
                'reserved': 'reserved',
                'revoked': 'revoked',
            }

            if status_filter in filter_map:
                key = filter_map[status_filter]
                result = {
                    key: result[key],
                    'total': len(result[key]),
                    'timestamp': result['timestamp'],
                }

        logger.info(f"Возвращено {result['total']} задач")
        return result

    except Exception as e:
        logger.error(f"Ошибка получения списка Celery задач: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить список задач: {str(e)}"
        )


@router.get("/stats")
async def get_celery_stats(
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить статистику Celery workers (только для Суперадмина).
    """
    try:
        logger.info(f"Получение статистики Celery администратором {current_admin.login}")

        inspect = celery_app.control.inspect()

        # Информация о workers
        stats = inspect.stats()
        active_queues = inspect.active_queues()
        registered_tasks = inspect.registered()

        workers_info = []
        if stats:
            for worker_name, worker_stats in stats.items():
                worker_info = {
                    'name': worker_name,
                    'status': 'online',
                    'pool': worker_stats.get('pool', {}).get('implementation'),
                    'max_concurrency': worker_stats.get('pool', {}).get('max-concurrency'),
                    'processes': worker_stats.get('pool', {}).get('processes', []),
                }

                # Добавляем информацию об очередях
                if active_queues and worker_name in active_queues:
                    worker_info['queues'] = [q['name'] for q in active_queues[worker_name]]

                # Добавляем зарегистрированные задачи
                if registered_tasks and worker_name in registered_tasks:
                    worker_info['registered_tasks'] = registered_tasks[worker_name]

                workers_info.append(worker_info)

        return {
            'workers': workers_info,
            'total_workers': len(workers_info),
            'timestamp': datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики Celery: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить статистику: {str(e)}"
        )


@router.post("/revoke/{task_id}")
async def revoke_task_endpoint(
    task_id: str,
    terminate: bool = False,
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Отменить задачу Celery по ID (только для Суперадмина).

    Args:
        task_id: ID задачи Celery
        terminate: Принудительно завершить задачу если она уже выполняется
    """
    try:
        from utils.task_manager import revoke_task

        logger.info(
            f"Администратор {current_admin.login} отменяет задачу {task_id} "
            f"(terminate={terminate})"
        )

        # Используем нашу утилиту для отмены
        result = revoke_task(task_id, task_type="manual_revoke")

        # Если нужно принудительно завершить
        if terminate and result['status'] in ['revoked', 'not_found']:
            celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
            logger.warning(f"Задача {task_id} принудительно завершена (terminate=True)")
            result['terminated'] = True

        # Обновляем БД: очищаем task_id в таблице bookings
        def _clear_task_id_in_booking(session):
            # Ищем бронирование с этим task_id
            booking = session.query(Booking).filter(
                (Booking.expiration_task_id == task_id) |
                (Booking.reminder_task_id == task_id)
            ).first()

            if booking:
                # Очищаем соответствующее поле
                if booking.expiration_task_id == task_id:
                    booking.expiration_task_id = None
                    logger.info(f"Cleared expiration_task_id for booking #{booking.id}")
                if booking.reminder_task_id == task_id:
                    booking.reminder_task_id = None
                    logger.info(f"Cleared reminder_task_id for booking #{booking.id}")

                session.commit()
                return booking.id
            return None

        try:
            booking_id = DatabaseManager.safe_execute(_clear_task_id_in_booking)
            if booking_id:
                logger.info(f"Cleared task_id from booking #{booking_id}")
        except Exception as e:
            logger.error(f"Failed to clear task_id from booking: {e}", exc_info=True)

        return {
            'success': result['revoked'],
            'task_id': task_id,
            'status': result['status'],
            'message': result['message'],
            'terminated': result.get('terminated', False),
        }

    except Exception as e:
        logger.error(f"Ошибка отмены задачи {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось отменить задачу: {str(e)}"
        )


@router.get("/task/{task_id}")
async def get_task_info(
    task_id: str,
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить детальную информацию о задаче Celery (только для Суперадмина).
    """
    try:
        from utils.task_manager import check_task_status

        logger.info(f"Получение информации о задаче {task_id} администратором {current_admin.login}")

        # Получаем статус задачи
        task_status = check_task_status(task_id)

        # Проверяем, связана ли задача с бронированием
        def _get_booking_for_task(session):
            # Делаем join с User и Tariff для получения полной информации
            result = session.query(Booking, User, Tariff).join(
                User, Booking.user_id == User.id
            ).join(
                Tariff, Booking.tariff_id == Tariff.id
            ).filter(
                (Booking.expiration_task_id == task_id) |
                (Booking.reminder_task_id == task_id)
            ).first()

            if result:
                booking, user, tariff = result
                task_type = 'expiration_notification' if booking.expiration_task_id == task_id else 'rental_reminder'

                return {
                    'booking_id': booking.id,
                    'task_type': task_type,
                    'user_id': booking.user_id,
                    'user_name': user.full_name or 'Не указано',
                    'user_telegram_username': user.username,
                    'tariff_name': tariff.name,
                    'tariff_purpose': tariff.purpose,
                    'visit_date': booking.visit_date.isoformat() if booking.visit_date else None,
                    'visit_time': booking.visit_time.isoformat() if booking.visit_time else None,
                    'duration': booking.duration,
                    'confirmed': booking.confirmed,
                    'paid': booking.paid,
                }
            return None

        booking_info = DatabaseManager.safe_execute(_get_booking_for_task)

        result = {
            'task_id': task_id,
            'exists': task_status['exists'],
            'state': task_status['state'],
            'info': task_status['info'],
            'booking': booking_info,
            'timestamp': datetime.now(MOSCOW_TZ).isoformat(),
        }

        return result

    except Exception as e:
        logger.error(f"Ошибка получения информации о задаче {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось получить информацию о задаче: {str(e)}"
        )


@router.post("/revoke-all")
async def revoke_all_tasks(
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Отменить ВСЕ активные и запланированные задачи Celery (только для Суперадмина).

    Отменяет все задачи в статусах: active, scheduled, reserved.
    Также очищает task_id в таблице bookings для всех затронутых бронирований.
    """
    try:
        logger.warning(
            f"Администратор {current_admin.login} инициировал массовую отмену ВСЕХ Celery задач"
        )

        inspect = celery_app.control.inspect()

        # Собираем все task IDs из разных статусов
        all_task_ids = []

        # Активные задачи
        active_raw = inspect.active()
        if active_raw:
            for worker, tasks in active_raw.items():
                for task in tasks:
                    all_task_ids.append(task.get('id'))

        # Запланированные задачи
        scheduled_raw = inspect.scheduled()
        if scheduled_raw:
            for worker, tasks in scheduled_raw.items():
                for task in tasks:
                    request = task.get('request', {})
                    task_id = request.get('id')
                    if task_id:
                        all_task_ids.append(task_id)

        # Зарезервированные задачи
        reserved_raw = inspect.reserved()
        if reserved_raw:
            for worker, tasks in reserved_raw.items():
                for task in tasks:
                    all_task_ids.append(task.get('id'))

        # Удаляем дубликаты
        all_task_ids = list(set(filter(None, all_task_ids)))

        logger.info(f"Найдено {len(all_task_ids)} задач для отмены")

        # Отменяем все задачи
        revoked_count = 0
        for task_id in all_task_ids:
            try:
                celery_app.control.revoke(task_id, terminate=False)
                revoked_count += 1
            except Exception as e:
                logger.error(f"Failed to revoke task {task_id}: {e}")

        logger.info(f"Отменено {revoked_count} задач через Celery")

        # Очищаем все task_id в таблице bookings
        def _clear_all_task_ids(session):
            bookings = session.query(Booking).filter(
                (Booking.expiration_task_id.isnot(None)) |
                (Booking.reminder_task_id.isnot(None))
            ).all()

            cleared_count = 0
            for booking in bookings:
                if booking.expiration_task_id or booking.reminder_task_id:
                    booking.expiration_task_id = None
                    booking.reminder_task_id = None
                    cleared_count += 1

            session.commit()
            return cleared_count

        cleared_bookings = DatabaseManager.safe_execute(_clear_all_task_ids)
        logger.info(f"Очищены task_ids у {cleared_bookings} бронирований")

        # Отправляем Telegram уведомление администратору
        try:
            from utils.bot_instance import send_admin_notification
            await send_admin_notification(
                f"🔴 МАССОВАЯ ОТМЕНА ВСЕХ ЗАДАЧ\n\n"
                f"Администратор: {current_admin.login}\n"
                f"Отменено задач: {revoked_count}\n"
                f"Очищено бронирований: {cleared_bookings}"
            )
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

        return {
            'success': True,
            'total_tasks_found': len(all_task_ids),
            'tasks_revoked': revoked_count,
            'bookings_cleared': cleared_bookings,
            'timestamp': datetime.now(MOSCOW_TZ).isoformat(),
        }

    except Exception as e:
        logger.error(f"Ошибка массовой отмены задач: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось отменить все задачи: {str(e)}"
        )
