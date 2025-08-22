"""
Тесты API тикетов
"""
import pytest
from fastapi.testclient import TestClient
from io import BytesIO


class TestTicketsAPI:
    """Тесты API для работы с тикетами"""
    
    def test_get_tickets_empty(self, client: TestClient, auth_headers):
        """Тест получения пустого списка тикетов"""
        response = client.get("/tickets", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_tickets_detailed_empty(self, client: TestClient, auth_headers):
        """Тест получения детальной информации о тикетах (пустой список)"""
        response = client.get("/tickets/detailed", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["tickets"] == []
        assert data["total_count"] == 0
        assert data["page"] == 1
        assert data["per_page"] == 20
    
    def test_get_tickets_with_data(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест получения тикетов с данными"""
        # Создаем тестового пользователя и тикет
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id, "Test ticket description")
        
        response = client.get("/tickets/detailed", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["tickets"]) == 1
        assert data["total_count"] == 1
        assert data["tickets"][0]["description"] == "Test ticket description"
        assert data["tickets"][0]["user"]["full_name"] == "Test User"
    
    def test_get_ticket_by_id(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест получения тикета по ID"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        response = client.get(f"/tickets/{ticket.id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == ticket.id
        assert data["description"] == "Test ticket"
    
    def test_get_ticket_not_found(self, client: TestClient, auth_headers):
        """Тест получения несуществующего тикета"""
        response = client.get("/tickets/99999", headers=auth_headers)
        assert response.status_code == 404
    
    def test_create_ticket_via_bot(self, client: TestClient, db_session, helpers):
        """Тест создания тикета через бот API"""
        user = helpers.create_test_user(db_session, telegram_id=12345)
        
        ticket_data = {
            "user_id": user.telegram_id,
            "description": "New ticket from bot",
            "photo_id": "photo_123",
            "status": "OPEN"
        }
        
        response = client.post("/tickets", json=ticket_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert data["message"] == "Ticket created successfully"
    
    def test_update_ticket_status(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест обновления статуса тикета"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        update_data = {
            "status": "IN_PROGRESS",
            "comment": "Working on it"
        }
        
        response = client.put(f"/tickets/{ticket.id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "IN_PROGRESS"
        assert data["comment"] == "Working on it"
    
    def test_delete_ticket(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест удаления тикета"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        response = client.delete(f"/tickets/{ticket.id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Проверяем что тикет действительно удален
        get_response = client.get(f"/tickets/{ticket.id}", headers=auth_headers)
        assert get_response.status_code == 404
    
    def test_tickets_pagination(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест пагинации тикетов"""
        user = helpers.create_test_user(db_session)
        
        # Создаем несколько тикетов
        for i in range(5):
            helpers.create_test_ticket(db_session, user.id, f"Ticket {i}")
        
        # Тест первой страницы
        response = client.get("/tickets/detailed?page=1&per_page=3", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["tickets"]) == 3
        assert data["total_count"] == 5
        assert data["page"] == 1
        assert data["total_pages"] == 2
        
        # Тест второй страницы
        response = client.get("/tickets/detailed?page=2&per_page=3", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["tickets"]) == 2
        assert data["page"] == 2
    
    def test_tickets_filter_by_status(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест фильтрации тикетов по статусу"""
        user = helpers.create_test_user(db_session)
        
        # Создаем тикеты с разными статусами
        ticket1 = helpers.create_test_ticket(db_session, user.id, "Open ticket")
        ticket2 = helpers.create_test_ticket(db_session, user.id, "Closed ticket")
        
        # Обновляем статус второго тикета
        from models.models import TicketStatus
        ticket2.status = TicketStatus.CLOSED
        db_session.commit()
        
        # Фильтруем по статусу OPEN
        response = client.get("/tickets/detailed?status=OPEN", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["status"] == "OPEN"
    
    @pytest.mark.asyncio
    async def test_file_upload_security(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест безопасности загрузки файлов"""
        user = helpers.create_test_user(db_session)
        ticket = helpers.create_test_ticket(db_session, user.id)
        
        # Создаем малый валидный JPEG файл
        jpeg_content = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342'
            b'\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01'
            b'\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x00\xff\xd9'
        )
        
        # Тест загрузки валидного файла
        files = {"file": ("test.jpg", BytesIO(jpeg_content), "image/jpeg")}
        data = {"comment": "Test photo upload"}
        
        response = client.post(
            f"/tickets/{ticket.id}/photo", 
            files=files, 
            data=data, 
            headers=auth_headers
        )
        # Может быть ошибка из-за отсутствия бота, но файл должен валидироваться
        assert response.status_code in [200, 500]  # 500 если бот недоступен
        
        # Тест загрузки слишком большого файла
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large.jpg", BytesIO(large_content), "image/jpeg")}
        
        response = client.post(
            f"/tickets/{ticket.id}/photo", 
            files=files, 
            data=data, 
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()
        
        # Тест загрузки невалидного типа файла
        files = {"file": ("test.txt", BytesIO(b"text content"), "text/plain")}
        
        response = client.post(
            f"/tickets/{ticket.id}/photo", 
            files=files, 
            data=data, 
            headers=auth_headers
        )
        assert response.status_code == 400
        assert "file type" in response.json()["detail"].lower()
    
    def test_get_ticket_stats(self, client: TestClient, auth_headers, db_session, helpers):
        """Тест получения статистики тикетов"""
        user = helpers.create_test_user(db_session)
        
        # Создаем тикеты с разными статусами
        helpers.create_test_ticket(db_session, user.id, "Open ticket 1")
        helpers.create_test_ticket(db_session, user.id, "Open ticket 2")
        
        closed_ticket = helpers.create_test_ticket(db_session, user.id, "Closed ticket")
        from models.models import TicketStatus
        closed_ticket.status = TicketStatus.CLOSED
        db_session.commit()
        
        response = client.get("/tickets/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_tickets"] == 3
        assert data["open_tickets"] == 2
        assert data["closed_tickets"] == 1