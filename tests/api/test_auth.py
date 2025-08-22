"""
Тесты аутентификации и авторизации
"""
import pytest
from fastapi.testclient import TestClient


class TestAuth:
    """Тесты системы аутентификации"""
    
    def test_login_success(self, client: TestClient, test_admin):
        """Тест успешного входа"""
        response = client.post(
            "/auth/login",
            json={
                "login": "test_admin",
                "password": "test_password"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self, client: TestClient, test_admin):
        """Тест входа с неверными данными"""
        response = client.post(
            "/auth/login",
            json={
                "login": "test_admin",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Тест входа несуществующего пользователя"""
        response = client.post(
            "/auth/login",
            json={
                "login": "nonexistent",
                "password": "password"
            }
        )
        
        assert response.status_code == 401
    
    def test_protected_endpoint_without_token(self, client: TestClient):
        """Тест доступа к защищенному эндпоинту без токена"""
        response = client.get("/users")
        assert response.status_code == 401
    
    def test_protected_endpoint_with_valid_token(self, client: TestClient, auth_headers):
        """Тест доступа к защищенному эндпоинту с валидным токеном"""
        response = client.get("/users", headers=auth_headers)
        assert response.status_code == 200
    
    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Тест доступа с невалидным токеном"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/users", headers=headers)
        assert response.status_code == 401