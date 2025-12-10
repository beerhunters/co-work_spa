#!/usr/bin/env python3
"""
Скрипт для добавления разрешений на управление офисами существующим администраторам.
Добавляет VIEW_OFFICES, CREATE_OFFICES, EDIT_OFFICES, DELETE_OFFICES всем super_admin.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.models import DatabaseManager, Admin, AdminPermission, Permission, AdminRole
from utils.logger import get_logger

logger = get_logger(__name__)


def add_office_permissions_to_super_admins():
    """Добавляет разрешения на офисы всем super_admin"""

    def _add_permissions(session):
        # Получаем всех super_admin
        super_admins = session.query(Admin).filter(
            Admin.role == AdminRole.SUPER_ADMIN
        ).all()

        if not super_admins:
            logger.info("Не найдено ни одного super_admin")
            return 0

        # Разрешения для офисов
        office_permissions = [
            Permission.VIEW_OFFICES,
            Permission.CREATE_OFFICES,
            Permission.EDIT_OFFICES,
            Permission.DELETE_OFFICES
        ]

        added_count = 0

        for admin in super_admins:
            logger.info(f"Обработка администратора: {admin.login} (ID: {admin.id})")

            for permission in office_permissions:
                # Проверяем, существует ли уже это разрешение
                existing = session.query(AdminPermission).filter(
                    AdminPermission.admin_id == admin.id,
                    AdminPermission.permission == permission
                ).first()

                if existing:
                    logger.info(f"  ✓ {permission.value} уже существует")
                else:
                    # Добавляем новое разрешение
                    new_permission = AdminPermission(
                        admin_id=admin.id,
                        permission=permission,
                        granted=True
                    )
                    session.add(new_permission)
                    added_count += 1
                    logger.info(f"  + Добавлено разрешение: {permission.value}")

        session.commit()
        logger.info(f"\n✅ Добавлено {added_count} новых разрешений")
        return added_count

    try:
        result = DatabaseManager.safe_execute(_add_permissions)
        return result
    except Exception as e:
        logger.error(f"Ошибка при добавлении разрешений: {e}")
        raise


def main():
    """Главная функция скрипта"""
    logger.info("=" * 60)
    logger.info("Скрипт добавления разрешений на управление офисами")
    logger.info("=" * 60)

    try:
        # Инициализируем базу данных
        DatabaseManager.ensure_initialized()
        logger.info("База данных инициализирована")

        # Добавляем разрешения
        added = add_office_permissions_to_super_admins()

        logger.info("\n" + "=" * 60)
        logger.info("✅ Миграция завершена успешно!")
        logger.info(f"Всего добавлено разрешений: {added}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n❌ Ошибка выполнения миграции: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
