-- Миграция для добавления таблиц управления офисами
-- Дата: 2025-12-10
-- Описание: Добавляет таблицы offices, office_tenants, office_tenant_reminders

-- ============================================================================
-- 1. Таблица офисов
-- ============================================================================
CREATE TABLE IF NOT EXISTS offices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    office_number VARCHAR(20) NOT NULL UNIQUE,
    floor INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    price_per_month FLOAT NOT NULL,
    payment_day INTEGER,  -- День месяца для платежа (1-31)

    -- Настройки напоминаний для администратора
    admin_reminder_enabled BOOLEAN DEFAULT 0,
    admin_reminder_days INTEGER DEFAULT 5,

    -- Настройки напоминаний для постояльцев
    tenant_reminder_enabled BOOLEAN DEFAULT 0,
    tenant_reminder_days INTEGER DEFAULT 5,

    -- Комментарий
    comment TEXT,

    -- Метаданные
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

-- Индексы для таблицы offices
CREATE INDEX IF NOT EXISTS idx_offices_office_number ON offices(office_number);
CREATE INDEX IF NOT EXISTS idx_offices_floor ON offices(floor);
CREATE INDEX IF NOT EXISTS idx_offices_is_active ON offices(is_active);
CREATE INDEX IF NOT EXISTS idx_offices_created_at ON offices(created_at);
CREATE INDEX IF NOT EXISTS idx_offices_floor_active ON offices(floor, is_active);

-- ============================================================================
-- 2. Промежуточная таблица для связи офисов и постояльцев (many-to-many)
-- ============================================================================
CREATE TABLE IF NOT EXISTS office_tenants (
    office_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (office_id, user_id),

    FOREIGN KEY (office_id) REFERENCES offices(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для office_tenants
CREATE INDEX IF NOT EXISTS idx_office_tenants_office ON office_tenants(office_id);
CREATE INDEX IF NOT EXISTS idx_office_tenants_user ON office_tenants(user_id);

-- ============================================================================
-- 3. Таблица настроек напоминаний для конкретных постояльцев
-- ============================================================================
CREATE TABLE IF NOT EXISTS office_tenant_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    office_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    is_enabled BOOLEAN DEFAULT 1,

    FOREIGN KEY (office_id) REFERENCES offices(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Индексы для office_tenant_reminders
CREATE INDEX IF NOT EXISTS idx_office_tenant_reminder_office ON office_tenant_reminders(office_id);
CREATE INDEX IF NOT EXISTS idx_office_tenant_reminder_user ON office_tenant_reminders(user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_office_tenant_reminder ON office_tenant_reminders(office_id, user_id);

-- ============================================================================
-- Проверка успешности миграции
-- ============================================================================
SELECT
    'Миграция завершена успешно!' as status,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='offices') as offices_table,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='office_tenants') as office_tenants_table,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='office_tenant_reminders') as office_tenant_reminders_table;
