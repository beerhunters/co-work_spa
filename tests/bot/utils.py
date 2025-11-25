"""
Test utility functions for bot testing.

This module provides helper functions for common testing operations like:
- Assertions on message/callback responses
- Creating test data with variations
- Simulating FSM flows
- Validating error handling
"""

from typing import Dict, Any, Optional, List
from unittest.mock import AsyncMock
import re


# ============================================================================
# Assertion Helpers
# ============================================================================

def assert_message_sent(mock_message: AsyncMock, expected_text: str = None,
                        contains: str = None, reply_markup_present: bool = None):
    """
    Assert that a message was sent with expected properties.

    Args:
        mock_message: Mock message object with answer() method
        expected_text: Exact text expected (optional)
        contains: Text that should be contained in message (optional)
        reply_markup_present: Whether reply_markup should be present (optional)

    Example:
        assert_message_sent(message, contains="Успешно")
        assert_message_sent(message, expected_text="Привет", reply_markup_present=True)
    """
    mock_message.answer.assert_called()
    call_kwargs = mock_message.answer.call_args[1] if mock_message.answer.call_args else {}
    call_args = mock_message.answer.call_args[0] if mock_message.answer.call_args else []

    sent_text = call_args[0] if call_args else call_kwargs.get('text', '')

    if expected_text is not None:
        assert sent_text == expected_text, \
            f"Expected text '{expected_text}', but got '{sent_text}'"

    if contains is not None:
        assert contains in sent_text, \
            f"Expected text to contain '{contains}', but got '{sent_text}'"

    if reply_markup_present is not None:
        has_markup = 'reply_markup' in call_kwargs and call_kwargs['reply_markup'] is not None
        assert has_markup == reply_markup_present, \
            f"Expected reply_markup_present={reply_markup_present}, but got {has_markup}"


def assert_message_edited(mock_callback: AsyncMock, expected_text: str = None,
                          contains: str = None):
    """
    Assert that a callback query edited a message with expected properties.

    Args:
        mock_callback: Mock callback query object
        expected_text: Exact text expected (optional)
        contains: Text that should be contained in message (optional)

    Example:
        assert_message_edited(callback, contains="Ошибка")
    """
    mock_callback.message.edit_text.assert_called()
    call_kwargs = mock_callback.message.edit_text.call_args[1]
    call_args = mock_callback.message.edit_text.call_args[0]

    edited_text = call_args[0] if call_args else call_kwargs.get('text', '')

    if expected_text is not None:
        assert edited_text == expected_text, \
            f"Expected edited text '{expected_text}', but got '{edited_text}'"

    if contains is not None:
        assert contains in edited_text, \
            f"Expected edited text to contain '{contains}', but got '{edited_text}'"


def assert_callback_answered(mock_callback: AsyncMock, text: str = None,
                             show_alert: bool = None):
    """
    Assert that a callback query was answered.

    Args:
        mock_callback: Mock callback query object
        text: Expected answer text (optional)
        show_alert: Whether alert should be shown (optional)

    Example:
        assert_callback_answered(callback, text="Готово", show_alert=False)
    """
    mock_callback.answer.assert_called()

    if text is not None or show_alert is not None:
        call_kwargs = mock_callback.answer.call_args[1] if mock_callback.answer.call_args else {}

        if text is not None:
            assert call_kwargs.get('text') == text, \
                f"Expected callback text '{text}', but got '{call_kwargs.get('text')}'"

        if show_alert is not None:
            assert call_kwargs.get('show_alert') == show_alert, \
                f"Expected show_alert={show_alert}, but got {call_kwargs.get('show_alert')}"


def assert_state_cleared(mock_state: AsyncMock):
    """
    Assert that FSM state was cleared.

    Args:
        mock_state: Mock FSM context

    Example:
        assert_state_cleared(state)
    """
    mock_state.clear.assert_called_once()


def assert_state_set(mock_state: AsyncMock, expected_state: str = None):
    """
    Assert that FSM state was set.

    Args:
        mock_state: Mock FSM context
        expected_state: Expected state name (optional)

    Example:
        assert_state_set(state, "Registration:FULL_NAME")
    """
    mock_state.set_state.assert_called()

    if expected_state is not None:
        call_args = mock_state.set_state.call_args[0]
        actual_state = str(call_args[0]) if call_args else None
        assert expected_state in str(actual_state), \
            f"Expected state '{expected_state}', but got '{actual_state}'"


def assert_error_message_sent(mock_message: AsyncMock, error_key: str = None):
    """
    Assert that an error message was sent.

    Args:
        mock_message: Mock message object
        error_key: Expected error key from localization (optional)

    Example:
        assert_error_message_sent(message, error_key="invalid_phone")
    """
    mock_message.answer.assert_called()
    call_args = mock_message.answer.call_args[0]
    sent_text = call_args[0] if call_args else ""

    # Error messages typically contain emojis like 🚫, ⚠️, ❌
    error_indicators = ["🚫", "⚠️", "❌", "ошибк", "Ошибк", "невозможно", "неверн"]
    has_error_indicator = any(indicator in sent_text for indicator in error_indicators)

    assert has_error_indicator, \
        f"Expected error message but got: '{sent_text}'"

    if error_key:
        # Convert error_key to a pattern we might find in the message
        # e.g., "invalid_phone" -> "телефон" or "phone"
        assert error_key in sent_text.lower() or \
               any(word in sent_text.lower() for word in error_key.split('_')), \
            f"Expected error about '{error_key}' but got: '{sent_text}'"


def assert_api_called(mock_api_client: AsyncMock, method: str,
                      times: int = 1, with_args: Dict[str, Any] = None):
    """
    Assert that an API client method was called.

    Args:
        mock_api_client: Mock API client
        method: Method name (e.g., "create_user")
        times: Expected number of calls (default: 1)
        with_args: Expected arguments passed (optional)

    Example:
        assert_api_called(api_client, "create_user", times=1,
                         with_args={"telegram_id": 12345})
    """
    method_mock = getattr(mock_api_client, method)
    assert method_mock.call_count == times, \
        f"Expected {method} to be called {times} times, but was called {method_mock.call_count} times"

    if with_args:
        call_kwargs = method_mock.call_args[1] if method_mock.call_args else {}
        call_args_list = method_mock.call_args[0] if method_mock.call_args else []

        # Check if with_args are in either positional or keyword arguments
        for key, expected_value in with_args.items():
            if call_kwargs.get(key) == expected_value:
                continue
            # Check if it's in a dict passed as positional argument
            found = False
            for arg in call_args_list:
                if isinstance(arg, dict) and arg.get(key) == expected_value:
                    found = True
                    break
            assert found or call_kwargs.get(key) == expected_value, \
                f"Expected {method} to be called with {key}={expected_value}"


# ============================================================================
# Test Data Builders
# ============================================================================

def create_user_data(telegram_id: int = 12345, full_name: str = "Test User",
                     phone: str = "+7 900 123-45-67", email: str = "test@example.com",
                     **kwargs) -> Dict[str, Any]:
    """
    Create user data dict with sensible defaults.

    Args:
        telegram_id: Telegram user ID
        full_name: User's full name
        phone: User's phone number
        email: User's email
        **kwargs: Additional fields to override

    Returns:
        Dict with user data

    Example:
        user_data = create_user_data(telegram_id=99999, email="custom@test.com")
    """
    data = {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "phone": phone,
        "email": email,
        "username": kwargs.get("username", "testuser"),
        "is_banned": kwargs.get("is_banned", False),
        "referral_code": kwargs.get("referral_code", f"REF{telegram_id}"),
        "balance": kwargs.get("balance", 0.0),
    }
    data.update(kwargs)
    return data


def create_tariff_data(tariff_id: int = 1, name: str = "Рабочее место на день",
                       price: float = 500.0, duration_hours: int = 8,
                       requires_payment: bool = True, **kwargs) -> Dict[str, Any]:
    """
    Create tariff data dict with sensible defaults.

    Args:
        tariff_id: Tariff ID
        name: Tariff name
        price: Price in rubles
        duration_hours: Duration in hours
        requires_payment: Whether payment is required
        **kwargs: Additional fields

    Returns:
        Dict with tariff data

    Example:
        tariff = create_tariff_data(price=1000.0, duration_hours=12)
    """
    data = {
        "id": tariff_id,
        "name": name,
        "price": price,
        "duration_hours": duration_hours,
        "requires_payment": requires_payment,
        "description": kwargs.get("description", f"Тариф {name}"),
    }
    data.update(kwargs)
    return data


def create_booking_data(booking_id: int = 1, user_id: int = 1,
                        tariff_id: int = 1, status: str = "PENDING",
                        total_price: float = 500.0, **kwargs) -> Dict[str, Any]:
    """
    Create booking data dict with sensible defaults.

    Args:
        booking_id: Booking ID
        user_id: User ID
        tariff_id: Tariff ID
        status: Booking status
        total_price: Total price
        **kwargs: Additional fields

    Returns:
        Dict with booking data

    Example:
        booking = create_booking_data(status="CONFIRMED")
    """
    data = {
        "id": booking_id,
        "user_id": user_id,
        "tariff_id": tariff_id,
        "status": status,
        "total_price": total_price,
        "start_time": kwargs.get("start_time", "2025-01-15T10:00:00"),
        "end_time": kwargs.get("end_time", "2025-01-15T18:00:00"),
    }
    data.update(kwargs)
    return data


def create_ticket_data(ticket_id: int = 1, user_id: int = 1,
                       description: str = "Test ticket", status: str = "OPEN",
                       **kwargs) -> Dict[str, Any]:
    """
    Create ticket data dict with sensible defaults.

    Args:
        ticket_id: Ticket ID
        user_id: User ID
        description: Ticket description
        status: Ticket status
        **kwargs: Additional fields

    Returns:
        Dict with ticket data

    Example:
        ticket = create_ticket_data(description="Проблема с доступом")
    """
    data = {
        "id": ticket_id,
        "user_id": user_id,
        "description": description,
        "status": status,
        "photo_id": kwargs.get("photo_id"),
        "created_at": kwargs.get("created_at", "2025-01-15T10:00:00Z"),
    }
    data.update(kwargs)
    return data


# ============================================================================
# FSM Flow Simulation
# ============================================================================

async def simulate_registration_flow(handler_functions: Dict[str, Any],
                                     mock_message: AsyncMock,
                                     mock_state: AsyncMock,
                                     user_data: Dict[str, Any]) -> None:
    """
    Simulate a complete registration flow through FSM states.

    Args:
        handler_functions: Dict mapping state names to handler functions
        mock_message: Mock message object
        mock_state: Mock FSM context
        user_data: User data to use in registration

    Example:
        await simulate_registration_flow(
            handler_functions={
                "agreement": process_agreement,
                "full_name": process_full_name,
                ...
            },
            mock_message=message,
            mock_state=state,
            user_data={"full_name": "Иван", ...}
        )
    """
    # Agreement
    if "agreement" in handler_functions:
        mock_callback = mock_message
        mock_callback.data = "accept_agreement"
        await handler_functions["agreement"](mock_callback, mock_state)

    # Full name
    if "full_name" in handler_functions:
        mock_message.text = user_data.get("full_name", "Test User")
        await handler_functions["full_name"](mock_message, mock_state)

    # Phone
    if "phone" in handler_functions:
        mock_message.text = user_data.get("phone", "+7 900 123-45-67")
        await handler_functions["phone"](mock_message, mock_state)

    # Email
    if "email" in handler_functions:
        mock_message.text = user_data.get("email", "test@example.com")
        await handler_functions["email"](mock_message, mock_state)


# ============================================================================
# Validation Helpers
# ============================================================================

def is_valid_phone_format(phone: str) -> bool:
    """
    Check if phone number matches expected format.

    Args:
        phone: Phone number string

    Returns:
        True if valid format

    Example:
        assert is_valid_phone_format("+7 900 123-45-67")
    """
    # Russian phone format: +7 XXX XXX-XX-XX or similar
    pattern = r'^\+7\s?\d{3}\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}$'
    return bool(re.match(pattern, phone))


def is_valid_email_format(email: str) -> bool:
    """
    Check if email matches expected format.

    Args:
        email: Email string

    Returns:
        True if valid format

    Example:
        assert is_valid_email_format("test@example.com")
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_valid_date_format(date_str: str) -> bool:
    """
    Check if date string matches DD.MM.YYYY format.

    Args:
        date_str: Date string

    Returns:
        True if valid format

    Example:
        assert is_valid_date_format("15.01.2025")
    """
    pattern = r'^\d{2}\.\d{2}\.\d{4}$'
    return bool(re.match(pattern, date_str))


def is_valid_time_format(time_str: str) -> bool:
    """
    Check if time string matches HH:MM format.

    Args:
        time_str: Time string

    Returns:
        True if valid format

    Example:
        assert is_valid_time_format("10:00")
    """
    pattern = r'^\d{2}:\d{2}$'
    return bool(re.match(pattern, time_str))


# ============================================================================
# Error Simulation
# ============================================================================

def simulate_api_error(mock_api_client: AsyncMock, method: str,
                       error_type: str = "network", error_message: str = None):
    """
    Configure mock API client to raise an error.

    Args:
        mock_api_client: Mock API client
        method: Method name to raise error on
        error_type: Type of error ("network", "not_found", "validation", "server")
        error_message: Custom error message (optional)

    Example:
        simulate_api_error(api_client, "create_user", error_type="network")
    """
    method_mock = getattr(mock_api_client, method)

    if error_type == "network":
        method_mock.side_effect = ConnectionError(
            error_message or "Network connection failed"
        )
    elif error_type == "not_found":
        method_mock.return_value = None
    elif error_type == "validation":
        method_mock.return_value = {
            "error": error_message or "Validation error",
            "details": "Invalid input data"
        }
    elif error_type == "server":
        method_mock.side_effect = Exception(
            error_message or "Internal server error"
        )
    else:
        method_mock.side_effect = Exception(error_message or "Unknown error")


def simulate_timeout_error(mock_api_client: AsyncMock, method: str):
    """
    Configure mock API client to raise a timeout error.

    Args:
        mock_api_client: Mock API client
        method: Method name to raise timeout on

    Example:
        simulate_timeout_error(api_client, "create_booking")
    """
    import asyncio
    method_mock = getattr(mock_api_client, method)
    method_mock.side_effect = asyncio.TimeoutError("Request timeout")
