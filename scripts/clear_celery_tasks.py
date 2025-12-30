"""
Скрипт для очистки всех запланированных Celery задач.
"""
import sys
sys.path.insert(0, '/app')

from celery_app import celery_app
from celery.result import AsyncResult
from utils.logger import get_logger

logger = get_logger(__name__)

def clear_all_scheduled_tasks():
    """Отменяет все запланированные задачи."""
    inspect = celery_app.control.inspect()
    scheduled = inspect.scheduled()

    if not scheduled:
        print("Нет запланированных задач")
        return

    total_revoked = 0

    for worker, tasks in scheduled.items():
        print(f"\nWorker: {worker}")
        print(f"Всего задач: {len(tasks)}")

        for task_info in tasks:
            task_id = task_info['request']['id']
            task_name = task_info['request']['name']
            task_args = task_info['request']['args']

            print(f"  - Отмена задачи {task_id}: {task_name}{task_args}")

            # Отменяем задачу
            try:
                result = AsyncResult(task_id, app=celery_app)
                result.revoke(terminate=True)
                total_revoked += 1
                print(f"    ✓ Отменена")
            except Exception as e:
                print(f"    ✗ Ошибка: {e}")

    print(f"\n✅ Всего отменено: {total_revoked} задач")

if __name__ == '__main__':
    clear_all_scheduled_tasks()
