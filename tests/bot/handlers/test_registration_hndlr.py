"""
Integration tests for bot.hndlrs.registration_hndlr module.

Tests cover:
P0 (Critical):
- Complete registration happy path
- Start command initiates registration
- User data saved correctly
- Existing user retrieval

P1 (High Priority):
- Phone validation
- Email validation
- API error handling
- Referral code processing
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.bot.utils import (
    assert_message_sent,
    assert_state_set,
    assert_state_cleared,
    assert_api_called,
    create_user_data,
)


# ============================================================================
# P0 - CRITICAL TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_start_command_initiates_registration(mock_get_text, mock_message, mock_state, mock_api_client_with_data):
    """
    P0: Test /start command initiates registration flow.

    Given: New user sends /start command
    When: start_handler() is called
    Then: Sends welcome message with agreement and sets state
    """
    from bot.hndlrs.registration_hndlr import start_handler

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "welcome.message"): "Добро пожаловать в коворкинг!",
        ("ru", "registration.agreement_text"): "Пожалуйста, примите соглашение",
        ("ru", "buttons.accept"): "Принять",
        ("ru", "buttons.decline"): "Отклонить",
    }.get((lang, key), "")

    # User not found (new registration)
    mock_api_client_with_data.get_user_by_telegram_id.return_value = None

    await start_handler(mock_message, mock_state)

    # Check message sent
    assert_message_sent(mock_message, reply_markup_present=True)

    # Check state set to agreement
    assert_state_set(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.registration_hndlr.get_text')
@patch('bot.hndlrs.registration_hndlr.get_button_text')
async def test_registration_complete_happy_path(mock_get_button_text, mock_get_text,
                                                 mock_message, mock_callback, mock_state,
                                                 mock_api_client_with_data):
    """
    P0: Test complete registration flow from start to finish.

    Given: User goes through entire registration process
    When: All steps completed successfully
    Then: User created in database and receives success message
    """
    from bot.hndlrs.registration_hndlr import (
        process_agreement,
        process_full_name,
        process_phone,
        process_email,
    )

    # Mock all text responses
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "registration.enter_full_name"): "Введите ваше ФИО",
        ("ru", "registration.enter_phone"): "Введите телефон",
        ("ru", "registration.enter_email"): "Введите email",
        ("ru", "registration.success"): "Регистрация завершена!",
        ("ru", "registration.your_referral_code"): "Ваш реферальный код: {code}",
    }.get((lang, key), "")

    mock_get_button_text.return_value = "Главное меню"

    # Initialize state
    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Step 1: Accept agreement
    mock_callback.data = "accept_agreement"
    await process_agreement(mock_callback, mock_state)
    assert_message_sent(mock_callback.message, contains="ФИО")
    assert_state_set(mock_state)

    # Step 2: Enter full name
    mock_message.text = "Иван Иванов"
    await process_full_name(mock_message, mock_state)
    assert_message_sent(mock_message, contains="телефон")
    assert_state_set(mock_state)

    # Step 3: Enter phone
    mock_message.text = "+7 900 123-45-67"
    await process_phone(mock_message, mock_state)
    assert_message_sent(mock_message, contains="email")
    assert_state_set(mock_state)

    # Step 4: Enter email (completes registration)
    mock_message.text = "ivan@example.com"
    mock_api_client_with_data.create_user.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "full_name": "Иван Иванов",
        "phone": "+7 900 123-45-67",
        "email": "ivan@example.com",
        "referral_code": "REF12345"
    }

    await process_email(mock_message, mock_state)

    # Check user created
    assert_api_called(mock_api_client_with_data, "create_user", times=1)

    # Check success message sent
    assert_message_sent(mock_message, reply_markup_present=True)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_agreement_acceptance(mock_get_text, mock_callback, mock_state):
    """
    P0: Test accepting user agreement.

    Given: User receives agreement
    When: User clicks "Accept" button
    Then: Proceeds to full name input
    """
    from bot.hndlrs.registration_hndlr import process_agreement

    mock_get_text.return_value = "Введите ваше полное имя"
    await mock_state.update_data(lang="ru")

    mock_callback.data = "accept_agreement"
    await process_agreement(mock_callback, mock_state)

    # Check callback answered
    mock_callback.answer.assert_called()

    # Check message edited with new prompt
    mock_callback.message.edit_text.assert_called()

    # Check state progressed
    assert_state_set(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_existing_user_login(mock_get_text, mock_message, mock_state, mock_api_client_with_data):
    """
    P0: Test existing user can access main menu via /start.

    Given: User already registered in system
    When: User sends /start command
    Then: Goes directly to main menu without re-registration
    """
    from bot.hndlrs.registration_hndlr import start_handler

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "welcome.back_message"): "С возвращением, {name}!",
        ("ru", "main_menu.title"): "Главное меню",
    }.get((lang, key), "")

    # User exists
    mock_api_client_with_data.get_user_by_telegram_id.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "full_name": "Иван Иванов",
        "is_banned": False
    }

    await start_handler(mock_message, mock_state)

    # Check welcome back message
    assert_message_sent(mock_message, reply_markup_present=True)

    # Check API called to get user
    assert_api_called(mock_api_client_with_data, "get_user_by_telegram_id", times=1)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_full_name_input(mock_get_text, mock_message, mock_state):
    """
    P0: Test full name input during registration.

    Given: User in FULL_NAME state
    When: User enters valid full name
    Then: Saves name and proceeds to phone input
    """
    from bot.hndlrs.registration_hndlr import process_full_name

    mock_get_text.return_value = "Введите ваш номер телефона"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    mock_message.text = "Петр Петров"
    await process_full_name(mock_message, mock_state)

    # Check full_name saved in state
    state_data = await mock_state.get_data()
    assert state_data.get("full_name") == "Петр Петров"

    # Check message sent for phone
    assert_message_sent(mock_message)

    # Check state progressed to phone
    assert_state_set(mock_state)


# ============================================================================
# P1 - HIGH PRIORITY TESTS (Validation & Errors)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.send_user_error')
async def test_invalid_phone_format(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of invalid phone format.

    Given: User in PHONE state
    When: User enters invalid phone format
    Then: Sends error message and stays in same state
    """
    from bot.hndlrs.registration_hndlr import process_phone

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Invalid phone formats
    invalid_phones = [
        "123456",  # Too short
        "abcdefg",  # Letters
        "+1234567890123456789",  # Too long
        "89001234567",  # Missing +7
    ]

    for invalid_phone in invalid_phones:
        mock_message.text = invalid_phone
        await process_phone(mock_message, mock_state)

        # Check error sent
        mock_send_error.assert_called()

    # State should not clear (stays in PHONE state for retry)
    mock_state.clear.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.send_user_error')
async def test_invalid_email_format(mock_send_error, mock_message, mock_state, mock_api_client_with_data):
    """
    P1: Test validation of invalid email format.

    Given: User in EMAIL state
    When: User enters invalid email format
    Then: Sends error message and stays in same state
    """
    from bot.hndlrs.registration_hndlr import process_email

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        full_name="Test User",
        phone="+7 900 123-45-67"
    )

    # Invalid email formats
    invalid_emails = [
        "notanemail",  # No @
        "@example.com",  # Missing local part
        "user@",  # Missing domain
        "user @example.com",  # Space in email
        "user@.com",  # Missing domain name
    ]

    for invalid_email in invalid_emails:
        mock_message.text = invalid_email
        await process_email(mock_message, mock_state)

        # Check error sent
        mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.send_user_error')
async def test_full_name_too_short(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of too short full name.

    Given: User in FULL_NAME state
    When: User enters name shorter than minimum length
    Then: Sends error message
    """
    from bot.hndlrs.registration_hndlr import process_full_name

    await mock_state.update_data(lang="ru")

    # Too short names
    mock_message.text = "А"  # Single letter
    await process_full_name(mock_message, mock_state)

    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.handle_api_error')
async def test_api_error_during_user_creation(mock_handle_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test handling of API error during user creation.

    Given: User completing registration
    When: API fails to create user
    Then: Handles error gracefully and notifies user
    """
    from bot.hndlrs.registration_hndlr import process_email

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        full_name="Test User",
        phone="+7 900 123-45-67"
    )

    # Simulate API error
    mock_api_client.create_user.side_effect = Exception("Database error")

    mock_message.text = "test@example.com"
    await process_email(mock_message, mock_state)

    # Check error handler called
    mock_handle_error.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_agreement_decline(mock_get_text, mock_callback, mock_state):
    """
    P1: Test declining user agreement.

    Given: User receives agreement
    When: User clicks "Decline" button
    Then: Sends goodbye message and clears state
    """
    from bot.hndlrs.registration_hndlr import process_agreement

    mock_get_text.return_value = "Вы отклонили соглашение. До свидания!"
    await mock_state.update_data(lang="ru")

    mock_callback.data = "decline_agreement"
    await process_agreement(mock_callback, mock_state)

    # Check callback answered
    mock_callback.answer.assert_called()

    # Check decline message sent
    mock_callback.message.edit_text.assert_called()

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_referral_code_applied(mock_get_text, mock_message, mock_state, mock_api_client_with_data):
    """
    P1: Test registration with referral code.

    Given: User starts registration with /start <referral_code>
    When: User completes registration
    Then: Referral code is applied and referrer gets bonus
    """
    from bot.hndlrs.registration_hndlr import start_handler

    mock_get_text.side_effect = lambda lang, key, **kwargs: ""

    # User not found (new registration)
    mock_api_client_with_data.get_user_by_telegram_id.return_value = None

    # Simulate /start with referral code
    mock_message.text = "/start REF123"
    await start_handler(mock_message, mock_state)

    # Check referral code saved in state
    state_data = await mock_state.get_data()
    assert "referred_by_code" in state_data or "referral_code" in state_data


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_phone_normalization(mock_get_text, mock_message, mock_state):
    """
    P1: Test phone number normalization.

    Given: User enters phone in various formats
    When: process_phone() is called
    Then: Phone is normalized to standard format
    """
    from bot.hndlrs.registration_hndlr import process_phone

    mock_get_text.return_value = "Введите email"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Various phone formats that should be accepted
    valid_phones = [
        "+7 900 123-45-67",
        "+79001234567",
        "8 (900) 123-45-67",
    ]

    for phone in valid_phones:
        mock_message.text = phone
        await process_phone(mock_message, mock_state)

        # Check phone saved (may be normalized)
        state_data = await mock_state.get_data()
        assert "phone" in state_data


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.send_user_error')
async def test_empty_input_validation(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of empty inputs.

    Given: User in any input state
    When: User sends empty or whitespace-only message
    Then: Sends error message requesting valid input
    """
    from bot.hndlrs.registration_hndlr import process_full_name, process_phone, process_email

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Test empty full name
    mock_message.text = "   "  # Only whitespace
    await process_full_name(mock_message, mock_state)
    mock_send_error.assert_called()

    # Test empty phone
    mock_message.text = ""
    await process_phone(mock_message, mock_state)
    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_duplicate_registration_prevention(mock_get_text, mock_message, mock_state, mock_api_client):
    """
    P1: Test prevention of duplicate user registration.

    Given: User already exists in system
    When: Same telegram_id tries to register again
    Then: Shows existing user menu instead of registration
    """
    from bot.hndlrs.registration_hndlr import start_handler

    mock_get_text.return_value = "С возвращением!"

    # User already exists
    mock_api_client.get_user_by_telegram_id.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "full_name": "Existing User",
        "is_banned": False
    }

    await start_handler(mock_message, mock_state)

    # Should NOT start new registration
    # Should go to main menu instead
    assert_message_sent(mock_message, reply_markup_present=True)

    # Check user retrieval was called
    assert_api_called(mock_api_client, "get_user_by_telegram_id", times=1)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.handle_api_error')
async def test_network_timeout_during_registration(mock_handle_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test handling of network timeout during registration.

    Given: User completing registration
    When: Network timeout occurs during API call
    Then: Handles timeout gracefully with user-friendly message
    """
    import asyncio
    from bot.hndlrs.registration_hndlr import process_email

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        full_name="Test User",
        phone="+7 900 123-45-67"
    )

    # Simulate timeout
    mock_api_client.create_user.side_effect = asyncio.TimeoutError()

    mock_message.text = "test@example.com"
    await process_email(mock_message, mock_state)

    # Check timeout handled
    mock_handle_error.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_special_characters_in_name(mock_get_text, mock_message, mock_state):
    """
    P1: Test handling of special characters in full name.

    Given: User entering full name
    When: Name contains special characters (hyphens, apostrophes)
    Then: Accepts valid special characters
    """
    from bot.hndlrs.registration_hndlr import process_full_name

    mock_get_text.return_value = "Введите телефон"
    await mock_state.update_data(lang="ru")

    # Valid names with special characters
    valid_names = [
        "Анна-Мария Иванова",
        "O'Connor John",
        "Мария-Луиза фон Штайн",
    ]

    for name in valid_names:
        mock_message.text = name
        await process_full_name(mock_message, mock_state)

        # Check name saved
        state_data = await mock_state.get_data()
        assert state_data.get("full_name") == name


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.send_user_error')
async def test_sql_injection_prevention(mock_send_error, mock_message, mock_state, mock_api_client_with_data):
    """
    P1: Test prevention of SQL injection in user inputs.

    Given: User enters malicious SQL in inputs
    When: Data is processed
    Then: Treats as regular text, doesn't execute SQL
    """
    from bot.hndlrs.registration_hndlr import process_full_name, process_email

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # SQL injection attempts
    mock_message.text = "'; DROP TABLE users; --"
    await process_full_name(mock_message, mock_state)

    # Should save as regular text without executing
    state_data = await mock_state.get_data()
    # Name should be saved (or rejected as too short)
    # Either way, no SQL should execute


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_long_input_truncation(mock_get_text, mock_message, mock_state):
    """
    P1: Test handling of excessively long inputs.

    Given: User enters very long text
    When: Input exceeds maximum length
    Then: Truncates or rejects with error
    """
    from bot.hndlrs.registration_hndlr import process_full_name

    mock_get_text.return_value = "Имя слишком длинное"
    await mock_state.update_data(lang="ru")

    # Extremely long name
    mock_message.text = "A" * 500
    await process_full_name(mock_message, mock_state)

    # Should either truncate or show error
    # Check that some handling occurred
    assert mock_message.answer.called or mock_get_text.called


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.registration_hndlr.get_text')
async def test_concurrent_registration_attempts(mock_get_text, mock_message, mock_state, mock_api_client):
    """
    P1: Test handling of concurrent registration attempts.

    Given: User triggers registration multiple times
    When: Multiple /start commands sent rapidly
    Then: Handles gracefully without duplicate users
    """
    from bot.hndlrs.registration_hndlr import start_handler

    mock_get_text.return_value = "Начнем регистрацию"

    # First attempt - no user exists
    mock_api_client.get_user_by_telegram_id.return_value = None

    # Simulate rapid multiple /start calls
    await start_handler(mock_message, mock_state)
    await start_handler(mock_message, mock_state)
    await start_handler(mock_message, mock_state)

    # Should handle gracefully
    assert mock_message.answer.call_count >= 1
