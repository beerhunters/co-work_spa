#!/usr/bin/env python3
"""
Скрипт для выполнения SQL миграций.

Использование:
    python scripts/run_migration.py migrations/add_scheduled_tasks_and_subscriptions.sql

Или запустить все миграции:
    python scripts/run_migration.py --all
"""

import sys
import os
import sqlite3
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATABASE_PATH
from utils.logger import get_logger

logger = get_logger(__name__)


def run_migration(migration_file: str) -> bool:
    """
    Выполняет SQL миграцию из файла.

    Args:
        migration_file: Путь к SQL файлу с миграцией

    Returns:
        True если миграция выполнена успешно, иначе False
    """
    migration_path = Path(migration_file)

    if not migration_path.exists():
        logger.error(f"Migration file not found: {migration_file}")
        return False

    logger.info(f"Running migration: {migration_path.name}")

    try:
        # Создаем бэкап перед миграцией
        backup_path = create_backup()
        logger.info(f"Database backup created: {backup_path}")

        # Читаем SQL из файла
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()

        # Подключаемся к базе данных
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Выполняем миграцию
        logger.info("Executing SQL script...")
        cursor.executescript(sql_script)
        conn.commit()

        # Проверяем результаты
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Current tables in database: {', '.join(tables)}")

        conn.close()

        logger.info(f"✅ Migration completed successfully: {migration_path.name}")
        return True

    except sqlite3.Error as e:
        logger.error(f"❌ Database error during migration: {e}")
        logger.error(f"You can restore from backup: {backup_path}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during migration: {e}")
        return False


def create_backup() -> str:
    """
    Создает резервную копию базы данных.

    Returns:
        Путь к файлу бэкапа
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path(__file__).parent.parent / 'data' / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / f'pre_migration_backup_{timestamp}.db'

    # Копируем базу данных
    import shutil
    shutil.copy2(DATABASE_PATH, backup_path)

    return str(backup_path)


def list_migrations() -> list:
    """
    Возвращает список доступных миграций.

    Returns:
        Список путей к файлам миграций
    """
    migrations_dir = Path(__file__).parent.parent / 'migrations'
    if not migrations_dir.exists():
        return []

    return sorted(migrations_dir.glob('*.sql'))


def run_all_migrations() -> bool:
    """
    Выполняет все доступные миграции.

    Returns:
        True если все миграции выполнены успешно
    """
    migrations = list_migrations()

    if not migrations:
        logger.warning("No migrations found in migrations/ directory")
        return True

    logger.info(f"Found {len(migrations)} migration(s) to run")

    all_success = True
    for migration_path in migrations:
        success = run_migration(str(migration_path))
        if not success:
            all_success = False
            logger.error(f"Migration failed, stopping: {migration_path.name}")
            break

    return all_success


def main():
    """Главная функция."""
    import argparse

    parser = argparse.ArgumentParser(description='Run database migrations')
    parser.add_argument('migration_file', nargs='?', help='Path to SQL migration file')
    parser.add_argument('--all', action='store_true', help='Run all migrations in migrations/ directory')
    parser.add_argument('--list', action='store_true', help='List available migrations')

    args = parser.parse_args()

    # Список миграций
    if args.list:
        migrations = list_migrations()
        if migrations:
            print("\nAvailable migrations:")
            for migration in migrations:
                print(f"  - {migration.name}")
        else:
            print("\nNo migrations found in migrations/ directory")
        return

    # Выполнение всех миграций
    if args.all:
        logger.info("="*60)
        logger.info("Running ALL migrations")
        logger.info("="*60)
        success = run_all_migrations()
        sys.exit(0 if success else 1)

    # Выполнение конкретной миграции
    if not args.migration_file:
        parser.print_help()
        sys.exit(1)

    logger.info("="*60)
    logger.info("Database Migration Script")
    logger.info("="*60)
    logger.info(f"Database: {DATABASE_PATH}")
    logger.info(f"Migration: {args.migration_file}")
    logger.info("="*60)

    # Подтверждение
    response = input("\n⚠️  This will modify the production database. Continue? [y/N]: ")
    if response.lower() != 'y':
        logger.info("Migration cancelled by user")
        sys.exit(0)

    success = run_migration(args.migration_file)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
