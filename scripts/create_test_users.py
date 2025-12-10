#!/usr/bin/env python3
"""
Скрипт для создания тестовых пользователей для проверки рассылок.
Создает 150 тестовых пользователей с разными статусами для тестирования батч-обработки.
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import random

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MOSCOW_TZ
from models.models import DatabaseManager, User
from utils.logger import get_logger

logger = get_logger(__name__)


def create_test_users(count: int = 150):
    """
    Создает тестовых пользователей.

    Args:
        count: Количество пользователей для создания (по умолчанию 150)

    Распределение:
    - 120 обычных пользователей (активных)
    - 20 пользователей с bot_blocked=True (заблокировали бота)
    - 10 пользователей с несуществующими telegram_id (для chat_not_found)
    """

    def _create_users(session):
        # Проверяем, есть ли уже тестовые пользователи
        existing_test_users = session.query(User).filter(
            User.full_name.like('Test User %')
        ).count()

        if existing_test_users > 0:
            logger.warning(f"Найдено {existing_test_users} существующих тестовых пользователей")
            response = input("Удалить существующих тестовых пользователей? (y/n): ")
            if response.lower() == 'y':
                session.query(User).filter(
                    User.full_name.like('Test User %')
                ).delete(synchronize_session='fetch')
                session.commit()
                logger.info("Существующие тестовые пользователи удалены")
            else:
                logger.info("Создание отменено")
                return 0

        created_count = 0
        base_telegram_id = 1000000000  # Базовый ID для тестовых пользователей

        # 1. Создаём 120 обычных активных пользователей
        logger.info("Создание 120 обычных активных пользователей...")
        for i in range(1, 121):
            user = User(
                telegram_id=base_telegram_id + i,
                full_name=f"Test User {i:03d}",
                username=f"testuser{i:03d}",
                phone=f"+7900{i:07d}",
                is_banned=False,
                bot_blocked=False,
                reg_date=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365)),
                first_join_time=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365))
            )
            session.add(user)
            created_count += 1

            if i % 20 == 0:
                logger.info(f"  Создано {i} обычных пользователей...")

        # 2. Создаём 20 пользователей, заблокировавших бота
        logger.info("Создание 20 пользователей с bot_blocked=True...")
        for i in range(121, 141):
            user = User(
                telegram_id=base_telegram_id + i,
                full_name=f"Test User {i:03d} (Blocked Bot)",
                username=f"testuser{i:03d}",
                phone=f"+7900{i:07d}",
                is_banned=False,
                bot_blocked=True,
                bot_blocked_at=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 30)),
                reg_date=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365)),
                first_join_time=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365))
            )
            session.add(user)
            created_count += 1

        # 3. Создаём 10 пользователей с несуществующими telegram_id
        # (используем большие ID, которые точно не существуют)
        logger.info("Создание 10 пользователей с несуществующими telegram_id...")
        base_fake_id = 9999999000  # Явно несуществующие ID
        for i in range(141, 151):
            user = User(
                telegram_id=base_fake_id + i,
                full_name=f"Test User {i:03d} (Fake ID)",
                username=f"testuser{i:03d}",
                phone=f"+7900{i:07d}",
                is_banned=False,
                bot_blocked=False,
                reg_date=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365)),
                first_join_time=datetime.now(MOSCOW_TZ) - timedelta(days=random.randint(1, 365))
            )
            session.add(user)
            created_count += 1

        session.commit()
        logger.info(f"✅ Создано {created_count} тестовых пользователей")

        return created_count

    try:
        total_created = DatabaseManager.safe_execute(_create_users)

        if total_created > 0:
            logger.info("=" * 60)
            logger.info("📊 Статистика созданных пользователей:")
            logger.info(f"  • Обычных активных: 120")
            logger.info(f"  • С bot_blocked=True: 20")
            logger.info(f"  • С несуществующими telegram_id: 10")
            logger.info(f"  • ВСЕГО: {total_created}")
            logger.info("=" * 60)
            logger.info("")
            logger.info("💡 Рекомендации по тестированию:")
            logger.info("  1. Перезапустите Celery worker: docker-compose restart celery_worker")
            logger.info("  2. Создайте рассылку через админку, выбрав 'Все пользователи'")
            logger.info("  3. Проверьте логи: docker-compose logs -f celery_worker")
            logger.info("  4. Убедитесь, что:")
            logger.info("     - Батчи по 100 обрабатываются корректно")
            logger.info("     - Пользователи с bot_blocked помечаются правильно")
            logger.info("     - Несуществующие чаты обрабатываются без крэша")
            logger.info("     - Переменная 'recipients' не вызывает ошибок")
            logger.info("")

    except Exception as e:
        logger.error(f"Ошибка при создании тестовых пользователей: {e}")
        raise


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Запуск скрипта создания тестовых пользователей")
    logger.info("=" * 60)

    try:
        create_test_users(150)
    except KeyboardInterrupt:
        logger.info("\n❌ Создание прервано пользователем")
    except Exception as e:
        logger.error(f"\n❌ Критическая ошибка: {e}")
        sys.exit(1)
