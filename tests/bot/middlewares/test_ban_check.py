"""
Tests for BanCheckMiddleware in bot.bot module.

Tests cover:
- Blocking banned users
- Allowing non-banned users
- Sending ban messages
- Handling API errors
- Message vs CallbackQuery events
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot.bot import BanCheckMiddleware


# ============================================================================
# Test Banned User Blocking
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_blocks_banned_user_message(mock_message, mock_api_client, mock_bot):
    """
    Test banned user is blocked from using bot (Message event).

    Given: User is banned in database
    When: User sends message
    Then: Sends ban message and blocks handler execution
    """
    # User is banned
    mock_api_client._make_request.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "is_banned": True,
        "ban_reason": "Spam"
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    with patch('bot.bot.get_bot', return_value=mock_bot):
        result = await middleware(handler, mock_message, {})

    # Check ban message sent
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args
    assert "администратором" in str(call_args).lower() or "admin" in str(call_args).lower()

    # Handler should NOT be called
    handler.assert_not_called()

    # Result should be None (blocks execution)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_blocks_banned_user_callback(mock_callback, mock_api_client):
    """
    Test banned user is blocked from using bot (CallbackQuery event).

    Given: User is banned in database
    When: User clicks button (callback query)
    Then: Shows alert and blocks handler execution
    """
    # User is banned
    mock_api_client._make_request.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "is_banned": True,
        "ban_reason": "Violation of rules"
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    result = await middleware(handler, mock_callback, {})

    # Check alert shown
    mock_callback.answer.assert_called_once()
    call_kwargs = mock_callback.answer.call_args[1]
    assert call_kwargs.get("show_alert") is True

    # Handler should NOT be called
    handler.assert_not_called()

    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_allows_non_banned_user(mock_message, mock_api_client):
    """
    Test non-banned user can use bot normally.

    Given: User is not banned
    When: User sends message
    Then: Allows handler execution without sending ban message
    """
    # User is not banned
    mock_api_client._make_request.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "is_banned": False,
        "ban_reason": None
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_message, {})

    # Handler SHOULD be called
    handler.assert_called_once()

    # No ban message should be sent
    mock_message.answer.assert_not_called()


# ============================================================================
# Test Error Handling
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_allows_user_on_api_error(mock_message, mock_api_client):
    """
    Test user is allowed through if API check fails.

    Given: API request fails with error
    When: Trying to check ban status
    Then: Allows user through (fail open for availability)
    """
    # API error
    mock_api_client._make_request.side_effect = Exception("API unavailable")

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    # Should not raise exception
    await middleware(handler, mock_message, {})

    # Handler SHOULD be called (fail open)
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_user_not_found(mock_message, mock_api_client):
    """
    Test middleware handles case when user not found in DB.

    Given: User doesn't exist in database
    When: API returns None
    Then: Allows user through (new users should be able to register)
    """
    # User not found
    mock_api_client._make_request.return_value = None

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_message, {})

    # Handler SHOULD be called (new user registration)
    handler.assert_called_once()


# ============================================================================
# Test API Client Initialization
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_initializes_api_client(mock_message, mock_api_client):
    """
    Test middleware initializes API client on first use.

    Given: Middleware without api_client set
    When: Called for first time
    Then: Initializes api_client
    """
    middleware = BanCheckMiddleware()
    # api_client not set initially
    assert middleware.api_client is None

    handler = AsyncMock()

    with patch('bot.bot.get_api_client', return_value=mock_api_client):
        mock_api_client._make_request.return_value = {"is_banned": False}
        await middleware(handler, mock_message, {})

    # API client should be initialized
    assert middleware.api_client is not None


# ============================================================================
# Test Event Type Handling
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_message_event(mock_message, mock_api_client):
    """
    Test middleware correctly identifies Message event.

    Given: Message event with from_user
    When: Middleware processes event
    Then: Extracts user from message.from_user
    """
    mock_api_client._make_request.return_value = {"is_banned": False}

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_message, {})

    # Check API called with correct telegram_id from message.from_user
    mock_api_client._make_request.assert_called_once()
    call_args = mock_api_client._make_request.call_args[0]
    assert f"/users/telegram/{mock_message.from_user.id}" in call_args[1]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_callback_event(mock_callback, mock_api_client):
    """
    Test middleware correctly identifies CallbackQuery event.

    Given: CallbackQuery event with from_user
    When: Middleware processes event
    Then: Extracts user from callback.from_user
    """
    mock_api_client._make_request.return_value = {"is_banned": False}

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_callback, {})

    # Check API called with correct telegram_id from callback.from_user
    mock_api_client._make_request.assert_called_once()
    call_args = mock_api_client._make_request.call_args[0]
    assert f"/users/telegram/{mock_callback.from_user.id}" in call_args[1]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_no_user(mock_api_client):
    """
    Test middleware handles events without user information.

    Given: Event with no from_user attribute
    When: Middleware processes event
    Then: Allows through without checking ban status
    """
    # Event without from_user
    event = MagicMock()
    del event.from_user  # Remove from_user attribute

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, event, {})

    # Handler should be called (no user to check)
    handler.assert_called_once()

    # API should not be called
    mock_api_client._make_request.assert_not_called()


# ============================================================================
# Test Ban Message Content
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_message_includes_admin_contact(mock_message, mock_api_client, mock_bot):
    """
    Test ban message includes admin contact information.

    Given: Banned user
    When: Ban message is sent
    Then: Message includes admin contact URL
    """
    mock_api_client._make_request.return_value = {
        "is_banned": True,
        "ban_reason": "Test ban"
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client

    with patch('bot.bot.get_bot', return_value=mock_bot):
        with patch('bot.bot.ADMIN_URL', 'https://t.me/admin'):
            handler = AsyncMock()
            await middleware(handler, mock_message, {})

    # Check message contains admin URL
    call_args = mock_bot.send_message.call_args[0]
    assert 'https://t.me/admin' in str(call_args) or 'admin' in str(call_args).lower()


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.bot.logger')
async def test_ban_check_logs_blocked_user(mock_logger, mock_message, mock_api_client, mock_bot):
    """
    Test that blocking banned user is logged.

    Given: Banned user tries to use bot
    When: User is blocked
    Then: Logs the blocking event
    """
    mock_api_client._make_request.return_value = {
        "is_banned": True,
        "ban_reason": "Spam"
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client

    with patch('bot.bot.get_bot', return_value=mock_bot):
        handler = AsyncMock()
        await middleware(handler, mock_message, {})

    # Check logging occurred
    mock_logger.info.assert_called()

    # Check log mentions user_id and blocking
    log_call = mock_logger.info.call_args[0][0]
    assert "12345" in str(log_call)  # user_id
    assert "блокирован" in str(log_call).lower() or "block" in str(log_call).lower()


# ============================================================================
# Test Edge Cases
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_partial_user_data(mock_message, mock_api_client):
    """
    Test middleware handles incomplete user data from API.

    Given: API returns user data without ban fields
    When: Checking ban status
    Then: Treats as not banned (missing is_banned field)
    """
    # Incomplete user data
    mock_api_client._make_request.return_value = {
        "id": 1,
        "telegram_id": 12345
        # Missing is_banned field
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_message, {})

    # Should allow through (no is_banned field = not banned)
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_false_is_banned(mock_message, mock_api_client):
    """
    Test middleware correctly handles is_banned=False.

    Given: User explicitly has is_banned=False
    When: Checking ban status
    Then: Allows user through
    """
    mock_api_client._make_request.return_value = {
        "id": 1,
        "telegram_id": 12345,
        "is_banned": False
    }

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    await middleware(handler, mock_message, {})

    # Should allow through
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_handles_truthy_is_banned_values(mock_message, mock_api_client, mock_bot):
    """
    Test middleware treats various truthy values as banned.

    Given: is_banned has truthy values (True, 1, "true")
    When: Checking ban status
    Then: Blocks user
    """
    truthy_values = [True, 1, "true", "yes"]

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client

    for truthy_value in truthy_values:
        handler = AsyncMock()
        mock_api_client._make_request.return_value = {
            "id": 1,
            "telegram_id": 12345,
            "is_banned": truthy_value
        }

        with patch('bot.bot.get_bot', return_value=mock_bot):
            await middleware(handler, mock_message, {})

        # All truthy values should block
        handler.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_ban_check_performance_with_many_requests(mock_message, mock_api_client):
    """
    Test middleware performance doesn't degrade with repeated calls.

    Given: Multiple sequential requests
    When: Processing many events
    Then: Maintains performance (API client reused)
    """
    mock_api_client._make_request.return_value = {"is_banned": False}

    middleware = BanCheckMiddleware()
    middleware.api_client = mock_api_client
    handler = AsyncMock()

    # Simulate 100 requests
    for _ in range(100):
        await middleware(handler, mock_message, {})

    # Check API client was reused (not re-initialized)
    assert middleware.api_client is mock_api_client

    # All requests should have gone through
    assert handler.call_count == 100
