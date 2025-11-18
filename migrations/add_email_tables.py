"""
Миграция: Добавление таблиц для email рассылок
Дата: 2025-11-14
Описание: Создает таблицы email_campaigns, email_campaign_recipients, email_templates, email_tracking
"""

import sqlite3
import os
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR
from utils.logger import get_logger

logger = get_logger(__name__)

# Путь к БД
DB_PATH = f"{DATA_DIR}/coworking.db"


def run_migration():
    """Выполняет миграцию базы данных"""

    logger.info(f"Начало миграции: добавление таблиц email рассылок")
    logger.info(f"Путь к БД: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        logger.error(f"База данных не найдена: {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверяем, существует ли уже таблица
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_campaigns'")
        if cursor.fetchone():
            logger.warning("Таблица email_campaigns уже существует. Миграция не требуется.")
            conn.close()
            return True

        logger.info("Создание таблицы email_campaigns...")
        cursor.execute("""
            CREATE TABLE email_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                subject VARCHAR(500) NOT NULL,
                html_content TEXT NOT NULL,
                unlayer_design TEXT,
                recipient_type VARCHAR(50) NOT NULL,
                recipient_ids TEXT,
                segment_type VARCHAR(100),
                segment_params TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'draft',
                scheduled_at DATETIME,
                total_count INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                delivered_count INTEGER NOT NULL DEFAULT 0,
                opened_count INTEGER NOT NULL DEFAULT 0,
                clicked_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                bounced_count INTEGER NOT NULL DEFAULT 0,
                is_ab_test BOOLEAN NOT NULL DEFAULT 0,
                ab_test_percentage INTEGER,
                ab_variant_b_subject VARCHAR(500),
                ab_variant_b_content TEXT,
                created_at DATETIME NOT NULL,
                sent_at DATETIME,
                created_by VARCHAR(255)
            )
        """)

        # Создаем индексы для email_campaigns
        logger.info("Создание индексов для email_campaigns...")
        cursor.execute("CREATE INDEX ix_email_campaigns_recipient_type ON email_campaigns(recipient_type)")
        cursor.execute("CREATE INDEX ix_email_campaigns_segment_type ON email_campaigns(segment_type)")
        cursor.execute("CREATE INDEX ix_email_campaigns_status ON email_campaigns(status)")
        cursor.execute("CREATE INDEX ix_email_campaigns_scheduled_at ON email_campaigns(scheduled_at)")
        cursor.execute("CREATE INDEX ix_email_campaigns_created_at ON email_campaigns(created_at)")
        cursor.execute("CREATE INDEX ix_email_campaigns_sent_at ON email_campaigns(sent_at)")

        logger.info("Создание таблицы email_campaign_recipients...")
        cursor.execute("""
            CREATE TABLE email_campaign_recipients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                email VARCHAR(255) NOT NULL,
                full_name VARCHAR(255),
                tracking_token VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                sent_at DATETIME,
                opened_at DATETIME,
                first_click_at DATETIME,
                clicks_count INTEGER NOT NULL DEFAULT 0,
                ab_variant VARCHAR(1),
                FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Создаем индексы для email_campaign_recipients
        logger.info("Создание индексов для email_campaign_recipients...")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_campaign_id ON email_campaign_recipients(campaign_id)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_user_id ON email_campaign_recipients(user_id)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_email ON email_campaign_recipients(email)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_tracking_token ON email_campaign_recipients(tracking_token)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_status ON email_campaign_recipients(status)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_sent_at ON email_campaign_recipients(sent_at)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_opened_at ON email_campaign_recipients(opened_at)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_first_click_at ON email_campaign_recipients(first_click_at)")
        cursor.execute("CREATE INDEX ix_email_campaign_recipients_ab_variant ON email_campaign_recipients(ab_variant)")

        logger.info("Создание таблицы email_templates...")
        cursor.execute("""
            CREATE TABLE email_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(100),
                thumbnail_url VARCHAR(500),
                unlayer_design TEXT NOT NULL,
                html_content TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                created_by VARCHAR(255)
            )
        """)

        # Создаем индексы для email_templates
        logger.info("Создание индексов для email_templates...")
        cursor.execute("CREATE INDEX ix_email_templates_category ON email_templates(category)")
        cursor.execute("CREATE INDEX ix_email_templates_is_active ON email_templates(is_active)")
        cursor.execute("CREATE INDEX ix_email_templates_created_at ON email_templates(created_at)")

        logger.info("Создание таблицы email_tracking...")
        cursor.execute("""
            CREATE TABLE email_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                recipient_id INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                link_url TEXT,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES email_campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (recipient_id) REFERENCES email_campaign_recipients(id) ON DELETE CASCADE
            )
        """)

        # Создаем индексы для email_tracking
        logger.info("Создание индексов для email_tracking...")
        cursor.execute("CREATE INDEX ix_email_tracking_campaign_id ON email_tracking(campaign_id)")
        cursor.execute("CREATE INDEX ix_email_tracking_recipient_id ON email_tracking(recipient_id)")
        cursor.execute("CREATE INDEX ix_email_tracking_event_type ON email_tracking(event_type)")
        cursor.execute("CREATE INDEX ix_email_tracking_created_at ON email_tracking(created_at)")

        # Коммит изменений
        conn.commit()

        logger.info("✅ Миграция успешно выполнена!")
        logger.info("Создано 4 таблицы:")
        logger.info("  - email_campaigns")
        logger.info("  - email_campaign_recipients")
        logger.info("  - email_templates")
        logger.info("  - email_tracking")

        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Ошибка при выполнении миграции: {e}", exc_info=True)
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
