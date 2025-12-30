-- Migration: Add scheduled_tasks and office_subscriptions tables
-- Date: 2025-12-30
-- Description: Adds tables for scheduled tasks management and office subscriptions

-- ============================================
-- 1. Create office_subscriptions table
-- ============================================

CREATE TABLE IF NOT EXISTS office_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    office_1 BOOLEAN NOT NULL DEFAULT 0,
    office_2 BOOLEAN NOT NULL DEFAULT 0,
    office_4 BOOLEAN NOT NULL DEFAULT 0,
    office_6 BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    telegram_id BIGINT NOT NULL,
    full_name VARCHAR(100),
    username VARCHAR(50),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for office_subscriptions
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_user_id ON office_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_telegram_id ON office_subscriptions(telegram_id);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_created_at ON office_subscriptions(created_at);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_office_1 ON office_subscriptions(office_1);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_office_2 ON office_subscriptions(office_2);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_office_4 ON office_subscriptions(office_4);
CREATE INDEX IF NOT EXISTS idx_office_subscriptions_office_6 ON office_subscriptions(office_6);

-- ============================================
-- 2. Create scheduled_tasks table
-- ============================================

CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type VARCHAR(50) NOT NULL,
    celery_task_id VARCHAR(255) UNIQUE,
    office_id INTEGER,
    booking_id INTEGER,
    scheduled_datetime TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    executed_at TIMESTAMP,
    result TEXT,
    error_message TEXT,
    params TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (office_id) REFERENCES offices(id) ON DELETE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
);

-- Create indexes for scheduled_tasks
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_task_type ON scheduled_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_celery_task_id ON scheduled_tasks(celery_task_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_office_id ON scheduled_tasks(office_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_booking_id ON scheduled_tasks(booking_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_scheduled_datetime ON scheduled_tasks(scheduled_datetime);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_created_at ON scheduled_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_status ON scheduled_tasks(status);

-- ============================================
-- 3. Update users table (add relationship support)
-- ============================================

-- Note: SQLite doesn't support ALTER TABLE ADD FOREIGN KEY for existing tables.
-- The relationship is handled at the application level through SQLAlchemy.
-- No database schema changes needed for the users table.

-- ============================================
-- Migration complete
-- ============================================

SELECT 'Migration completed successfully. Tables created:' AS status;
SELECT name FROM sqlite_master WHERE type='table' AND (name='office_subscriptions' OR name='scheduled_tasks');
