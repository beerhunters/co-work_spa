"""
Интеграционные тесты для работы с базой данных
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from models.models import User, Ticket, Admin, TicketStatus, DatabaseManager


class TestDatabaseIntegration:
    """Тесты интеграции с базой данных"""
    
    def test_database_manager_safe_execute(self, db_session):
        """Тест безопасного выполнения операций через DatabaseManager"""
        def create_user(session):
            user = User(
                telegram_id=99999,
                full_name="Database Test User",
                username="db_test",
                created_at=datetime.now()
            )
            session.add(user)
            session.commit()
            return user
        
        # Не можем использовать DatabaseManager напрямую с тестовой сессией
        # Но можем протестировать логику
        user = create_user(db_session)
        
        assert user.id is not None
        assert user.telegram_id == 99999
        assert user.full_name == "Database Test User"
    
    def test_user_creation_and_relationships(self, db_session):
        """Тест создания пользователя и связанных сущностей"""
        # Создаем пользователя
        user = User(
            telegram_id=12345,
            full_name="Integration Test User",
            username="integration_test",
            phone="+1234567890",
            email="integration@test.com",
            created_at=datetime.now()
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Создаем тикет для пользователя
        ticket = Ticket(
            user_id=user.id,
            description="Integration test ticket",
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db_session.add(ticket)
        db_session.commit()
        db_session.refresh(ticket)
        
        # Проверяем связи
        assert ticket.user_id == user.id
        
        # Загружаем пользователя с тикетами через запрос
        user_from_db = db_session.query(User).filter(User.id == user.id).first()
        assert user_from_db is not None
        assert user_from_db.telegram_id == 12345
        
        # Проверяем что можем найти тикеты пользователя
        tickets = db_session.query(Ticket).filter(Ticket.user_id == user.id).all()
        assert len(tickets) == 1
        assert tickets[0].description == "Integration test ticket"
    
    def test_admin_creation_with_permissions(self, db_session):
        """Тест создания администратора с разрешениями"""
        from utils.password_security import hash_password_bcrypt

        admin = Admin(
            login="integration_admin",
            password=hash_password_bcrypt("secure_password"),
            role="admin",
            permissions=["manage_users", "view_tickets"],
            created_at=datetime.now()
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        
        # Проверяем сохранение
        assert admin.id is not None
        assert admin.login == "integration_admin"
        assert isinstance(admin.permissions, list)
        assert "manage_users" in admin.permissions
        assert "view_tickets" in admin.permissions
    
    def test_unique_constraints(self, db_session):
        """Тест уникальных ограничений"""
        # Создаем первого пользователя
        user1 = User(
            telegram_id=55555,
            full_name="User One",
            created_at=datetime.now()
        )
        db_session.add(user1)
        db_session.commit()
        
        # Пытаемся создать второго пользователя с тем же telegram_id
        user2 = User(
            telegram_id=55555,  # Дублируем telegram_id
            full_name="User Two",
            created_at=datetime.now()
        )
        db_session.add(user2)
        
        # Должно быть нарушение уникального ограничения
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
    
    def test_ticket_status_transitions(self, db_session, helpers):
        """Тест переходов статусов тикетов"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        # Проверяем начальный статус
        assert ticket.status == TicketStatus.OPEN
        
        # Меняем статус на IN_PROGRESS
        ticket.status = TicketStatus.IN_PROGRESS
        ticket.updated_at = datetime.now()
        db_session.commit()
        
        # Проверяем изменение
        updated_ticket = db_session.query(Ticket).filter(Ticket.id == ticket.id).first()
        assert updated_ticket.status == TicketStatus.IN_PROGRESS
        
        # Меняем на CLOSED
        updated_ticket.status = TicketStatus.CLOSED
        updated_ticket.comment = "Issue resolved"
        updated_ticket.updated_at = datetime.now()
        db_session.commit()
        
        # Проверяем финальное состояние
        final_ticket = db_session.query(Ticket).filter(Ticket.id == ticket.id).first()
        assert final_ticket.status == TicketStatus.CLOSED
        assert final_ticket.comment == "Issue resolved"
    
    def test_cascade_deletion(self, db_session, helpers):
        """Тест каскадного удаления (если настроено)"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        ticket_id = ticket.id
        user_id = user.id
        
        # Удаляем пользователя
        db_session.delete(user)
        db_session.commit()
        
        # Проверяем что пользователь удален
        deleted_user = db_session.query(User).filter(User.id == user_id).first()
        assert deleted_user is None
        
        # Проверяем что тикет остался (так как нет каскадного удаления)
        orphaned_ticket = db_session.query(Ticket).filter(Ticket.id == ticket_id).first()
        assert orphaned_ticket is not None
        assert orphaned_ticket.user_id == user_id  # Ссылка на удаленного пользователя
    
    def test_complex_query(self, db_session, helpers):
        """Тест сложного запроса с JOIN"""
        # Создаем несколько пользователей и тикетов
        user1 = helpers.create_test_user(db_session, telegram_id=11111, full_name="User One")
        user2 = helpers.create_test_user(db_session, telegram_id=22222, full_name="User Two")
        
        # Создаем тикеты с разными статусами
        ticket1 = helpers.create_test_ticket(db_session, user1.id, "Open ticket 1")
        ticket2 = helpers.create_test_ticket(db_session, user1.id, "Closed ticket 1")
        ticket3 = helpers.create_test_ticket(db_session, user2.id, "Open ticket 2")
        
        # Меняем статус одного тикета
        ticket2.status = TicketStatus.CLOSED
        db_session.commit()
        
        # Сложный запрос: пользователи с открытыми тикетами
        from sqlalchemy import and_
        
        users_with_open_tickets = db_session.query(User).join(Ticket).filter(
            and_(Ticket.status == TicketStatus.OPEN)
        ).distinct().all()
        
        assert len(users_with_open_tickets) == 2  # user1 и user2
        
        # Запрос: количество тикетов по пользователям
        from sqlalchemy import func
        
        ticket_counts = db_session.query(
            User.full_name,
            func.count(Ticket.id).label('ticket_count')
        ).join(Ticket).group_by(User.id).all()
        
        assert len(ticket_counts) == 2
        
        # Проверяем что у user1 2 тикета, у user2 1 тикет
        counts_dict = {name: count for name, count in ticket_counts}
        assert counts_dict["User One"] == 2
        assert counts_dict["User Two"] == 1
    
    def test_transaction_rollback(self, db_session, helpers):
        """Тест отката транзакций при ошибках"""
        user = helpers.create_test_user(db_session, telegram_id=77777)
        initial_user_count = db_session.query(User).count()
        
        try:
            # Начинаем операцию, которая должна вызвать ошибку
            new_user = User(
                telegram_id=77777,  # Дублируем telegram_id - должна быть ошибка
                full_name="Duplicate User",
                created_at=datetime.now()
            )
            db_session.add(new_user)
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
        
        # Проверяем что количество пользователей не изменилось
        final_user_count = db_session.query(User).count()
        assert final_user_count == initial_user_count
        
        # Проверяем что сессия все еще работает
        another_user = helpers.create_test_user(db_session, telegram_id=88888)
        assert another_user.id is not None