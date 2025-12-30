"""
API endpoints для управления запланированными задачами.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime

from models.models import DatabaseManager, ScheduledTask, TaskStatus, TaskType, MOSCOW_TZ
from schemas.scheduled_task_schemas import (
    ScheduledTaskResponse,
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    ScheduledTaskStats
)
from dependencies import require_super_admin, CachedAdmin
from utils.logger import get_logger
from celery.result import AsyncResult
from celery_app import celery_app

router = APIRouter(prefix="/scheduled-tasks", tags=["Scheduled Tasks"])
logger = get_logger(__name__)


@router.get("/", response_model=List[ScheduledTaskResponse])
async def get_all_tasks(
    task_type: Optional[str] = Query(None, description="Фильтр по типу задачи"),
    status_filter: Optional[str] = Query(None, alias="status", description="Фильтр по статусу"),
    office_id: Optional[int] = Query(None, description="Фильтр по офису"),
    booking_id: Optional[int] = Query(None, description="Фильтр по бронированию"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить список всех запланированных задач с фильтрацией.
    """
    def _get_tasks(session: Session):
        query = session.query(ScheduledTask).order_by(ScheduledTask.scheduled_datetime.desc())

        # Применяем фильтры
        if task_type:
            query = query.filter(ScheduledTask.task_type == TaskType(task_type))

        if status_filter:
            query = query.filter(ScheduledTask.status == TaskStatus(status_filter))

        if office_id:
            query = query.filter(ScheduledTask.office_id == office_id)

        if booking_id:
            query = query.filter(ScheduledTask.booking_id == booking_id)

        total = query.count()
        tasks = query.offset(offset).limit(limit).all()

        # Добавляем вычисляемые поля
        now = datetime.now(MOSCOW_TZ)
        result = []
        for task in tasks:
            task_dict = {
                "id": task.id,
                "task_type": task.task_type.value,
                "celery_task_id": task.celery_task_id,
                "office_id": task.office_id,
                "booking_id": task.booking_id,
                "scheduled_datetime": task.scheduled_datetime,
                "created_at": task.created_at,
                "created_by": task.created_by,
                "status": task.status.value,
                "executed_at": task.executed_at,
                "result": task.result,
                "error_message": task.error_message,
                "params": task.params,
                "retry_count": task.retry_count,
                "is_overdue": task.is_overdue,
                "time_until_execution_seconds": int(task.time_until_execution.total_seconds()) if task.status == TaskStatus.PENDING else None
            }
            result.append(task_dict)

        return result

    try:
        tasks = DatabaseManager.safe_execute(_get_tasks)
        return tasks
    except Exception as e:
        logger.error(f"Error fetching scheduled tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения задач"
        )


@router.get("/stats", response_model=ScheduledTaskStats)
async def get_task_stats(
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить статистику по задачам.
    """
    def _get_stats(session: Session):
        now = datetime.now(MOSCOW_TZ)

        total = session.query(ScheduledTask).count()
        pending = session.query(ScheduledTask).filter(ScheduledTask.status == TaskStatus.PENDING).count()
        running = session.query(ScheduledTask).filter(ScheduledTask.status == TaskStatus.RUNNING).count()
        completed = session.query(ScheduledTask).filter(ScheduledTask.status == TaskStatus.COMPLETED).count()
        failed = session.query(ScheduledTask).filter(ScheduledTask.status == TaskStatus.FAILED).count()
        cancelled = session.query(ScheduledTask).filter(ScheduledTask.status == TaskStatus.CANCELLED).count()

        # Просроченные (pending но время прошло)
        overdue = session.query(ScheduledTask).filter(
            and_(
                ScheduledTask.status == TaskStatus.PENDING,
                ScheduledTask.scheduled_datetime < now
            )
        ).count()

        # По типам
        office_reminders = session.query(ScheduledTask).filter(
            or_(
                ScheduledTask.task_type == TaskType.OFFICE_REMINDER_ADMIN,
                ScheduledTask.task_type == TaskType.OFFICE_REMINDER_TENANT
            )
        ).count()

        booking_tasks = session.query(ScheduledTask).filter(
            or_(
                ScheduledTask.task_type == TaskType.BOOKING_EXPIRATION,
                ScheduledTask.task_type == TaskType.BOOKING_RENTAL_REMINDER
            )
        ).count()

        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "overdue": overdue,
            "office_reminders": office_reminders,
            "booking_tasks": booking_tasks
        }

    try:
        stats = DatabaseManager.safe_execute(_get_stats)
        return stats
    except Exception as e:
        logger.error(f"Error fetching task stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения статистики"
        )


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_task(
    task_id: int,
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Получить детали конкретной задачи.
    """
    def _get_task(session: Session):
        task = session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise ValueError("Задача не найдена")

        return {
            "id": task.id,
            "task_type": task.task_type.value,
            "celery_task_id": task.celery_task_id,
            "office_id": task.office_id,
            "booking_id": task.booking_id,
            "scheduled_datetime": task.scheduled_datetime,
            "created_at": task.created_at,
            "created_by": task.created_by,
            "status": task.status.value,
            "executed_at": task.executed_at,
            "result": task.result,
            "error_message": task.error_message,
            "params": task.params,
            "retry_count": task.retry_count,
            "is_overdue": task.is_overdue,
            "time_until_execution_seconds": int(task.time_until_execution.total_seconds()) if task.status == TaskStatus.PENDING else None
        }

    try:
        task = DatabaseManager.safe_execute(_get_task)
        return task
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка получения задачи"
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Удалить задачу (отменить в Celery и удалить из БД).
    """
    def _delete_task(session: Session):
        task = session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise ValueError("Задача не найдена")

        # Отменяем в Celery если задача еще pending
        if task.celery_task_id and task.status == TaskStatus.PENDING:
            try:
                result = AsyncResult(task.celery_task_id, app=celery_app)
                result.revoke(terminate=True)
                logger.info(f"Revoked Celery task {task.celery_task_id}")
            except Exception as e:
                logger.error(f"Error revoking Celery task: {e}")

        session.delete(task)
        session.commit()
        logger.info(f"Admin {current_admin.login} deleted scheduled task {task_id}")
        return True

    try:
        DatabaseManager.safe_execute(_delete_task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка удаления задачи"
        )


@router.post("/{task_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_task(
    task_id: int,
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Отменить выполнение задачи (не удалять из БД, а изменить статус на cancelled).
    """
    def _cancel_task(session: Session):
        task = session.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            raise ValueError("Задача не найдена")

        if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise ValueError("Можно отменить только задачи в статусе pending или running")

        # Отменяем в Celery
        if task.celery_task_id:
            try:
                result = AsyncResult(task.celery_task_id, app=celery_app)
                result.revoke(terminate=True)
                logger.info(f"Revoked Celery task {task.celery_task_id}")
            except Exception as e:
                logger.error(f"Error revoking Celery task: {e}")

        task.status = TaskStatus.CANCELLED
        task.executed_at = datetime.now(MOSCOW_TZ)
        session.commit()
        logger.info(f"Admin {current_admin.login} cancelled task {task_id}")
        return {"status": "cancelled"}

    try:
        result = DatabaseManager.safe_execute(_cancel_task)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка отмены задачи"
        )


@router.post("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_old_tasks(
    days: int = Query(30, ge=1, le=365, description="Удалить задачи старше N дней"),
    current_admin: CachedAdmin = Depends(require_super_admin)
):
    """
    Очистить старые выполненные/отмененные задачи.
    """
    def _cleanup(session: Session):
        from datetime import timedelta
        cutoff_date = datetime.now(MOSCOW_TZ) - timedelta(days=days)

        deleted_count = session.query(ScheduledTask).filter(
            and_(
                or_(
                    ScheduledTask.status == TaskStatus.COMPLETED,
                    ScheduledTask.status == TaskStatus.CANCELLED
                ),
                ScheduledTask.created_at < cutoff_date
            )
        ).delete()

        session.commit()
        logger.info(f"Admin {current_admin.login} cleaned up {deleted_count} old tasks (older than {days} days)")
        return {"deleted_count": deleted_count}

    try:
        result = DatabaseManager.safe_execute(_cleanup)
        return result
    except Exception as e:
        logger.error(f"Error cleaning up old tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка очистки задач"
        )
