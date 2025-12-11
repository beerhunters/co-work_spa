#!/usr/bin/env python3
"""
Миграция таблицы offices: добавление полей для типов напоминаний.

Добавляемые поля:
- admin_reminder_type: TEXT - Тип напоминания администратору (days_before/specific_datetime)
- admin_reminder_datetime: DATETIME - Конкретная дата/время напоминания администратору
- tenant_reminder_type: TEXT - Тип напоминания арендатору (days_before/specific_datetime)
- tenant_reminder_datetime: DATETIME - Конкретная дата/время напоминания арендатору
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
    """Добавить поля типов напоминаний в таблицу offices."""

    def _check_and_add_columns(session):
        # Получить информацию о таблице
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('offices')]

        logger.info(f"Existing columns in offices table: {columns}")

        # Проверка существующих полей
        fields_to_add = []
        if 'admin_reminder_type' not in columns:
            fields_to_add.append('admin_reminder_type')
        if 'admin_reminder_datetime' not in columns:
            fields_to_add.append('admin_reminder_datetime')
        if 'tenant_reminder_type' not in columns:
            fields_to_add.append('tenant_reminder_type')
        if 'tenant_reminder_datetime' not in columns:
            fields_to_add.append('tenant_reminder_datetime')

        if not fields_to_add:
            logger.info("All reminder type columns already exist")
            logger.info("Migration skipped")
            return

        logger.info(f"Adding columns: {fields_to_add}")

        try:
            # Добавление полей
            if 'admin_reminder_type' in fields_to_add:
                session.execute(text("""
                    ALTER TABLE offices ADD COLUMN admin_reminder_type TEXT DEFAULT 'days_before' NOT NULL;
                """))
                logger.info("✓ Added column 'admin_reminder_type'")

            if 'admin_reminder_datetime' in fields_to_add:
                session.execute(text("""
                    ALTER TABLE offices ADD COLUMN admin_reminder_datetime DATETIME DEFAULT NULL;
                """))
                logger.info("✓ Added column 'admin_reminder_datetime'")

            if 'tenant_reminder_type' in fields_to_add:
                session.execute(text("""
                    ALTER TABLE offices ADD COLUMN tenant_reminder_type TEXT DEFAULT 'days_before' NOT NULL;
                """))
                logger.info("✓ Added column 'tenant_reminder_type'")

            if 'tenant_reminder_datetime' in fields_to_add:
                session.execute(text("""
                    ALTER TABLE offices ADD COLUMN tenant_reminder_datetime DATETIME DEFAULT NULL;
                """))
                logger.info("✓ Added column 'tenant_reminder_datetime'")

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
    logger.info("Starting offices table migration (reminder types)")
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
