#!/usr/bin/env python3
"""
Скрипт миграции базы данных для добавления новых полей и таблиц.
Запускается автоматически при старте приложения.
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from datetime import datetime
from config import DATA_DIR, MOSCOW_TZ
from utils.logger import get_logger

logger = get_logger(__name__)

# Путь к базе данных
DB_PATH = Path(DATA_DIR) / "coworking.db"


def check_column_exists(cursor, table_name, column_name):
    """Проверяет существование колонки в таблице."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def check_table_exists(cursor, table_name):
    """Проверяет существование таблицы."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_add_bot_blocked_fields(conn, cursor):
    """Добавляет поля bot_blocked и bot_blocked_at в таблицу users."""
    logger.info("Проверка миграции: добавление полей bot_blocked в таблицу users")

    changes_made = False

    # Проверяем и добавляем поле bot_blocked
    if not check_column_exists(cursor, 'users', 'bot_blocked'):
        logger.info("Добавление поля bot_blocked в таблицу users")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN bot_blocked BOOLEAN NOT NULL DEFAULT 0"
        )
        # Создаем индекс для быстрой фильтрации
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_bot_blocked ON users(bot_blocked)"
        )
        conn.commit()
        changes_made = True
        logger.info("✅ Поле bot_blocked успешно добавлено")
    else:
        logger.info("⏭️  Поле bot_blocked уже существует, пропускаем")

    # Проверяем и добавляем поле bot_blocked_at
    if not check_column_exists(cursor, 'users', 'bot_blocked_at'):
        logger.info("Добавление поля bot_blocked_at в таблицу users")
        cursor.execute(
            "ALTER TABLE users ADD COLUMN bot_blocked_at DATETIME"
        )
        conn.commit()
        changes_made = True
        logger.info("✅ Поле bot_blocked_at успешно добавлено")
    else:
        logger.info("⏭️  Поле bot_blocked_at уже существует, пропускаем")

    return changes_made


def migrate_create_refresh_tokens_table(conn, cursor):
    """Создает таблицу refresh_tokens."""
    logger.info("Проверка миграции: создание таблицы refresh_tokens")

    if check_table_exists(cursor, 'refresh_tokens'):
        logger.info("⏭️  Таблица refresh_tokens уже существует, пропускаем")
        return False

    logger.info("Создание таблицы refresh_tokens")
    cursor.execute("""
        CREATE TABLE refresh_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            token VARCHAR(500) NOT NULL UNIQUE,
            expires_at DATETIME NOT NULL,
            created_at DATETIME NOT NULL,
            revoked BOOLEAN NOT NULL DEFAULT 0,
            FOREIGN KEY (admin_id) REFERENCES admins(id) ON DELETE CASCADE
        )
    """)

    # Создаем индексы для производительности
    cursor.execute(
        "CREATE INDEX idx_refresh_tokens_admin_id ON refresh_tokens(admin_id)"
    )
    cursor.execute(
        "CREATE INDEX idx_refresh_tokens_token ON refresh_tokens(token)"
    )
    cursor.execute(
        "CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)"
    )

    conn.commit()
    logger.info("✅ Таблица refresh_tokens успешно создана")
    return True


def run_migrations():
    """Запускает все миграции."""
    logger.info("=" * 60)
    logger.info("Начало миграции базы данных")
    logger.info(f"Путь к БД: {DB_PATH}")
    logger.info("=" * 60)

    if not os.path.exists(DB_PATH):
        logger.warning(f"База данных не найдена по пути {DB_PATH}")
        logger.info("База данных будет создана при первом запуске приложения")
        return

    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Запускаем миграции
        migrations = [
            ("Добавление полей bot_blocked", migrate_add_bot_blocked_fields),
            ("Создание таблицы refresh_tokens", migrate_create_refresh_tokens_table),
        ]

        total_changes = 0
        for migration_name, migration_func in migrations:
            try:
                logger.info(f"\n--- Выполнение: {migration_name} ---")
                changes = migration_func(conn, cursor)
                if changes:
                    total_changes += 1
            except Exception as e:
                logger.error(f"Ошибка при выполнении миграции '{migration_name}': {e}")
                conn.rollback()
                raise

        # Закрываем соединение
        cursor.close()
        conn.close()

        logger.info("=" * 60)
        if total_changes > 0:
            logger.info(f"✅ Миграция завершена успешно! Применено изменений: {total_changes}")
        else:
            logger.info("✅ База данных актуальна, изменений не требуется")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Критическая ошибка при миграции: {e}")
        raise


if __name__ == "__main__":
    run_migrations()
