"""
Конфигурация для pytest - общие фикстуры и настройки
"""
import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Импорты приложения
from main import app
from models.models import get_db, Base, Admin
from config import SECRET_KEY_JWT
from dependencies import get_db as get_db_dependency
from utils.logger import get_logger

logger = get_logger(__name__)

# Настройка тестовой базы данных
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
    },
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    """Переопределение зависимости базы данных для тестов"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Переопределяем зависимость в приложении
app.dependency_overrides[get_db_dependency] = override_get_db

@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для всей тестовой сессии"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_db():
    """Создание и очистка тестовой базы данных"""
    # Создаем таблицы
    Base.metadata.create_all(bind=engine)
    yield
    # Удаляем таблицы после тестов
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(test_db):
    """Создание сессии БД для каждого теста"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(test_db):
    """Создание тестового клиента FastAPI"""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def test_admin(db_session):
    """Создание тестового администратора"""
    from werkzeug.security import generate_password_hash
    
    admin = Admin(
        login="test_admin",
        password_hash=generate_password_hash("test_password"),
        role="super_admin",
        permissions=["manage_users", "manage_bookings", "manage_tickets", "view_dashboard"],
        created_at=pytest.datetime.now()
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture
def auth_token(test_admin):
    """Создание JWT токена для аутентификации"""
    import jwt
    from datetime import datetime, timedelta
    from config import ALGORITHM, ACCESS_TOKEN_EXPIRE_HOURS
    
    payload = {
        "sub": test_admin.login,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    
    token = jwt.encode(payload, SECRET_KEY_JWT, algorithm=ALGORITHM)
    return f"Bearer {token}"

@pytest.fixture
def auth_headers(auth_token):
    """Заголовки для аутентифицированных запросов"""
    return {"Authorization": auth_token}

# Хелперы для тестов
class TestHelpers:
    @staticmethod
    def create_test_user(db_session, telegram_id=12345, full_name="Test User"):
        """Создание тестового пользователя"""
        from models.models import User
        from datetime import datetime
        
        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username="test_user",
            phone="+1234567890",
            email="test@example.com",
            created_at=datetime.now()
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @staticmethod
    def create_test_ticket(db_session, user_id, description="Test ticket"):
        """Создание тестового тикета"""
        from models.models import Ticket, TicketStatus
        from datetime import datetime
        
        ticket = Ticket(
            user_id=user_id,
            description=description,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        return ticket

@pytest.fixture
def helpers():
    """Фикстура с хелперами для тестов"""
    return TestHelpers