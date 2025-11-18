#!/usr/bin/env python3
"""
Миграция для Email Tracking
Дата: 2025-11-17
Описание: Обновляет таблицу email_campaign_recipients для поддержки custom emails

Изменения:
1. email_campaign_recipients.user_id -> nullable=True (для custom emails без user_id)
"""

import sys
import os
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, MOSCOW_TZ


class EmailTrackingMigration:
    """Миграция для добавления поддержки email tracking с custom emails"""

    def __init__(self):
        self.db_path = DATA_DIR / "coworking.db"
        self.backup_dir = DATA_DIR / "backups"
        self.backup_path = None

    def log(self, message: str, level: str = "INFO"):
        """Логирование с timestamp"""
        timestamp = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def create_backup(self) -> bool:
        """Создает резервную копию базы данных"""
        try:
            if not self.db_path.exists():
                self.log(f"База данных не найдена: {self.db_path}", "ERROR")
                return False

            # Создаем директорию для бэкапов
            self.backup_dir.mkdir(exist_ok=True)

            # Имя бэкапа с timestamp
            timestamp = datetime.now(MOSCOW_TZ).strftime("%Y%m%d_%H%M%S")
            self.backup_path = self.backup_dir / f"pre_migration_email_tracking_{timestamp}.db"

            self.log(f"Создание резервной копии: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)

            # Проверяем размер
            original_size = self.db_path.stat().st_size
            backup_size = self.backup_path.stat().st_size

            if original_size != backup_size:
                self.log("Размер бэкапа не совпадает с оригиналом!", "ERROR")
                return False

            self.log(f"✅ Бэкап создан успешно ({backup_size} bytes)", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Ошибка создания бэкапа: {e}", "ERROR")
            return False

    def check_table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        """Проверяет существование таблицы"""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None

    def get_column_info(self, conn: sqlite3.Connection, table_name: str) -> dict:
        """Получает информацию о колонках таблицы"""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {}
        for row in cursor.fetchall():
            # row = (cid, name, type, notnull, dflt_value, pk)
            columns[row[1]] = {
                'type': row[2],
                'notnull': bool(row[3]),
                'default': row[4],
                'pk': bool(row[5])
            }
        return columns

    def migrate_email_campaign_recipients(self, conn: sqlite3.Connection) -> bool:
        """Мигрирует таблицу email_campaign_recipients"""
        try:
            table_name = "email_campaign_recipients"

            # Проверяем существование таблицы
            if not self.check_table_exists(conn, table_name):
                self.log(f"Таблица {table_name} не найдена. Создание новой таблицы...", "WARNING")
                # Если таблицы нет, она будет создана при запуске приложения
                return True

            # Получаем информацию о колонках
            columns = self.get_column_info(conn, table_name)

            if 'user_id' not in columns:
                self.log("Колонка user_id не найдена. Возможно, таблица новая.", "WARNING")
                return True

            # Проверяем текущее состояние user_id
            user_id_info = columns['user_id']
            self.log(f"Текущее состояние user_id: notnull={user_id_info['notnull']}")

            if not user_id_info['notnull']:
                self.log("✅ Колонка user_id уже nullable, миграция не требуется", "SUCCESS")
                return True

            self.log("Начинаем миграцию таблицы email_campaign_recipients...")

            # SQLite не поддерживает ALTER COLUMN, поэтому создаем новую таблицу
            cursor = conn.cursor()

            # 1. Создаем временную таблицу с новой структурой
            self.log("Создание временной таблицы...")
            cursor.execute(f"""
                CREATE TABLE {table_name}_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    user_id INTEGER,  -- ИЗМЕНЕНО: теперь nullable
                    email VARCHAR(255) NOT NULL,
                    tracking_token VARCHAR(255) UNIQUE NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    sent BOOLEAN DEFAULT 0,
                    sent_at TIMESTAMP,
                    opened BOOLEAN DEFAULT 0,
                    opened_at TIMESTAMP,
                    clicked BOOLEAN DEFAULT 0,
                    clicked_at TIMESTAMP,
                    clicked_links TEXT,
                    bounced BOOLEAN DEFAULT 0,
                    bounce_reason TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            # 2. Копируем данные из старой таблицы
            self.log("Копирование данных...")
            cursor.execute(f"""
                INSERT INTO {table_name}_new
                SELECT * FROM {table_name}
            """)

            rows_copied = cursor.rowcount
            self.log(f"Скопировано записей: {rows_copied}")

            # 3. Получаем индексы из старой таблицы
            cursor.execute(f"""
                SELECT sql FROM sqlite_master
                WHERE type='index' AND tbl_name='{table_name}' AND sql IS NOT NULL
            """)
            indexes = cursor.fetchall()

            # 4. Удаляем старую таблицу
            self.log("Удаление старой таблицы...")
            cursor.execute(f"DROP TABLE {table_name}")

            # 5. Переименовываем новую таблицу
            self.log("Переименование новой таблицы...")
            cursor.execute(f"ALTER TABLE {table_name}_new RENAME TO {table_name}")

            # 6. Восстанавливаем индексы
            self.log("Восстановление индексов...")
            for (index_sql,) in indexes:
                # Заменяем старое имя таблицы на новое в SQL индекса
                index_sql = index_sql.replace(f"{table_name}_new", table_name)
                try:
                    cursor.execute(index_sql)
                    self.log(f"  ✅ Индекс восстановлен")
                except sqlite3.Error as e:
                    self.log(f"  ⚠️  Ошибка восстановления индекса: {e}", "WARNING")

            # 7. Создаем основные индексы если их нет
            self.log("Создание индексов...")
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_campaign_id
                    ON {table_name}(campaign_id)
                """)
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id
                    ON {table_name}(user_id)
                """)
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_tracking_token
                    ON {table_name}(tracking_token)
                """)
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_email
                    ON {table_name}(email)
                """)
            except sqlite3.Error as e:
                self.log(f"Ошибка создания индексов: {e}", "WARNING")

            # 8. Коммитим изменения
            conn.commit()

            # 9. Проверяем результат
            new_columns = self.get_column_info(conn, table_name)
            if 'user_id' in new_columns and not new_columns['user_id']['notnull']:
                self.log("✅ Миграция завершена успешно!", "SUCCESS")
                return True
            else:
                self.log("Ошибка: колонка user_id все еще NOT NULL", "ERROR")
                return False

        except Exception as e:
            self.log(f"Ошибка миграции: {e}", "ERROR")
            conn.rollback()
            return False

    def verify_migration(self, conn: sqlite3.Connection) -> bool:
        """Проверяет успешность миграции"""
        try:
            self.log("Проверка миграции...")

            # Проверяем структуру таблицы
            columns = self.get_column_info(conn, "email_campaign_recipients")

            if 'user_id' not in columns:
                self.log("Ошибка: колонка user_id не найдена", "ERROR")
                return False

            if columns['user_id']['notnull']:
                self.log("Ошибка: user_id все еще NOT NULL", "ERROR")
                return False

            # Проверяем что данные на месте
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM email_campaign_recipients")
            count = cursor.fetchone()[0]

            self.log(f"✅ Проверка пройдена. Записей в таблице: {count}", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Ошибка проверки: {e}", "ERROR")
            return False

    def rollback(self) -> bool:
        """Откатывает миграцию из бэкапа"""
        try:
            if not self.backup_path or not self.backup_path.exists():
                self.log("Бэкап не найден для отката", "ERROR")
                return False

            self.log(f"Откат из бэкапа: {self.backup_path}")
            shutil.copy2(self.backup_path, self.db_path)
            self.log("✅ Откат выполнен успешно", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Ошибка отката: {e}", "ERROR")
            return False

    def run(self, auto_confirm: bool = False) -> bool:
        """Запускает миграцию"""
        try:
            self.log("=" * 60)
            self.log("Email Tracking Migration - Start")
            self.log("=" * 60)

            # 1. Создаем бэкап
            if not self.create_backup():
                self.log("Не удалось создать бэкап. Миграция отменена.", "ERROR")
                return False

            # 2. Подтверждение
            if not auto_confirm:
                print("\n⚠️  ВНИМАНИЕ: Будут внесены изменения в базу данных!")
                print(f"Бэкап сохранен: {self.backup_path}")
                response = input("\nПродолжить миграцию? (yes/no): ").strip().lower()
                if response != 'yes':
                    self.log("Миграция отменена пользователем", "WARNING")
                    return False

            # 3. Подключаемся к БД
            self.log(f"Подключение к БД: {self.db_path}")
            conn = sqlite3.connect(self.db_path)

            try:
                # 4. Выполняем миграцию
                if not self.migrate_email_campaign_recipients(conn):
                    self.log("Миграция не удалась. Выполняется откат...", "ERROR")
                    conn.close()
                    self.rollback()
                    return False

                # 5. Проверяем результат
                if not self.verify_migration(conn):
                    self.log("Проверка не прошла. Выполняется откат...", "ERROR")
                    conn.close()
                    self.rollback()
                    return False

                conn.close()

                self.log("=" * 60)
                self.log("✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!", "SUCCESS")
                self.log("=" * 60)
                self.log(f"Бэкап сохранен: {self.backup_path}")
                self.log("Можно удалить бэкап после проверки работоспособности")

                return True

            except Exception as e:
                self.log(f"Критическая ошибка: {e}", "ERROR")
                conn.close()
                self.rollback()
                return False

        except Exception as e:
            self.log(f"Неожиданная ошибка: {e}", "ERROR")
            return False


def main():
    """Точка входа"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Миграция для Email Tracking"
    )
    parser.add_argument(
        '--auto-confirm',
        action='store_true',
        help='Автоматическое подтверждение (для CI/CD)'
    )

    args = parser.parse_args()

    migration = EmailTrackingMigration()
    success = migration.run(auto_confirm=args.auto_confirm)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
