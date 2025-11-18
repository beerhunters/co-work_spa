#!/usr/bin/env python3
"""
Главный скрипт миграций
Запускает все миграции по порядку

Использование:
    python migrations/run_all_migrations.py
    python migrations/run_all_migrations.py --auto-confirm
"""

import sys
import os
import shutil
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR


class MigrationRunner:
    """Запускает все миграции по порядку"""

    def __init__(self):
        self.db_path = DATA_DIR / "coworking.db"
        self.backup_dir = DATA_DIR / "backups"
        self.migrations_dir = Path(__file__).parent
        self.backup_path = None

        # Список миграций в порядке выполнения
        self.migrations = [
            {
                'name': 'add_email_tables',
                'description': 'Создание таблиц для email рассылок',
                'module': 'migrations.add_email_tables',
                'function': 'run_migration'
            },
            {
                'name': 'migrate_email_tracking',
                'description': 'Обновление user_id на nullable для custom emails',
                'module': 'migrations.migrate_email_tracking',
                'class': 'EmailTrackingMigration'
            }
        ]

    def log(self, message: str, level: str = "INFO"):
        """Логирование с timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def create_master_backup(self) -> bool:
        """Создает главный бэкап перед всеми миграциями"""
        try:
            if not self.db_path.exists():
                self.log(f"База данных не найдена: {self.db_path}", "ERROR")
                return False

            # Создаем директорию для бэкапов
            self.backup_dir.mkdir(exist_ok=True)

            # Имя бэкапа с timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.backup_path = self.backup_dir / f"pre_all_migrations_{timestamp}.db"

            self.log(f"Создание главного бэкапа: {self.backup_path}")
            shutil.copy2(self.db_path, self.backup_path)

            # Проверяем размер
            original_size = self.db_path.stat().st_size
            backup_size = self.backup_path.stat().st_size

            if original_size != backup_size:
                self.log("Размер бэкапа не совпадает с оригиналом!", "ERROR")
                return False

            self.log(f"✅ Главный бэкап создан успешно ({backup_size} bytes)", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Ошибка создания бэкапа: {e}", "ERROR")
            return False

    def run_single_migration(self, migration: dict) -> bool:
        """Запускает одну миграцию"""
        try:
            self.log("=" * 60)
            self.log(f"Миграция: {migration['name']}", "INFO")
            self.log(f"Описание: {migration['description']}", "INFO")
            self.log("=" * 60)

            # Импортируем модуль миграции
            module = __import__(migration['module'], fromlist=[''])

            # Запускаем миграцию
            if 'function' in migration:
                # Простая функция (add_email_tables)
                func = getattr(module, migration['function'])
                result = func()

                if result:
                    self.log(f"✅ Миграция {migration['name']} завершена успешно", "SUCCESS")
                    return True
                else:
                    self.log(f"❌ Миграция {migration['name']} не удалась", "ERROR")
                    return False

            elif 'class' in migration:
                # Класс миграции (migrate_email_tracking)
                cls = getattr(module, migration['class'])
                migrator = cls()
                result = migrator.run(auto_confirm=True)

                if result:
                    self.log(f"✅ Миграция {migration['name']} завершена успешно", "SUCCESS")
                    return True
                else:
                    self.log(f"❌ Миграция {migration['name']} не удалась", "ERROR")
                    return False

            else:
                self.log(f"Неизвестный тип миграции: {migration}", "ERROR")
                return False

        except Exception as e:
            self.log(f"Ошибка выполнения миграции {migration['name']}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False

    def rollback(self) -> bool:
        """Откатывает все изменения из главного бэкапа"""
        try:
            if not self.backup_path or not self.backup_path.exists():
                self.log("Главный бэкап не найден для отката", "ERROR")
                return False

            self.log(f"Откат из главного бэкапа: {self.backup_path}")
            shutil.copy2(self.backup_path, self.db_path)
            self.log("✅ Откат выполнен успешно", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Ошибка отката: {e}", "ERROR")
            return False

    def run(self, auto_confirm: bool = False) -> bool:
        """Запускает все миграции"""
        try:
            self.log("=" * 70)
            self.log("ЗАПУСК ВСЕХ МИГРАЦИЙ", "INFO")
            self.log("=" * 70)
            self.log("")

            # 1. Создаем главный бэкап
            if not self.create_master_backup():
                self.log("Не удалось создать главный бэкап. Миграции отменены.", "ERROR")
                return False

            # 2. Подтверждение
            if not auto_confirm:
                print("\n⚠️  ВНИМАНИЕ: Будут выполнены все миграции базы данных!")
                print(f"Главный бэкап сохранен: {self.backup_path}")
                print("\nМиграции к выполнению:")
                for i, mig in enumerate(self.migrations, 1):
                    print(f"  {i}. {mig['name']} - {mig['description']}")
                print()

                response = input("Продолжить выполнение всех миграций? (yes/no): ").strip().lower()
                if response != 'yes':
                    self.log("Миграции отменены пользователем", "WARNING")
                    return False

            self.log("")

            # 3. Выполняем миграции по порядку
            for migration in self.migrations:
                if not self.run_single_migration(migration):
                    self.log(f"Миграция {migration['name']} не удалась. Выполняется откат...", "ERROR")
                    self.rollback()
                    return False
                self.log("")

            # 4. Все миграции успешны
            self.log("=" * 70)
            self.log("✅ ВСЕ МИГРАЦИИ ЗАВЕРШЕНЫ УСПЕШНО!", "SUCCESS")
            self.log("=" * 70)
            self.log(f"Главный бэкап сохранен: {self.backup_path}")
            self.log("Можно удалить бэкап после проверки работоспособности")
            self.log("")

            return True

        except Exception as e:
            self.log(f"Критическая ошибка: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            self.log("Выполняется откат...", "ERROR")
            self.rollback()
            return False


def main():
    """Точка входа"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Запуск всех миграций базы данных"
    )
    parser.add_argument(
        '--auto-confirm',
        action='store_true',
        help='Автоматическое подтверждение (для автоматического деплоя)'
    )

    args = parser.parse_args()

    runner = MigrationRunner()
    success = runner.run(auto_confirm=args.auto_confirm)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
