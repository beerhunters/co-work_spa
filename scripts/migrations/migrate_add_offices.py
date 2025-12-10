#!/usr/bin/env python3
"""
Скрипт миграции для добавления таблиц управления офисами
Применяет SQL миграцию add_offices_tables.sql
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from models.models import DatabaseManager
from utils.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)


def apply_migration():
    """Применяет SQL миграцию для создания таблиц офисов"""

    migration_file = Path(__file__).parent / "add_offices_tables.sql"

    if not migration_file.exists():
        raise FileNotFoundError(f"Файл миграции не найден: {migration_file}")

    # Читаем SQL скрипт
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()

    def _execute_migration(session):
        # Разбиваем на отдельные SQL команды
        statements = [s.strip() for s in sql_script.split(';') if s.strip() and not s.strip().startswith('--')]

        logger.info(f"Найдено {len(statements)} SQL команд для выполнения")

        for i, statement in enumerate(statements, 1):
            # Пропускаем комментарии и пустые строки
            if not statement or statement.startswith('--'):
                continue

            try:
                logger.info(f"Выполнение команды {i}/{len(statements)}...")
                logger.debug(f"SQL: {statement[:100]}...")

                result = session.execute(text(statement))

                # Если это SELECT запрос, выводим результат
                if statement.strip().upper().startswith('SELECT'):
                    rows = result.fetchall()
                    for row in rows:
                        logger.info(f"  {dict(row._mapping)}")

                session.commit()

            except Exception as e:
                logger.error(f"Ошибка при выполнении команды {i}: {e}")
                logger.error(f"SQL: {statement}")
                # Если таблица уже существует - это нормально, продолжаем
                if "already exists" in str(e).lower():
                    logger.warning("Таблица уже существует, пропускаем...")
                    session.rollback()
                    continue
                else:
                    session.rollback()
                    raise

        return True

    try:
        result = DatabaseManager.safe_execute(_execute_migration)
        return result
    except Exception as e:
        logger.error(f"Ошибка применения миграции: {e}")
        raise


def verify_migration():
    """Проверяет, что миграция была применена корректно"""

    def _verify(session):
        # Проверяем наличие таблиц
        tables_to_check = ['offices', 'office_tenants', 'office_tenant_reminders']

        for table_name in tables_to_check:
            result = session.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            )).fetchone()

            if result:
                logger.info(f"✓ Таблица '{table_name}' создана успешно")
            else:
                logger.error(f"✗ Таблица '{table_name}' не найдена!")
                return False

        # Проверяем индексы для offices
        result = session.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='offices'"
        )).fetchall()

        index_count = len(result)
        logger.info(f"✓ Создано {index_count} индексов для таблицы offices")

        return True

    return DatabaseManager.safe_execute(_verify)


def main():
    """Главная функция скрипта"""
    logger.info("=" * 70)
    logger.info("Миграция: Добавление таблиц для управления офисами")
    logger.info("=" * 70)

    try:
        # Инициализируем базу данных
        DatabaseManager.ensure_initialized()
        logger.info("✓ База данных инициализирована")

        # Применяем миграцию
        logger.info("\nПрименение SQL миграции...")
        apply_migration()

        # Проверяем результат
        logger.info("\nПроверка результатов миграции...")
        if verify_migration():
            logger.info("\n" + "=" * 70)
            logger.info("✅ Миграция завершена успешно!")
            logger.info("=" * 70)
        else:
            logger.error("\n" + "=" * 70)
            logger.error("❌ Миграция выполнена с ошибками!")
            logger.error("=" * 70)
            sys.exit(1)

    except Exception as e:
        logger.error(f"\n❌ Критическая ошибка миграции: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
