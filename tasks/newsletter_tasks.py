"""
Celery tasks for newsletter distribution.
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import aiofiles
from celery import Task
from aiogram.types import BufferedInputFile, InputMediaPhoto

from celery_app import celery_app
from config import MOSCOW_TZ
from models.models import Newsletter, DatabaseManager
from utils.logger import get_logger
from dependencies import get_bot

logger = get_logger(__name__)


class CallbackTask(Task):
    """Base task with callbacks for progress tracking."""

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(f"Task {task_id} retrying: {exc}")


@celery_app.task(
    bind=True,
    base=CallbackTask,
    name='tasks.newsletter_tasks.send_newsletter_task',
    max_retries=3,
    default_retry_delay=60
)
def send_newsletter_task(
    self,
    message: str,
    recipients: List[Dict[str, any]],
    photo_paths: List[str],
    newsletter_data: Dict[str, any]
):
    """
    Celery task for sending newsletter to recipients.

    Args:
        message: Newsletter message text
        recipients: List of recipient dicts with telegram_id and full_name
        photo_paths: List of paths to photos
        newsletter_data: Dict with newsletter metadata (recipient_type, segment_type, etc.)

    Returns:
        Dict with results: {
            'success_count': int,
            'failed_count': int,
            'newsletter_id': int,
            'status': str
        }
    """
    try:
        # Update task state to show progress
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': len(recipients),
                'status': 'Starting newsletter distribution...'
            }
        )

        # Run async send function
        result = asyncio.run(
            _send_newsletter_async(
                self,
                message,
                recipients,
                photo_paths,
                newsletter_data
            )
        )

        return result

    except Exception as e:
        logger.error(f"Error in send_newsletter_task: {e}", exc_info=True)

        # Clean up photos on error
        asyncio.run(_cleanup_photos(photo_paths))

        raise self.retry(exc=e)


async def _send_newsletter_async(
    task: Task,
    message: str,
    recipients: List[Dict[str, any]],
    photo_paths: List[str],
    newsletter_data: Dict[str, any]
) -> Dict[str, any]:
    """
    Async function to send newsletter to all recipients.
    """
    bot = get_bot()
    if not bot:
        raise RuntimeError("Bot not available")

    success_count = 0
    failed_count = 0
    total = len(recipients)

    # Список для хранения деталей отправки каждому получателю
    recipient_details = []

    for idx, recipient in enumerate(recipients, 1):
        telegram_id = recipient['telegram_id']
        full_name = recipient.get('full_name', 'Unknown')
        user_id = recipient.get('user_id')

        send_status = 'success'
        error_message = None

        try:
            # Send newsletter based on photo count
            if photo_paths:
                if len(photo_paths) == 1:
                    # Single photo
                    async with aiofiles.open(photo_paths[0], 'rb') as photo_file:
                        photo_content = await photo_file.read()

                    photo_file_obj = BufferedInputFile(
                        photo_content,
                        filename=Path(photo_paths[0]).name
                    )

                    await bot.send_photo(
                        chat_id=telegram_id,
                        photo=photo_file_obj,
                        caption=message,
                        parse_mode='HTML'
                    )
                else:
                    # Multiple photos - send as media group
                    media_group = []
                    for photo_idx, photo_path in enumerate(photo_paths):
                        async with aiofiles.open(photo_path, 'rb') as photo_file:
                            photo_content = await photo_file.read()

                        media = InputMediaPhoto(
                            media=BufferedInputFile(
                                photo_content,
                                filename=f"photo_{photo_idx}.jpg"
                            ),
                            caption=message if photo_idx == 0 else None,
                            parse_mode='HTML' if photo_idx == 0 else None
                        )
                        media_group.append(media)

                    await bot.send_media_group(
                        chat_id=telegram_id,
                        media=media_group
                    )
            else:
                # Text only
                await bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode='HTML'
                )

            success_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)

        except Exception as e:
            failed_count += 1
            send_status = 'failed'
            error_message = str(e)
            logger.error(f"Failed to send to {telegram_id}: {e}")

        # Сохраняем детали отправки для этого получателя
        recipient_details.append({
            'user_id': user_id,
            'telegram_id': telegram_id,
            'full_name': full_name,
            'status': send_status,
            'error_message': error_message,
        })

        # Update task progress
        task.update_state(
            state='PROGRESS',
            meta={
                'current': idx,
                'total': total,
                'success': success_count,
                'failed': failed_count,
                'status': f'Sent {idx}/{total} messages...'
            }
        )

    # Determine status
    if success_count == total:
        status = 'success'
    elif success_count == 0:
        status = 'failed'
    else:
        status = 'partial'

    # Save to database
    newsletter_id = _save_newsletter_to_db(
        message=message,
        recipients=recipients,
        recipient_details=recipient_details,
        photo_count=len(photo_paths),
        success_count=success_count,
        failed_count=failed_count,
        status=status,
        **newsletter_data
    )

    # Clean up photos
    await _cleanup_photos(photo_paths)

    logger.info(f"Newsletter {newsletter_id} sent: {success_count}/{total} delivered")

    return {
        'success_count': success_count,
        'failed_count': failed_count,
        'total_count': total,
        'newsletter_id': newsletter_id,
        'status': status
    }


def _save_newsletter_to_db(
    message: str,
    recipients: List[Dict[str, any]],
    recipient_details: List[Dict[str, any]],
    photo_count: int,
    success_count: int,
    failed_count: int,
    status: str,
    recipient_type: str,
    segment_type: Optional[str] = None,
    segment_params: Optional[str] = None
) -> int:
    """
    Save newsletter to database along with recipient details.
    Returns newsletter ID.
    """
    from models.models import Newsletter, NewsletterRecipient

    def _save(session):
        # Создаем запись Newsletter
        newsletter = Newsletter(
            message=message,
            recipient_type=recipient_type,
            recipient_ids=','.join([str(r['telegram_id']) for r in recipients]),
            total_count=len(recipients),
            success_count=success_count,
            failed_count=failed_count,
            photo_count=photo_count,
            status=status,
            segment_type=segment_type,
            segment_params=segment_params,
            created_at=datetime.now(MOSCOW_TZ)
        )
        session.add(newsletter)
        session.flush()  # Получаем newsletter.id

        # Создаем записи NewsletterRecipient для каждого получателя
        for detail in recipient_details:
            recipient_record = NewsletterRecipient(
                newsletter_id=newsletter.id,
                user_id=detail.get('user_id'),
                telegram_id=detail['telegram_id'],
                full_name=detail.get('full_name'),
                status=detail['status'],
                error_message=detail.get('error_message'),
                sent_at=datetime.now(MOSCOW_TZ)
            )
            session.add(recipient_record)

        session.commit()
        return newsletter.id

    try:
        return DatabaseManager.safe_execute(_save)
    except Exception as e:
        logger.error(f"Failed to save newsletter to DB: {e}")
        return -1


async def _cleanup_photos(photo_paths: List[str]):
    """Remove temporary photo files."""
    for photo_path in photo_paths:
        try:
            path = Path(photo_path)
            if path.exists():
                path.unlink()
                logger.debug(f"Cleaned up photo: {photo_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup photo {photo_path}: {e}")
