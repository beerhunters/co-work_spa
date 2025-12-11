#!/usr/bin/env python3
"""
Миграция таблицы bookings: добавление поля для комментариев.

Добавляемые поля:
- comment: TEXT - Комментарий к бронированию (например, "Без оплаты")
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from models.models import DatabaseManager, engine
from utils.logger import get_logger

logger = get_logger(__name__)


def migrate_bookings_table():
    """Добавить поле comment в таблицу bookings."""

    def _check_and_add_column(session):
        # Получить информацию о таблице
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('bookings')]

        logger.info(f"Existing columns in bookings table: {columns}")

        # Если поле уже существует, пропустить
        if 'comment' in columns:
            logger.info("Column 'comment' already exists")
            logger.info("Migration skipped")
            return

        logger.info("Adding 'comment' column to bookings table...")

        try:
            # Выполнить миграцию
            session.execute(text("""
                ALTER TABLE bookings ADD COLUMN comment TEXT DEFAULT NULL;
            """))
            logger.info("✓ Added column 'comment'")

            session.commit()
            logger.info("✅ Migration completed successfully")

            # Проверка после миграции
            inspector = inspect(engine)
            new_columns = [col['name'] for col in inspector.get_columns('bookings')]
            logger.info(f"Columns after migration: {new_columns}")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise

    try:
        DatabaseManager.safe_execute(_check_and_add_column)
    except Exception as e:
        logger.error(f"Error executing migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting bookings table migration")
    logger.info("=" * 60)

    try:
        migrate_bookings_table()
        logger.info("=" * 60)
        logger.info("Migration process completed")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Critical error: {e}")
        sys.exit(1)
