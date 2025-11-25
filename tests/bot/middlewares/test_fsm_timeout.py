"""
Tests for bot.middlewares.fsm_timeout module.

Tests cover:
- Timeout detection after 5 minutes
- State clearing on timeout
- Excluded states (payment processing)
- Timeout message sending
- Activity timestamp updates
- Edge cases (no state, no timestamp)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from bot.middlewares.fsm_timeout import FSMTimeoutMiddleware


# ============================================================================
# Test FSM Timeout Detection
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_clears_state_after_5_minutes(mock_get_text, mock_message, mock_state):
    """
    Test FSM state is cleared after 5 minutes of inactivity.

    Given: User has FSM state with last activity >5 minutes ago
    When: Middleware is called
    Then: Clears state and sends timeout message
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "fsm.timeout_message"): "⏱ Время ожидания истекло",
        ("ru", "fsm.timeout_alert"): "Время сессии истекло",
    }.get((lang, key), "")

    # Set state with old timestamp (6 minutes ago)
    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Registration:FULL_NAME")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    # Call middleware
    result = await middleware(handler, mock_message, {"state": mock_state})

    # Check state was cleared
    mock_state.clear.assert_called_once()

    # Check timeout message sent
    mock_message.answer.assert_called_once()

    # Handler should NOT be called (timeout occurred)
    handler.assert_not_called()

    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_allows_recent_activity(mock_message, mock_state):
    """
    Test FSM state is NOT cleared for recent activity.

    Given: User has FSM state with last activity <5 minutes ago
    When: Middleware is called
    Then: Updates timestamp and continues to handler
    """
    # Set state with recent timestamp (2 minutes ago)
    recent_timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
    await mock_state.set_state("Registration:PHONE")
    await mock_state.update_data(_last_activity=recent_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    # Call middleware
    result = await middleware(handler, mock_message, {"state": mock_state})

    # Check state was NOT cleared
    mock_state.clear.assert_not_called()

    # Check message was NOT sent
    mock_message.answer.assert_not_called()

    # Handler SHOULD be called
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_updates_timestamp(mock_message, mock_state):
    """
    Test FSM middleware updates activity timestamp.

    Given: User has FSM state
    When: Middleware is called
    Then: Updates _last_activity to current time
    """
    # Set state with timestamp
    old_timestamp = (datetime.now() - timedelta(minutes=1)).timestamp()
    await mock_state.set_state("Booking:SELECT_TARIFF")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    before_time = datetime.now().timestamp()
    await middleware(handler, mock_message, {"state": mock_state})
    after_time = datetime.now().timestamp()

    # Check timestamp was updated
    state_data = await mock_state.get_data()
    new_timestamp = state_data.get("_last_activity")

    assert new_timestamp is not None
    assert before_time <= new_timestamp <= after_time


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_handles_no_state(mock_message, mock_state):
    """
    Test middleware handles case when user has no FSM state.

    Given: User has no FSM state set
    When: Middleware is called
    Then: Continues to handler without errors
    """
    # No state set
    await mock_state.set_state(None)

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    # Should not raise error
    await middleware(handler, mock_message, {"state": mock_state})

    # Handler should be called
    handler.assert_called_once()

    # No clear should happen
    mock_state.clear.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_handles_no_timestamp(mock_message, mock_state):
    """
    Test middleware handles case when state has no _last_activity.

    Given: User has FSM state but no _last_activity timestamp
    When: Middleware is called
    Then: Sets initial timestamp and continues
    """
    # State without timestamp
    await mock_state.set_state("Registration:FULL_NAME")
    await mock_state.update_data(lang="ru")  # No _last_activity

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Should set timestamp
    state_data = await mock_state.get_data()
    assert "_last_activity" in state_data

    # Handler should be called
    handler.assert_called_once()


# ============================================================================
# Test Excluded States
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_excludes_payment_state(mock_message, mock_state):
    """
    Test payment processing state is excluded from timeout.

    Given: User in STATUS_PAYMENT state (can take longer)
    When: More than 5 minutes pass
    Then: State is NOT cleared
    """
    # Set payment state with old timestamp (10 minutes ago)
    old_timestamp = (datetime.now() - timedelta(minutes=10)).timestamp()
    await mock_state.set_state("Booking:STATUS_PAYMENT")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    # Call middleware
    await middleware(handler, mock_message, {"state": mock_state})

    # Check state was NOT cleared (payment is excluded)
    mock_state.clear.assert_not_called()

    # Handler should be called
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_non_excluded_states_timeout(mock_get_text, mock_message, mock_state):
    """
    Test non-excluded states timeout normally.

    Given: User in non-excluded state with old timestamp
    When: Middleware is called
    Then: State is cleared
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: "Timeout message"

    # Test various non-excluded states
    non_excluded_states = [
        "Registration:FULL_NAME",
        "Registration:PHONE",
        "Registration:EMAIL",
        "Booking:SELECT_TARIFF",
        "Booking:ENTER_DATE",
        "Booking:ENTER_TIME",
        "TicketForm:DESCRIPTION",
        "TicketForm:PHOTO",
    ]

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    for state_name in non_excluded_states:
        # Reset mocks
        mock_state.clear.reset_mock()
        handler.reset_mock()

        # Set state with old timestamp
        old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
        await mock_state.set_state(state_name)
        await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

        # Call middleware
        await middleware(handler, mock_message, {"state": mock_state})

        # All should timeout
        mock_state.clear.assert_called_once()


# ============================================================================
# Test Timeout Messages
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_sends_general_message(mock_get_text, mock_message, mock_state):
    """
    Test generic timeout message for unknown states.

    Given: User in timeout state
    When: State name not recognized
    Then: Sends general timeout message
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "fsm.timeout_message"): "⏱ Время ожидания истекло",
        ("ru", "fsm.timeout_alert"): "Сессия завершена",
    }.get((lang, key), "")

    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("UnknownState:SOMETHING")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Check generic message used
    mock_get_text.assert_any_call("ru", "fsm.timeout_message")


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_sends_booking_specific_message(mock_get_text, mock_message, mock_state):
    """
    Test booking-specific timeout message.

    Given: User in Booking state timeout
    When: Timeout occurs
    Then: Sends booking-specific message
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "fsm.timeout_booking"): "⏱ Сессия бронирования завершена",
        ("ru", "fsm.timeout_alert"): "Время истекло",
    }.get((lang, key), "")

    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Booking:ENTER_DATE")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Check booking-specific message used
    mock_get_text.assert_any_call("ru", "fsm.timeout_booking")


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_sends_registration_specific_message(mock_get_text, mock_message, mock_state):
    """
    Test registration-specific timeout message.

    Given: User in Registration state timeout
    When: Timeout occurs
    Then: Sends registration-specific message
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "fsm.timeout_registration"): "⏱ Время регистрации истекло",
        ("ru", "fsm.timeout_alert"): "Сессия завершена",
    }.get((lang, key), "")

    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Registration:PHONE")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Check registration-specific message used
    mock_get_text.assert_any_call("ru", "fsm.timeout_registration")


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.get_text')
async def test_fsm_timeout_sends_ticket_specific_message(mock_get_text, mock_message, mock_state):
    """
    Test ticket-specific timeout message.

    Given: User in TicketForm state timeout
    When: Timeout occurs
    Then: Sends ticket-specific message
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "fsm.timeout_ticket"): "⏱ Время создания обращения истекло",
        ("ru", "fsm.timeout_alert"): "Сессия завершена",
    }.get((lang, key), "")

    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("TicketForm:DESCRIPTION")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Check ticket-specific message used
    mock_get_text.assert_any_call("ru", "fsm.timeout_ticket")


# ============================================================================
# Test Edge Cases
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_handles_callback_query(mock_callback, mock_state):
    """
    Test middleware works with CallbackQuery events.

    Given: CallbackQuery event instead of Message
    When: Middleware is called
    Then: Handles correctly with callback.answer()
    """
    # Set old timestamp
    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Registration:EMAIL")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    # Use callback query instead of message
    with patch('bot.middlewares.fsm_timeout.get_text', return_value="Timeout"):
        await middleware(handler, mock_callback, {"state": mock_state})

    # Check state cleared
    mock_state.clear.assert_called_once()

    # Check callback answered (not message.answer)
    mock_callback.answer.assert_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_boundary_exactly_5_minutes(mock_message, mock_state):
    """
    Test boundary case: exactly 5 minutes.

    Given: User has FSM state with activity exactly 5 minutes ago
    When: Middleware is called
    Then: State is cleared (>= 5 minutes)
    """
    # Exactly 5 minutes (300 seconds)
    exactly_5min_timestamp = (datetime.now() - timedelta(seconds=300)).timestamp()
    await mock_state.set_state("Registration:PHONE")
    await mock_state.update_data(_last_activity=exactly_5min_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    with patch('bot.middlewares.fsm_timeout.get_text', return_value="Timeout"):
        await middleware(handler, mock_message, {"state": mock_state})

    # At exactly 5 minutes, should timeout
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_boundary_just_under_5_minutes(mock_message, mock_state):
    """
    Test boundary case: just under 5 minutes.

    Given: User has FSM state with activity 4:59 ago
    When: Middleware is called
    Then: State is NOT cleared (< 5 minutes)
    """
    # Just under 5 minutes (299 seconds)
    just_under_5min_timestamp = (datetime.now() - timedelta(seconds=299)).timestamp()
    await mock_state.set_state("Booking:ENTER_TIME")
    await mock_state.update_data(_last_activity=just_under_5min_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    await middleware(handler, mock_message, {"state": mock_state})

    # Should NOT timeout
    mock_state.clear.assert_not_called()

    # Handler should be called
    handler.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.middlewares.fsm_timeout.logger')
async def test_fsm_timeout_logs_timeout_event(mock_logger, mock_message, mock_state):
    """
    Test that timeout events are logged.

    Given: User FSM state times out
    When: State is cleared
    Then: Logs timeout event with context
    """
    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Registration:FULL_NAME")
    await mock_state.update_data(_last_activity=old_timestamp, lang="ru")

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    with patch('bot.middlewares.fsm_timeout.get_text', return_value="Timeout"):
        await middleware(handler, mock_message, {"state": mock_state})

    # Check logging occurred
    mock_logger.info.assert_called()

    # Check log contains user_id and state
    log_call = mock_logger.info.call_args[0][0]
    assert "12345" in str(log_call)  # user_id
    assert "Registration" in str(log_call) or "FULL_NAME" in str(log_call)  # state


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fsm_timeout_handles_missing_language(mock_message, mock_state):
    """
    Test middleware handles missing language in state data.

    Given: User has FSM state without lang field
    When: Timeout occurs
    Then: Uses default language "ru"
    """
    old_timestamp = (datetime.now() - timedelta(minutes=6)).timestamp()
    await mock_state.set_state("Registration:PHONE")
    await mock_state.update_data(_last_activity=old_timestamp)  # No lang

    middleware = FSMTimeoutMiddleware()
    handler = AsyncMock()

    with patch('bot.middlewares.fsm_timeout.get_text', return_value="Timeout") as mock_get_text:
        await middleware(handler, mock_message, {"state": mock_state})

    # Should use default "ru" language
    mock_get_text.assert_called()
    call_args = mock_get_text.call_args_list
    # Check that "ru" was used
    assert any("ru" in str(call) for call in call_args)
