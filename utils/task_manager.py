"""
Utility for managing Celery tasks (revoke, check status, etc.)
"""
from typing import Optional, List, Dict, Any
from celery.result import AsyncResult
from celery_app import celery_app
from utils.logger import get_logger

logger = get_logger(__name__)


def revoke_task(task_id: Optional[str], task_type: str = "notification") -> Dict[str, Any]:
    """
    Revoke a Celery task by its ID.

    Args:
        task_id: Celery task ID to revoke
        task_type: Type of task for logging (e.g., "notification", "reminder")

    Returns:
        Dict with status: {
            'revoked': bool,
            'task_id': str,
            'status': str,  # 'not_found', 'already_executed', 'revoked', 'error'
            'message': str
        }
    """
    if not task_id:
        return {
            'revoked': False,
            'task_id': None,
            'status': 'not_found',
            'message': 'Task ID is None or empty'
        }

    try:
        # Get task result object
        task_result = AsyncResult(task_id, app=celery_app)

        # Check current task status
        task_status = task_result.state

        # Task already executed or doesn't exist
        if task_status in ['SUCCESS', 'FAILURE']:
            logger.info(
                f"Task {task_id} ({task_type}) already executed with status {task_status}, "
                f"cannot revoke"
            )
            return {
                'revoked': False,
                'task_id': task_id,
                'status': 'already_executed',
                'message': f'Task already {task_status.lower()}'
            }

        # Revoke the task
        # terminate=False means task won't be killed if already running (default, safer)
        # signal='SIGTERM' can be used for terminate=True if needed
        celery_app.control.revoke(task_id, terminate=False)

        logger.info(f"Successfully revoked {task_type} task {task_id} (status: {task_status})")

        return {
            'revoked': True,
            'task_id': task_id,
            'status': 'revoked',
            'message': f'Task revoked (was {task_status})'
        }

    except Exception as e:
        logger.error(f"Error revoking task {task_id} ({task_type}): {e}", exc_info=True)
        return {
            'revoked': False,
            'task_id': task_id,
            'status': 'error',
            'message': f'Error: {str(e)}'
        }


def revoke_booking_tasks(
    expiration_task_id: Optional[str],
    reminder_task_id: Optional[str],
    booking_id: int
) -> Dict[str, Any]:
    """
    Revoke all Celery tasks associated with a booking.

    Args:
        expiration_task_id: Task ID for expiration notification
        reminder_task_id: Task ID for rental reminder
        booking_id: Booking ID for logging

    Returns:
        Dict with results: {
            'booking_id': int,
            'expiration_task': Dict,
            'reminder_task': Dict,
            'total_revoked': int
        }
    """
    logger.info(
        f"Revoking tasks for booking #{booking_id}: "
        f"expiration={expiration_task_id}, reminder={reminder_task_id}"
    )

    results = {
        'booking_id': booking_id,
        'expiration_task': {'revoked': False, 'status': 'not_found'},
        'reminder_task': {'revoked': False, 'status': 'not_found'},
        'total_revoked': 0
    }

    # Revoke expiration notification task
    if expiration_task_id:
        results['expiration_task'] = revoke_task(expiration_task_id, "expiration notification")
        if results['expiration_task']['revoked']:
            results['total_revoked'] += 1

    # Revoke rental reminder task
    if reminder_task_id:
        results['reminder_task'] = revoke_task(reminder_task_id, "rental reminder")
        if results['reminder_task']['revoked']:
            results['total_revoked'] += 1

    logger.info(
        f"Revoked {results['total_revoked']} tasks for booking #{booking_id}"
    )

    return results


def bulk_revoke_booking_tasks(bookings_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Revoke tasks for multiple bookings.

    Args:
        bookings_data: List of dicts with keys: id, expiration_task_id, reminder_task_id

    Returns:
        Dict with summary: {
            'total_bookings': int,
            'total_tasks_revoked': int,
            'results': List[Dict]
        }
    """
    logger.info(f"Bulk revoking tasks for {len(bookings_data)} bookings")

    summary = {
        'total_bookings': len(bookings_data),
        'total_tasks_revoked': 0,
        'results': []
    }

    for booking_data in bookings_data:
        result = revoke_booking_tasks(
            expiration_task_id=booking_data.get('expiration_task_id'),
            reminder_task_id=booking_data.get('reminder_task_id'),
            booking_id=booking_data['id']
        )
        summary['total_tasks_revoked'] += result['total_revoked']
        summary['results'].append(result)

    logger.info(
        f"Bulk revoke complete: {summary['total_tasks_revoked']} tasks revoked "
        f"for {summary['total_bookings']} bookings"
    )

    return summary


def check_task_status(task_id: Optional[str]) -> Dict[str, Any]:
    """
    Check status of a Celery task.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with status info: {
            'task_id': str,
            'exists': bool,
            'state': str,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
            'info': Any    # Additional task info
        }
    """
    if not task_id:
        return {
            'task_id': None,
            'exists': False,
            'state': 'UNKNOWN',
            'info': None
        }

    try:
        task_result = AsyncResult(task_id, app=celery_app)
        return {
            'task_id': task_id,
            'exists': True,
            'state': task_result.state,
            'info': task_result.info
        }
    except Exception as e:
        logger.error(f"Error checking task {task_id} status: {e}")
        return {
            'task_id': task_id,
            'exists': False,
            'state': 'ERROR',
            'info': str(e)
        }
