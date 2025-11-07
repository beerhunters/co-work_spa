import enum
from datetime import datetime
from sqlite3 import IntegrityError
from typing import Optional, List
import threading
import time
import os
from pathlib import Path
from contextlib import contextmanager

import pytz
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    text,
    Boolean,
    Float,
    ForeignKey,
    Date,
    Time,
    select,
    Enum,
    Index,
    event,
    Text,
)
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    sessionmaker,
    relationship,
    scoped_session,
    Session as SQLSession,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DisconnectionError
from werkzeug.security import generate_password_hash, check_password_hash

from utils.logger import get_logger

logger = get_logger(__name__)

Base = declarative_base()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")

# Создаем директорию data если её нет
DB_DIR = Path("/app/data")
DB_DIR.mkdir(exist_ok=True)

# Настройки connection pool - оптимизированы для production
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))  # Увеличено с 5 до 10
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "15"))  # Увеличено с 10 до 15
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "45"))  # Увеличено с 30 до 45
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # Уменьшено до 30 минут
POOL_PRE_PING = True  # Проверка соединений перед использованием

# Улучшенная конфигурация SQLite с optimized connection pooling
engine = create_engine(
    f"sqlite:///{DB_DIR}/coworking.db",
    echo=False,
    pool_pre_ping=POOL_PRE_PING,  # Проверка соединения перед использованием
    pool_size=POOL_SIZE,  # Базовый размер пула (увеличено до 10)
    max_overflow=MAX_OVERFLOW,  # Дополнительные соединения при нагрузке (до 15)
    pool_timeout=POOL_TIMEOUT,  # Таймаут ожидания соединения (45 сек)
    pool_recycle=POOL_RECYCLE,  # Время жизни соединения (30 мин для быстрого обновления)
    poolclass=QueuePool,  # QueuePool вместо StaticPool для лучшего управления
    connect_args={
        "check_same_thread": False,
        "timeout": 60,  # Таймаут блокировки базы
        "isolation_level": "IMMEDIATE",  # Изоляция транзакций для SQLite
    },
)

# Session factory с правильным scope
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Не истекать объекты после коммита
)

# Scoped session для thread-safe работы
Session = scoped_session(SessionLocal)


class ConnectionPoolMonitor:
    """Мониторинг состояния connection pool"""

    @staticmethod
    def get_pool_status() -> dict:
        """Получение статистики пула соединений"""
        try:
            pool = engine.pool

            # Безопасное получение статистики с проверкой доступности методов
            stats = {"pool_timeout": POOL_TIMEOUT, "max_overflow": MAX_OVERFLOW}

            # Основные метрики, доступные в большинстве версий
            if hasattr(pool, "size"):
                stats["pool_size"] = pool.size()
            else:
                stats["pool_size"] = POOL_SIZE

            if hasattr(pool, "checkedin"):
                stats["checked_in"] = pool.checkedin()
            else:
                stats["checked_in"] = 0

            if hasattr(pool, "checkedout"):
                stats["checked_out"] = pool.checkedout()
            else:
                stats["checked_out"] = 0

            if hasattr(pool, "overflow"):
                stats["overflow"] = pool.overflow()
            else:
                stats["overflow"] = 0

            # Вычисляемые метрики
            stats["total_connections"] = stats["checked_in"] + stats["checked_out"]
            stats["available_connections"] = stats["pool_size"] - stats["checked_out"]

            # invalid() доступен не во всех версиях
            if hasattr(pool, "invalid"):
                try:
                    stats["invalid"] = pool.invalid()
                except:
                    stats["invalid"] = 0
            else:
                stats["invalid"] = 0

            return stats

        except Exception as e:
            logger.warning(f"Error getting pool status: {e}")
            return {
                "pool_size": POOL_SIZE,
                "checked_in": 0,
                "checked_out": 0,
                "overflow": 0,
                "invalid": 0,
                "total_connections": 0,
                "available_connections": POOL_SIZE,
                "pool_timeout": POOL_TIMEOUT,
                "max_overflow": MAX_OVERFLOW,
                "error": str(e),
            }

    @staticmethod
    def log_pool_stats():
        """Логирование статистики пула"""
        stats = ConnectionPoolMonitor.get_pool_status()
        logger.debug(f"DB Pool stats: {stats}")

    @staticmethod
    def is_pool_healthy() -> tuple[bool, str]:
        """Проверка здоровья пула соединений"""
        try:
            stats = ConnectionPoolMonitor.get_pool_status()

            # Если есть ошибка в получении статистики
            if "error" in stats:
                return False, f"Pool status error: {stats['error']}"

            # Проверяем что пул не переполнен
            max_connections = POOL_SIZE + MAX_OVERFLOW
            if stats["checked_out"] >= max_connections:
                return (
                    False,
                    f"Pool exhausted: {stats['checked_out']}/{max_connections}",
                )

            # Проверяем что есть доступные соединения
            if stats["available_connections"] <= 0:
                return False, "No available connections"

            # Проверяем количество невалидных соединений (если доступно)
            if stats["invalid"] > POOL_SIZE // 2:
                return False, f"Too many invalid connections: {stats['invalid']}"

            return True, "Pool healthy"

        except Exception as e:
            return False, f"Pool check failed: {e}"


# Настройка PRAGMA для каждого нового соединения
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Настраивает PRAGMA для каждого нового соединения SQLite."""
    cursor = dbapi_connection.cursor()

    # Основные настройки для производительности и надежности
    cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    cursor.execute("PRAGMA synchronous=NORMAL")  # Баланс между скоростью и надежностью
    cursor.execute("PRAGMA cache_size=10000")  # Увеличиваем кеш
    cursor.execute("PRAGMA temp_store=MEMORY")  # Временные данные в памяти
    cursor.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O

    # Настройки для многопользовательского доступа
    cursor.execute("PRAGMA busy_timeout=60000")  # 60 секунд ожидания блокировок
    cursor.execute("PRAGMA wal_autocheckpoint=1000")  # Автоматический checkpoint

    # Настройки для целостности данных
    cursor.execute("PRAGMA foreign_keys=ON")  # Включаем внешние ключи
    cursor.execute("PRAGMA optimize")  # Оптимизация базы

    cursor.close()
    logger.debug("SQLite PRAGMA настройки применены для нового соединения")


# Обновленный DatabaseManager с connection pooling
class DatabaseManager:
    """Улучшенный менеджер базы данных с connection pooling"""

    _lock = threading.RLock()
    _initialization_done = False
    _last_pool_log = time.time()

    @classmethod
    def get_session(cls) -> SQLSession:
        """Получение сессии из пула с мониторингом"""
        try:
            session = Session()

            # Периодически логируем статистику пула
            current_time = time.time()
            if current_time - cls._last_pool_log > 300:  # Каждые 5 минут
                ConnectionPoolMonitor.log_pool_stats()
                cls._last_pool_log = current_time

            return session

        except Exception as e:
            logger.error(f"Ошибка получения сессии из пула: {e}")
            ConnectionPoolMonitor.log_pool_stats()
            raise

    @classmethod
    @contextmanager
    def get_session_context(cls):
        """Context manager для автоматического управления сессией"""
        session = None
        try:
            session = cls.get_session()
            yield session
        except Exception as e:
            if session:
                try:
                    session.rollback()
                except:
                    pass
            logger.error(f"Ошибка в сессии БД: {e}")
            raise
        finally:
            if session:
                try:
                    session.close()
                except Exception as e:
                    logger.warning(f"Ошибка закрытия сессии: {e}")

    @classmethod
    def safe_execute(cls, func, max_retries=3, retry_delay=0.1):
        """Безопасное выполнение операций с retry и connection pooling"""
        last_exception = None

        for attempt in range(max_retries):
            try:
                with cls.get_session_context() as session:
                    result = func(session)
                    session.commit()
                    return result

            except (OperationalError, DisconnectionError) as e:
                last_exception = e
                error_msg = str(e).lower()

                # Специальная обработка ошибок SQLite
                if "database is locked" in error_msg:
                    logger.warning(
                        f"Database locked, retry {attempt + 1}/{max_retries}"
                    )
                    time.sleep(retry_delay * (2**attempt))  # Exponential backoff
                    continue
                elif "no such table" in error_msg:
                    logger.error("Database schema issue, initializing...")
                    cls.ensure_initialized()
                    continue
                else:
                    logger.error(f"Database error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        raise

            except Exception as e:
                logger.error(f"Unexpected error in safe_execute: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    last_exception = e
                    continue
                else:
                    raise

        # Если дошли сюда, все попытки провалились
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("All retry attempts failed")

    @classmethod
    def ensure_initialized(cls):
        """Обеспечение инициализации БД с connection pooling"""
        if cls._initialization_done:
            return

        with cls._lock:
            if cls._initialization_done:
                return

            try:
                # Создаем таблицы если их нет
                Base.metadata.create_all(bind=engine)

                # Простая проверка что база доступна
                try:
                    with cls.get_session_context() as session:
                        session.execute(text("SELECT 1"))
                except Exception as e:
                    logger.warning(f"Initial DB test failed, but continuing: {e}")

                cls._initialization_done = True
                logger.info("Database initialized successfully with connection pooling")

                # Логируем статистику только если получается
                try:
                    ConnectionPoolMonitor.log_pool_stats()
                except Exception as e:
                    logger.debug(f"Could not log pool stats: {e}")

            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                raise

    @classmethod
    def cleanup_connections(cls):
        """Очистка соединений и освобождение ресурсов"""
        try:
            # Закрываем все scoped sessions
            Session.remove()

            # Принудительно очищаем пул
            engine.dispose()

            logger.info("Database connections cleaned up")

        except Exception as e:
            logger.error(f"Error during connection cleanup: {e}")

    @classmethod
    def check_connection_health(cls) -> bool:
        """Проверка здоровья соединений"""
        try:
            with cls.get_session_context() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Connection health check failed: {e}")
            return False


# Ваши существующие модели без изменений
class AdminRole(enum.Enum):
    SUPER_ADMIN = "super_admin"
    MANAGER = "manager"


class Permission(enum.Enum):
    # Пользователи
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"

    # Бронирования
    VIEW_BOOKINGS = "view_bookings"
    CREATE_BOOKINGS = "create_bookings"
    EDIT_BOOKINGS = "edit_bookings"
    DELETE_BOOKINGS = "delete_bookings"
    CONFIRM_BOOKINGS = "confirm_bookings"

    # Тарифы
    VIEW_TARIFFS = "view_tariffs"
    CREATE_TARIFFS = "create_tariffs"
    EDIT_TARIFFS = "edit_tariffs"
    DELETE_TARIFFS = "delete_tariffs"

    # Промокоды
    VIEW_PROMOCODES = "view_promocodes"
    CREATE_PROMOCODES = "create_promocodes"
    EDIT_PROMOCODES = "edit_promocodes"
    DELETE_PROMOCODES = "delete_promocodes"

    # Тикеты
    VIEW_TICKETS = "view_tickets"
    EDIT_TICKETS = "edit_tickets"
    DELETE_TICKETS = "delete_tickets"

    # Уведомления
    VIEW_NOTIFICATIONS = "view_notifications"
    MANAGE_NOTIFICATIONS = "manage_notifications"

    # Рассылки
    VIEW_NEWSLETTERS = "view_newsletters"
    SEND_NEWSLETTERS = "send_newsletters"
    MANAGE_NEWSLETTERS = "manage_newsletters"

    # Управление администраторами (только для super_admin)
    MANAGE_ADMINS = "manage_admins"

    # Дашборд и статистика
    VIEW_DASHBOARD = "view_dashboard"

    # Логирование и мониторинг
    VIEW_LOGS = "view_logs"
    MANAGE_LOGGING = "manage_logging"
    
    # Бэкапы (только для super_admin)
    MANAGE_BACKUPS = "manage_backups"


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    login = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(AdminRole), default=AdminRole.MANAGER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    created_by = Column(Integer, ForeignKey("admins.id"), nullable=True)

    # Связь с создателем - используем remote_side для самореференции
    creator = relationship(
        "Admin",
        remote_side=[id],
        backref="created_admins",
        foreign_keys=[created_by],
        lazy="select",
    )

    # Связь с разрешениями
    permissions = relationship(
        "AdminPermission",
        back_populates="admin",
        cascade="all, delete-orphan",
        foreign_keys="AdminPermission.admin_id",
        lazy="select",
    )

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)

    def has_permission(self, permission: Permission) -> bool:
        """Проверяет, есть ли у админа определенное разрешение"""
        if self.role == AdminRole.SUPER_ADMIN:
            return True  # Супер админ имеет все права

        # Если есть кешированные разрешения, используем их
        if hasattr(self, "permissions") and isinstance(self.permissions, list):
            return permission.value in self.permissions

        # Иначе загружаем из БД
        try:

            def _check_permission(session):
                admin = session.query(Admin).filter(Admin.id == self.id).first()
                if not admin:
                    return False
                return any(
                    ap.permission == permission and ap.granted
                    for ap in admin.permissions
                )

            return DatabaseManager.safe_execute(_check_permission)

        except Exception as e:
            logger.warning(
                f"Error checking permission {permission.value} for admin {self.login}: {e}"
            )
            return False

    def get_permissions_list(self) -> list:
        """Возвращает список разрешений админа"""
        if self.role == AdminRole.SUPER_ADMIN:
            return [p.value for p in Permission]

        # Если есть кешированные разрешения, используем их
        if hasattr(self, "permissions") and isinstance(self.permissions, list):
            return self.permissions

        # Иначе загружаем из БД
        try:

            def _get_permissions(session):
                admin = session.query(Admin).filter(Admin.id == self.id).first()
                if not admin:
                    return []
                return [ap.permission.value for ap in admin.permissions if ap.granted]

            return DatabaseManager.safe_execute(_get_permissions)

        except Exception as e:
            logger.warning(f"Error getting permissions for admin {self.login}: {e}")
            return []

    def safe_get_creator_login(self) -> Optional[str]:
        """Безопасно получает логин создателя"""
        # Если есть кешированный creator_login, используем его
        if hasattr(self, "creator_login"):
            return self.creator_login

        # Иначе загружаем из БД
        try:
            if self.created_by:

                def _get_creator_login(session):
                    creator = (
                        session.query(Admin).filter(Admin.id == self.created_by).first()
                    )
                    return creator.login if creator else None

                return DatabaseManager.safe_execute(_get_creator_login)

            return None

        except Exception as e:
            logger.warning(f"Error getting creator login for admin {self.login}: {e}")
            return None

    def __repr__(self):
        return f"<Admin(id={self.id}, login='{self.login}', role={self.role.value})>"


class AdminPermission(Base):
    __tablename__ = "admin_permissions"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    permission = Column(Enum(Permission), nullable=False)
    granted = Column(Boolean, default=True, nullable=False)
    granted_by = Column(Integer, ForeignKey("admins.id"), nullable=True)
    granted_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ))

    # Связи с явным указанием foreign_keys
    admin = relationship("Admin", back_populates="permissions", foreign_keys=[admin_id])
    granter = relationship("Admin", foreign_keys=[granted_by])

    __table_args__ = (
        UniqueConstraint("admin_id", "permission", name="unique_admin_permission"),
    )


class User(Base):
    """Модель пользователя."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    first_join_time = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False, index=True
    )
    full_name = Column(String, index=True)
    phone = Column(String)
    email = Column(String)
    username = Column(String)
    successful_bookings = Column(Integer, default=0)
    language_code = Column(String, default="ru")
    invited_count = Column(Integer, default=0)
    reg_date = Column(DateTime, index=True)
    agreed_to_terms = Column(Boolean, default=False)
    avatar = Column(String, nullable=True)
    referrer_id = Column(BigInteger, nullable=True)  # Убрать ForeignKey пока что
    admin_comment = Column(Text, nullable=True)  # Комментарий администратора о пользователе

    # Связи
    notifications = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bookings = relationship(
        "Booking",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tickets = relationship(
        "Ticket",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<User {self.telegram_id} - {self.full_name}>"


class Tariff(Base):
    """Модель тарифа."""

    __tablename__ = "tariffs"
    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, index=True)
    description = Column(String(255), default="Описание тарифа", nullable=False)
    price = Column(Float, nullable=False)
    purpose = Column(String(50), nullable=True)
    service_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, index=True)


class Promocode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    discount = Column(Integer, nullable=False)
    usage_quantity = Column(Integer, default=0)  # Количество оставшихся использований
    expiration_date = Column(DateTime(timezone=True), nullable=True, index=True)
    is_active = Column(Boolean, default=False, index=True)

    def __repr__(self) -> str:
        return f"<Promocode(id={self.id}, name='{self.name}', discount={self.discount}%, uses={self.usage_quantity})>"

    @property
    def is_available(self) -> bool:
        """Проверяет, доступен ли промокод для использования."""
        if not self.is_active:
            return False

        if self.expiration_date and self.expiration_date < datetime.now(MOSCOW_TZ):
            return False

        if self.usage_quantity <= 0:
            return False

        return True


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,  # Изменено с BigInteger на Integer
    )
    tariff_id = Column(Integer, ForeignKey("tariffs.id"), nullable=False, index=True)
    visit_date = Column(Date, nullable=False, index=True)
    visit_time = Column(Time, nullable=True)
    duration = Column(Integer, nullable=True)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=True)
    amount = Column(Float, nullable=False)
    payment_id = Column(String(100), nullable=True)
    paid = Column(Boolean, default=False, index=True)
    rubitime_id = Column(String(100), nullable=True)
    confirmed = Column(Boolean, default=False, index=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False, index=True
    )

    # Связи
    user = relationship("User", back_populates="bookings")
    tariff = relationship("Tariff", backref="bookings")
    promocode = relationship("Promocode", backref="promocodes")
    notifications = relationship("Notification", back_populates="booking")

    # Композитные индексы для часто используемых комбинаций
    __table_args__ = (
        Index('idx_bookings_user_paid', 'user_id', 'paid'),
        Index('idx_bookings_date_status', 'visit_date', 'confirmed', 'paid'),
        Index('idx_bookings_user_date', 'user_id', 'visit_date'),
    )


class Newsletter(Base):
    """Модель для хранения истории рассылок."""

    __tablename__ = "newsletters"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    recipient_type = Column(String(50), nullable=False)  # 'all' или 'selected'
    recipient_ids = Column(Text)  # Список telegram_id через запятую
    total_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    photo_count = Column(Integer, default=0)
    status = Column(
        String(50), default="pending"
    )  # 'pending', 'success', 'failed', 'partial'
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(MOSCOW_TZ)
    )

    def __repr__(self):
        return f"<Newsletter(id={self.id}, status={self.status}, recipients={self.total_count})>"


class TicketStatus(enum.Enum):
    """Перечисление для статусов заявки."""

    OPEN = "Открыта"
    IN_PROGRESS = "В работе"
    CLOSED = "Закрыта"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    description = Column(String, nullable=False)
    photo_id = Column(String, nullable=True)  # Фото от пользователя
    response_photo_id = Column(String, nullable=True)  # Фото в ответе от администратора
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False, index=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(MOSCOW_TZ), index=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(MOSCOW_TZ),
        onupdate=lambda: datetime.now(MOSCOW_TZ),
    )

    user = relationship("User", back_populates="tickets")
    notifications = relationship("Notification", back_populates="ticket")

    def __repr__(self) -> str:
        return f"<Ticket(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,  # Изменено с BigInteger на Integer
    )
    message = Column(String, nullable=False)
    target_url = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(MOSCOW_TZ), nullable=False, index=True
    )
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)

    # Связи
    user = relationship("User", back_populates="notifications")
    booking = relationship("Booking", back_populates="notifications")
    ticket = relationship("Ticket", back_populates="notifications")


# Обновленная функция создания админа
def create_admin(admin_login: str, admin_password: str) -> None:
    """Создает главного администратора при первом запуске"""

    def _create_admin_operation(session):
        admin = session.query(Admin).filter_by(login=admin_login).first()
        if admin:
            logger.info(f"Администратор {admin_login} уже существует")
            return

        hashed_password = generate_password_hash(
            admin_password, method="pbkdf2:sha256", salt_length=8
        )

        admin = Admin(
            login=admin_login,
            password=hashed_password,
            role=AdminRole.SUPER_ADMIN,  # Первый админ всегда супер админ
            is_active=True,
        )
        session.add(admin)
        session.commit()
        logger.info(f"Создан главный администратор: {admin_login}")

    DatabaseManager.safe_execute(_create_admin_operation)


def init_db() -> None:
    """Инициализация базы данных с connection pooling"""
    logger.info("Initializing database with connection pooling...")

    try:
        # Инициализируем через DatabaseManager
        DatabaseManager.ensure_initialized()

        # Выполняем оптимизацию базы
        def _optimize_db(session):
            session.execute(text("PRAGMA optimize"))
            session.execute(text("VACUUM"))
            logger.info("База данных оптимизирована")
            return True

        DatabaseManager.safe_execute(_optimize_db)

        # Логируем финальную статистику пула
        stats = ConnectionPoolMonitor.get_pool_status()
        logger.info(f"Database ready. Pool configuration: {stats}")

    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        raise


# Функции для мониторинга и интеграции
def get_db_health() -> dict:
    """Получение статуса здоровья БД и пула для health checks"""
    healthy, message = ConnectionPoolMonitor.is_pool_healthy()
    connection_ok = DatabaseManager.check_connection_health()

    return {
        "pool_healthy": healthy,
        "pool_message": message,
        "connection_ok": connection_ok,
        "pool_stats": ConnectionPoolMonitor.get_pool_status(),
    }


def optimize_database():
    """Оптимизация базы данных с учетом connection pooling"""

    def _optimize(session):
        # Анализ и оптимизация таблиц
        session.execute(text("ANALYZE"))

        # Проверка целостности
        result = session.execute(text("PRAGMA integrity_check")).scalar()
        if result != "ok":
            logger.warning(f"Database integrity check failed: {result}")

        # Очистка статистики
        session.execute(text("PRAGMA optimize"))

        logger.info("Database optimization completed")
        return True

    return DatabaseManager.safe_execute(_optimize)


async def cleanup_database():
    """Очистка ресурсов БД при завершении приложения"""
    logger.info("Cleaning up database connections...")
    DatabaseManager.cleanup_connections()
    logger.info("Database cleanup completed")


# Импорт дополнительных моделей
from models.api_keys import ApiKey, ApiKeyAuditLog, ApiKeyUsage

# Автоматическая инициализация при импорте с обработкой ошибок
try:
    DatabaseManager.ensure_initialized()
    logger.info("Database auto-initialization completed successfully")
except Exception as e:
    logger.warning(f"Database auto-initialization had issues: {e}")
    # Не падаем при импорте, позволяем приложению стартовать
