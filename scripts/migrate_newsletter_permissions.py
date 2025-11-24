#!/usr/bin/env python3
"""
Скрипт миграции прав для рассылок.
Переименовывает старые права на рассылки в Telegram-специфичные права.

Миграция:
- view_newsletters -> view_telegram_newsletters
- send_newsletters -> send_telegram_newsletters
- manage_newsletters -> manage_telegram_newsletters
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.models import DatabaseManager, AdminPermission, Permission
from sqlalchemy import text
from utils.logger import get_logger

logger = get_logger(__name__)


def migrate_permissions():
    """
    Миграция прав на рассылки из общих в Telegram-специфичные.
    """

    # Маппинг старых прав на новые
    permission_mapping = {
        'view_newsletters': 'view_telegram_newsletters',
        'send_newsletters': 'send_telegram_newsletters',
        'manage_newsletters': 'manage_telegram_newsletters'
    }

    try:
        def _migrate(session):
            total_updated = 0

            for old_perm, new_perm in permission_mapping.items():
                # Используем raw SQL для обновления, так как старые права уже не существуют в enum
                # Сначала проверяем сколько записей нужно обновить
                count_query = text(
                    "SELECT COUNT(*) FROM admin_permissions WHERE permission = :old_perm"
                )
                result = session.execute(count_query, {"old_perm": old_perm})
                count = result.scalar()

                if count > 0:
                    logger.info(f"Найдено {count} записей с правом '{old_perm}'")

                    # Получаем список admin_id для логирования
                    select_query = text(
                        "SELECT admin_id FROM admin_permissions WHERE permission = :old_perm"
                    )
                    admins_result = session.execute(select_query, {"old_perm": old_perm})
                    admin_ids = [row[0] for row in admins_result]

                    # Обновляем все записи
                    update_query = text(
                        "UPDATE admin_permissions SET permission = :new_perm "
                        "WHERE permission = :old_perm"
                    )
                    session.execute(update_query, {"old_perm": old_perm, "new_perm": new_perm})

                    for admin_id in admin_ids:
                        logger.info(
                            f"  Обновлено право для admin_id={admin_id}: "
                            f"{old_perm} -> {new_perm}"
                        )

                    total_updated += count
                else:
                    logger.info(f"Записей с правом '{old_perm}' не найдено")

            session.commit()
            return total_updated

        # Выполняем миграцию
        logger.info("=" * 60)
        logger.info("Начало миграции прав на рассылки")
        logger.info("=" * 60)

        total = DatabaseManager.safe_execute(_migrate)

        logger.info("=" * 60)
        logger.info(f"Миграция завершена успешно!")
        logger.info(f"Всего обновлено записей: {total}")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"Ошибка при миграции прав: {str(e)}", exc_info=True)
        return False


def verify_migration():
    """
    Проверка результатов миграции.
    """
    try:
        def _verify(session):
            results = {
                'old_permissions': {},
                'new_permissions': {}
            }

            # Проверяем старые права (их не должно остаться)
            old_perms = ['view_newsletters', 'send_newsletters', 'manage_newsletters']
            for perm_name in old_perms:
                count_query = text(
                    "SELECT COUNT(*) FROM admin_permissions WHERE permission = :perm"
                )
                result = session.execute(count_query, {"perm": perm_name})
                count = result.scalar()
                results['old_permissions'][perm_name] = count

            # Проверяем новые права
            new_perms = [
                'view_telegram_newsletters',
                'send_telegram_newsletters',
                'manage_telegram_newsletters'
            ]
            for perm_name in new_perms:
                count_query = text(
                    "SELECT COUNT(*) FROM admin_permissions WHERE permission = :perm"
                )
                result = session.execute(count_query, {"perm": perm_name})
                count = result.scalar()
                results['new_permissions'][perm_name] = count

            return results

        logger.info("\n" + "=" * 60)
        logger.info("Проверка результатов миграции")
        logger.info("=" * 60)

        results = DatabaseManager.safe_execute(_verify)

        logger.info("\nСтарые права (должны быть 0 или N/A):")
        for perm, count in results['old_permissions'].items():
            logger.info(f"  {perm}: {count}")

        logger.info("\nНовые права:")
        for perm, count in results['new_permissions'].items():
            logger.info(f"  {perm}: {count}")

        logger.info("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Ошибка при проверке миграции: {str(e)}", exc_info=True)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("МИГРАЦИЯ ПРАВ НА РАССЫЛКИ")
    print("=" * 60)
    print("\nЭтот скрипт переименует права на рассылки:")
    print("  view_newsletters -> view_telegram_newsletters")
    print("  send_newsletters -> send_telegram_newsletters")
    print("  manage_newsletters -> manage_telegram_newsletters")
    print("\nВнимание: убедитесь, что создали резервную копию базы данных!")
    print("=" * 60 + "\n")

    response = input("Продолжить миграцию? (yes/no): ").strip().lower()

    if response in ['yes', 'y', 'да']:
        success = migrate_permissions()

        if success:
            print("\n✅ Миграция выполнена успешно!")
            verify_migration()
        else:
            print("\n❌ Миграция завершилась с ошибками. Проверьте логи.")
            sys.exit(1)
    else:
        print("\n❌ Миграция отменена пользователем.")
        sys.exit(0)
