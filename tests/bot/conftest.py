"""
Bot test fixtures and configuration.

This module provides pytest fixtures for testing Telegram bot handlers,
including mocks for aiogram components (Bot, Message, CallbackQuery, FSMContext).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, Optional

# Mock aiogram types
class MockUser:
    """Mock Telegram User object."""

    def __init__(self, user_id: int = 12345, username: str = "testuser",
                 language_code: str = "ru", full_name: str = "Test User"):
        self.id = user_id
        self.username = username
        self.language_code = language_code
        self.full_name = full_name
        self.is_bot = False
        self.first_name = full_name.split()[0] if full_name else "Test"
        self.last_name = full_name.split()[1] if len(full_name.split()) > 1 else "User"


class MockChat:
    """Mock Telegram Chat object."""

    def __init__(self, chat_id: int = 12345, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type


class MockMessage:
    """Mock Telegram Message object."""

    def __init__(self, user: MockUser = None, text: str = "",
                 chat: MockChat = None, message_id: int = 1):
        self.from_user = user or MockUser()
        self.text = text
        self.chat = chat or MockChat()
        self.message_id = message_id
        self.content_type = "text"
        self.photo = None

        # Mock async methods
        self.answer = AsyncMock(return_value=self)
        self.edit_text = AsyncMock(return_value=self)
        self.delete = AsyncMock()


class MockCallbackQuery:
    """Mock Telegram CallbackQuery object."""

    def __init__(self, user: MockUser = None, data: str = "",
                 message: MockMessage = None):
        self.from_user = user or MockUser()
        self.data = data
        self.message = message or MockMessage(user=self.from_user)
        self.id = "callback_query_id"

        # Mock async methods
        self.answer = AsyncMock()


class MockBot:
    """Mock aiogram Bot object."""

    def __init__(self):
        self.send_message = AsyncMock()
        self.send_photo = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.delete_message = AsyncMock()
        self.get_file = AsyncMock()
        self.token = "TEST_BOT_TOKEN"
        self.session = MagicMock()


class MockFSMContext:
    """Mock FSM Context for state management."""

    def __init__(self, initial_data: Dict[str, Any] = None):
        self._data = initial_data or {}
        self._state = None

        # Mock async methods
        self.get_data = AsyncMock(return_value=self._data)
        self.update_data = AsyncMock(side_effect=self._update_data)
        self.set_state = AsyncMock(side_effect=self._set_state)
        self.clear = AsyncMock(side_effect=self._clear)
        self.get_state = AsyncMock(return_value=self._state)

    async def _update_data(self, **kwargs):
        """Update FSM data."""
        self._data.update(kwargs)
        self.get_data.return_value = self._data

    async def _set_state(self, state):
        """Set FSM state."""
        self._state = state
        self.get_state.return_value = state

    async def _clear(self):
        """Clear FSM data and state."""
        self._data = {}
        self._state = None
        self.get_data.return_value = {}
        self.get_state.return_value = None


class MockAPIClient:
    """Mock API Client for backend communication."""

    def __init__(self):
        # User endpoints
        self.get_user_by_telegram_id = AsyncMock()
        self.create_user = AsyncMock()
        self.update_user = AsyncMock()

        # Booking endpoints
        self.get_tariffs = AsyncMock()
        self.create_booking = AsyncMock()
        self.get_booking_by_id = AsyncMock()
        self.cancel_booking = AsyncMock()

        # Ticket endpoints
        self.create_ticket = AsyncMock()
        self.get_user_tickets = AsyncMock()

        # Notification endpoints
        self.create_notification = AsyncMock()

        # Payment endpoints
        self.create_payment = AsyncMock()
        self.check_payment_status = AsyncMock()

        # Promo code endpoints
        self.validate_promocode = AsyncMock()

        # Internal method
        self._make_request = AsyncMock()


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def mock_user():
    """Fixture providing a mock Telegram user."""
    return MockUser()


@pytest.fixture
def mock_banned_user():
    """Fixture providing a mock banned Telegram user."""
    return MockUser(user_id=99999, username="banneduser", full_name="Banned User")


@pytest.fixture
def mock_chat():
    """Fixture providing a mock Telegram chat."""
    return MockChat()


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Fixture providing a mock Telegram message."""
    return MockMessage(user=mock_user, chat=mock_chat)


@pytest.fixture
def mock_callback(mock_user, mock_message):
    """Fixture providing a mock callback query."""
    return MockCallbackQuery(user=mock_user, message=mock_message)


@pytest.fixture
def mock_bot():
    """Fixture providing a mock Bot instance."""
    return MockBot()


@pytest.fixture
def mock_state():
    """Fixture providing a mock FSM context."""
    return MockFSMContext()


@pytest.fixture
def mock_api_client():
    """Fixture providing a mock API client."""
    return MockAPIClient()


@pytest.fixture
def mock_api_client_with_data(mock_api_client):
    """
    Fixture providing a mock API client with sample data responses.

    This fixture configures the API client with typical successful responses
    for common operations like user lookup, tariff retrieval, etc.
    """
    # Configure user responses
    mock_api_client.get_user_by_telegram_id.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "full_name": "Test User",
        "username": "testuser",
        "phone": "+7 900 123-45-67",
        "email": "test@example.com",
        "is_banned": False,
        "referral_code": "TEST123",
        "balance": 0.0,
    }

    # Configure tariff responses
    mock_api_client.get_tariffs.return_value = [
        {
            "id": 1,
            "name": "Рабочее место на день",
            "price": 500.0,
            "duration_hours": 8,
            "requires_payment": True,
        },
        {
            "id": 2,
            "name": "Переговорная комната",
            "price": 0.0,
            "duration_hours": 1,
            "requires_payment": False,
        },
    ]

    # Configure booking responses
    mock_api_client.create_booking.return_value = {
        "id": 1,
        "user_id": 1,
        "tariff_id": 1,
        "start_time": "2025-01-15T10:00:00",
        "end_time": "2025-01-15T18:00:00",
        "status": "PENDING",
        "total_price": 500.0,
    }

    # Configure ticket responses
    mock_api_client.create_ticket.return_value = {
        "id": 1,
        "user_id": 1,
        "description": "Test ticket",
        "status": "OPEN",
        "photo_id": None,
    }

    return mock_api_client


@pytest.fixture
def sample_user_data():
    """Fixture providing sample user data for registration."""
    return {
        "telegram_id": 12345,
        "full_name": "Иван Иванов",
        "phone": "+7 900 123-45-67",
        "email": "ivan@example.com",
        "username": "testuser",
    }


@pytest.fixture
def sample_tariff_data():
    """Fixture providing sample tariff data."""
    return {
        "id": 1,
        "name": "Рабочее место на день",
        "price": 500.0,
        "duration_hours": 8,
        "requires_payment": True,
        "description": "Удобное рабочее место",
    }


@pytest.fixture
def sample_booking_data():
    """Fixture providing sample booking data."""
    return {
        "tariff_id": 1,
        "start_date": "15.01.2025",
        "start_time": "10:00",
        "duration_hours": 8,
        "promocode": None,
    }


@pytest.fixture
def sample_ticket_data():
    """Fixture providing sample ticket data."""
    return {
        "description": "У меня проблема с доступом в коворкинг",
        "photo_id": None,
    }


@pytest.fixture(autouse=True)
def mock_get_api_client(mock_api_client_with_data):
    """
    Auto-use fixture that patches get_api_client globally.

    This ensures all bot handlers use the mocked API client
    instead of making real HTTP requests.
    """
    with patch('utils.api_client.get_api_client',
               return_value=mock_api_client_with_data):
        yield mock_api_client_with_data


@pytest.fixture(autouse=True)
def mock_get_bot(mock_bot):
    """
    Auto-use fixture that patches get_bot globally.

    This ensures all bot handlers use the mocked bot instance.
    """
    with patch('utils.bot_instance.get_bot', return_value=mock_bot):
        yield mock_bot


@pytest.fixture
def freeze_time():
    """Fixture to freeze time for consistent datetime testing."""
    frozen_datetime = datetime(2025, 1, 15, 10, 0, 0)

    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = frozen_datetime
        mock_datetime.fromisoformat = datetime.fromisoformat
        yield frozen_datetime
