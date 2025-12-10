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


def migrate_create_offices_tables(conn, cursor):
    """Создает таблицы для управления офисами."""
    logger.info("Проверка миграции: создание таблиц для управления офисами")

    changes_made = False

    # 1. Создаем таблицу offices
    if not check_table_exists(cursor, 'offices'):
        logger.info("Создание таблицы offices")
        cursor.execute("""
            CREATE TABLE offices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                office_number VARCHAR(20) NOT NULL UNIQUE,
                floor INTEGER NOT NULL,
                capacity INTEGER NOT NULL,
                price_per_month FLOAT NOT NULL,
                payment_day INTEGER,
                admin_reminder_enabled BOOLEAN DEFAULT 0,
                admin_reminder_days INTEGER DEFAULT 5,
                tenant_reminder_enabled BOOLEAN DEFAULT 0,
                tenant_reminder_days INTEGER DEFAULT 5,
                comment TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """)

        # Создаем индексы для таблицы offices
        cursor.execute("CREATE INDEX idx_offices_office_number ON offices(office_number)")
        cursor.execute("CREATE INDEX idx_offices_floor ON offices(floor)")
        cursor.execute("CREATE INDEX idx_offices_is_active ON offices(is_active)")
        cursor.execute("CREATE INDEX idx_offices_created_at ON offices(created_at)")
        cursor.execute("CREATE INDEX idx_offices_floor_active ON offices(floor, is_active)")

        conn.commit()
        changes_made = True
        logger.info("✅ Таблица offices успешно создана")
    else:
        logger.info("⏭️  Таблица offices уже существует, пропускаем")

    # 2. Создаем таблицу office_tenants
    if not check_table_exists(cursor, 'office_tenants'):
        logger.info("Создание таблицы office_tenants")
        cursor.execute("""
            CREATE TABLE office_tenants (
                office_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (office_id, user_id),
                FOREIGN KEY (office_id) REFERENCES offices(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX idx_office_tenants_office ON office_tenants(office_id)")
        cursor.execute("CREATE INDEX idx_office_tenants_user ON office_tenants(user_id)")

        conn.commit()
        changes_made = True
        logger.info("✅ Таблица office_tenants успешно создана")
    else:
        logger.info("⏭️  Таблица office_tenants уже существует, пропускаем")

    # 3. Создаем таблицу office_tenant_reminders
    if not check_table_exists(cursor, 'office_tenant_reminders'):
        logger.info("Создание таблицы office_tenant_reminders")
        cursor.execute("""
            CREATE TABLE office_tenant_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                office_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (office_id) REFERENCES offices(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX idx_office_tenant_reminder_office ON office_tenant_reminders(office_id)")
        cursor.execute("CREATE INDEX idx_office_tenant_reminder_user ON office_tenant_reminders(user_id)")
        cursor.execute("CREATE UNIQUE INDEX idx_office_tenant_reminder ON office_tenant_reminders(office_id, user_id)")

        conn.commit()
        changes_made = True
        logger.info("✅ Таблица office_tenant_reminders успешно создана")
    else:
        logger.info("⏭️  Таблица office_tenant_reminders уже существует, пропускаем")

    return changes_made


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
            ("Создание таблиц для управления офисами", migrate_create_offices_tables),
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
