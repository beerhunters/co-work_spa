#!/usr/bin/env python3
"""
Миграция таблицы offices: добавление полей для длительности аренды.

Добавляемые поля:
- duration_months: INTEGER - Длительность аренды в месяцах
- rental_start_date: DATETIME - Дата начала аренды
- rental_end_date: DATETIME - Дата окончания аренды (вычисляется автоматически)
"""
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from models.models import DatabaseManager, engine
from utils.logger import get_logger

logger = get_logger(__name__)


def migrate_offices_table():
    """Добавить новые поля в таблицу offices."""

    def _check_and_add_columns(session):
        # Получить информацию о таблице
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('offices')]

        logger.info(f"Existing columns in offices table: {columns}")

        # Если поля уже существуют, пропустить
        if 'duration_months' in columns:
            logger.info("Columns 'duration_months', 'rental_start_date', 'rental_end_date' already exist")
            logger.info("Migration skipped")
            return

        logger.info("Adding new columns to offices table...")

        try:
            # Выполнить миграцию
            session.execute(text("""
                ALTER TABLE offices ADD COLUMN duration_months INTEGER;
            """))
            logger.info("✓ Added column 'duration_months'")

            session.execute(text("""
                ALTER TABLE offices ADD COLUMN rental_start_date DATETIME;
            """))
            logger.info("✓ Added column 'rental_start_date'")

            session.execute(text("""
                ALTER TABLE offices ADD COLUMN rental_end_date DATETIME;
            """))
            logger.info("✓ Added column 'rental_end_date'")

            session.commit()
            logger.info("✅ Migration completed successfully")

            # Проверка после миграции
            inspector = inspect(engine)
            new_columns = [col['name'] for col in inspector.get_columns('offices')]
            logger.info(f"Columns after migration: {new_columns}")

        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise

    try:
        DatabaseManager.safe_execute(_check_and_add_columns)
    except Exception as e:
        logger.error(f"Error executing migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting offices table migration")
    logger.info("=" * 60)

    try:
        migrate_offices_table()
        logger.info("=" * 60)
        logger.info("Migration process completed")
        logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n❌ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Critical error: {e}")
        sys.exit(1)
