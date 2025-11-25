"""
Unit tests for bot.utils.error_handler module.

Tests cover:
- Error category classification
- Support keyboard creation
- User error message sending
- API error handling
- Validation error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from bot.utils.error_handler import (
    ErrorCategory,
    _get_error_category,
    _create_support_keyboard,
    send_user_error,
    handle_api_error,
    handle_validation_error,
)


# ============================================================================
# Test ErrorCategory Enum
# ============================================================================

@pytest.mark.unit
def test_error_category_enum():
    """Test that ErrorCategory enum has all expected values."""
    assert ErrorCategory.NETWORK.value == "network"
    assert ErrorCategory.DATA.value == "data"
    assert ErrorCategory.VALIDATION.value == "validation"
    assert ErrorCategory.BUSINESS.value == "business"
    assert ErrorCategory.SYSTEM.value == "system"
    assert ErrorCategory.PAYMENT.value == "payment"


# ============================================================================
# Test _get_error_category()
# ============================================================================

@pytest.mark.unit
def test_get_error_category_network_errors():
    """
    Test error categorization for network-related errors.

    Given: Various network-related exceptions
    When: _get_error_category() is called
    Then: Returns ErrorCategory.NETWORK
    """
    # aiohttp.ClientError
    error = aiohttp.ClientError("Connection failed")
    assert _get_error_category(error) == ErrorCategory.NETWORK

    # aiohttp.ServerTimeoutError
    error = aiohttp.ServerTimeoutError()
    assert _get_error_category(error) == ErrorCategory.NETWORK

    # TimeoutError
    error = TimeoutError("Request timeout")
    assert _get_error_category(error) == ErrorCategory.NETWORK


@pytest.mark.unit
def test_get_error_category_data_errors():
    """
    Test error categorization for data-related errors.

    Given: KeyError or AttributeError exceptions
    When: _get_error_category() is called
    Then: Returns ErrorCategory.DATA
    """
    # KeyError
    error = KeyError("user_id")
    assert _get_error_category(error) == ErrorCategory.DATA

    # AttributeError
    error = AttributeError("'NoneType' object has no attribute 'id'")
    assert _get_error_category(error) == ErrorCategory.DATA


@pytest.mark.unit
def test_get_error_category_validation_errors():
    """
    Test error categorization for validation-related errors.

    Given: ValueError or TypeError exceptions
    When: _get_error_category() is called
    Then: Returns ErrorCategory.VALIDATION
    """
    # ValueError
    error = ValueError("Invalid email format")
    assert _get_error_category(error) == ErrorCategory.VALIDATION

    # TypeError
    error = TypeError("Expected str, got int")
    assert _get_error_category(error) == ErrorCategory.VALIDATION


@pytest.mark.unit
def test_get_error_category_system_errors():
    """
    Test error categorization for unknown/system errors.

    Given: Generic Exception or unknown error types
    When: _get_error_category() is called
    Then: Returns ErrorCategory.SYSTEM
    """
    # Generic Exception
    error = Exception("Unknown error")
    assert _get_error_category(error) == ErrorCategory.SYSTEM

    # Custom exception
    class CustomError(Exception):
        pass

    error = CustomError("Custom error")
    assert _get_error_category(error) == ErrorCategory.SYSTEM


# ============================================================================
# Test _create_support_keyboard()
# ============================================================================

@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
def test_create_support_keyboard_russian(mock_get_text):
    """
    Test support keyboard creation for Russian language.

    Given: Russian language code
    When: _create_support_keyboard() is called
    Then: Returns InlineKeyboardMarkup with localized support button
    """
    mock_get_text.return_value = "💬 Связаться с поддержкой"

    keyboard = _create_support_keyboard(lang="ru")

    # Check that get_text was called correctly
    mock_get_text.assert_called_once_with("ru", "buttons.contact_support")

    # Check keyboard structure
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 1

    # Check button properties
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "💬 Связаться с поддержкой"
    assert button.callback_data == "create_ticket"


@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
def test_create_support_keyboard_english(mock_get_text):
    """
    Test support keyboard creation for English language.

    Given: English language code
    When: _create_support_keyboard() is called
    Then: Returns InlineKeyboardMarkup with English support button
    """
    mock_get_text.return_value = "💬 Contact Support"

    keyboard = _create_support_keyboard(lang="en")

    mock_get_text.assert_called_once_with("en", "buttons.contact_support")
    button = keyboard.inline_keyboard[0][0]
    assert button.text == "💬 Contact Support"


# ============================================================================
# Test send_user_error() - Message Events
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
@patch('bot.utils.error_handler.logger')
async def test_send_user_error_message_basic(mock_logger, mock_get_text, mock_message):
    """
    Test sending error message via Message event (basic case).

    Given: A message event and error key
    When: send_user_error() is called
    Then: Sends localized error message and logs warning
    """
    mock_get_text.return_value = "❌ Произошла ошибка"

    await send_user_error(
        mock_message,
        "errors.general",
        lang="ru"
    )

    # Check localization called
    mock_get_text.assert_called_once_with("ru", "errors.general")

    # Check message sent
    mock_message.answer.assert_called_once()
    call_args = mock_message.answer.call_args
    assert "❌ Произошла ошибка" in str(call_args)
    assert call_args[1].get('reply_markup') is None  # No support button

    # Check logged as warning (no exception)
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
@patch('bot.utils.error_handler.logger')
async def test_send_user_error_with_exception(mock_logger, mock_get_text, mock_message):
    """
    Test sending error message with actual exception.

    Given: A message event and an exception
    When: send_user_error() is called with error parameter
    Then: Logs error with exc_info
    """
    mock_get_text.return_value = "🌐 Сервер недоступен"
    test_error = aiohttp.ClientError("Connection failed")

    await send_user_error(
        mock_message,
        "errors.api_unavailable",
        lang="ru",
        error=test_error
    )

    # Check logged as error with exception info
    mock_logger.error.assert_called_once()
    call_kwargs = mock_logger.error.call_args[1]
    assert call_kwargs['exc_info'] == test_error
    assert 'extra' in call_kwargs
    assert call_kwargs['extra']['error_category'] == 'network'


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
async def test_send_user_error_with_support_button(mock_get_text, mock_message):
    """
    Test sending error message with support button.

    Given: show_support=True parameter
    When: send_user_error() is called
    Then: Includes support button in reply_markup
    """
    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "errors.system_critical"): "❌ Произошла системная ошибка",
        ("ru", "buttons.contact_support"): "💬 Связаться с поддержкой"
    }.get((lang, key), "")

    await send_user_error(
        mock_message,
        "errors.system_critical",
        lang="ru",
        show_support=True
    )

    # Check that answer was called with reply_markup
    mock_message.answer.assert_called_once()
    call_kwargs = mock_message.answer.call_args[1]
    assert call_kwargs['reply_markup'] is not None

    # Verify keyboard structure
    keyboard = call_kwargs['reply_markup']
    assert len(keyboard.inline_keyboard) == 1
    assert keyboard.inline_keyboard[0][0].callback_data == "create_ticket"


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
async def test_send_user_error_with_format_kwargs(mock_get_text, mock_message):
    """
    Test sending error message with format parameters.

    Given: Additional format_kwargs for message formatting
    When: send_user_error() is called
    Then: Passes format_kwargs to get_text()
    """
    mock_get_text.return_value = "Тариф 'Рабочее место' недоступен"

    await send_user_error(
        mock_message,
        "errors.tariff_not_available",
        lang="ru",
        tariff_name="Рабочее место"
    )

    # Check that format_kwargs were passed to get_text
    mock_get_text.assert_called_once_with(
        "ru",
        "errors.tariff_not_available",
        tariff_name="Рабочее место"
    )


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
@patch('bot.utils.error_handler.logger')
async def test_send_user_error_with_fsm_state(mock_logger, mock_get_text, mock_message, mock_state):
    """
    Test sending error message with FSM state logging.

    Given: FSM state context provided
    When: send_user_error() is called with state parameter
    Then: Logs FSM state and data keys
    """
    mock_get_text.return_value = "❌ Ошибка"
    await mock_state.set_state("Registration:PHONE")
    await mock_state.update_data(lang="ru", telegram_id=12345)

    await send_user_error(
        mock_message,
        "errors.general",
        lang="ru",
        state=mock_state
    )

    # Check that FSM state was retrieved
    mock_state.get_state.assert_called()
    mock_state.get_data.assert_called()

    # Check logging includes FSM context
    mock_logger.warning.assert_called_once()
    log_extra = mock_logger.warning.call_args[1]['extra']
    assert 'fsm_state' in log_extra
    assert 'fsm_data_keys' in log_extra


# ============================================================================
# Test send_user_error() - CallbackQuery Events
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
async def test_send_user_error_callback_edit_success(mock_get_text, mock_callback):
    """
    Test sending error via CallbackQuery (successful edit).

    Given: A callback query event
    When: send_user_error() is called
    Then: Edits message text and answers callback
    """
    mock_get_text.return_value = "❌ Ошибка"

    await send_user_error(
        mock_callback,
        "errors.general",
        lang="ru"
    )

    # Check message was edited
    mock_callback.message.edit_text.assert_called_once()
    call_args = mock_callback.message.edit_text.call_args
    assert "❌ Ошибка" in str(call_args[0])

    # Check callback was answered
    mock_callback.answer.assert_called()


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
async def test_send_user_error_callback_edit_fails(mock_get_text, mock_callback):
    """
    Test sending error via CallbackQuery when edit fails.

    Given: A callback query where edit_text fails
    When: send_user_error() is called
    Then: Falls back to answer with alert and new message
    """
    mock_get_text.return_value = "❌ Ошибка при редактировании"

    # Make edit_text fail
    mock_callback.message.edit_text.side_effect = Exception("Cannot edit")

    await send_user_error(
        mock_callback,
        "errors.general",
        lang="ru"
    )

    # Check that edit was attempted
    mock_callback.message.edit_text.assert_called_once()

    # Check fallback: answer with alert
    assert mock_callback.answer.call_count >= 1

    # Check new message was sent
    mock_callback.message.answer.assert_called_once()


# ============================================================================
# Test handle_api_error()
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
@patch('bot.utils.error_handler.logger')
async def test_handle_api_error_timeout(mock_logger, mock_send_error, mock_message):
    """
    Test API error handling for timeout errors.

    Given: aiohttp.ServerTimeoutError
    When: handle_api_error() is called
    Then: Sends network_timeout error with support button
    """
    error = aiohttp.ServerTimeoutError()

    await handle_api_error(
        mock_message,
        error,
        lang="ru",
        operation="create_user"
    )

    # Check logger called
    mock_logger.error.assert_called_once()

    # Check send_user_error called with correct error_key
    mock_send_error.assert_called_once_with(
        mock_message,
        "errors.network_timeout",
        lang="ru",
        error=error,
        show_support=True,
        state=None,
        operation="create_user"
    )


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
async def test_handle_api_error_client_error(mock_send_error, mock_message):
    """
    Test API error handling for client errors.

    Given: aiohttp.ClientError
    When: handle_api_error() is called
    Then: Sends api_unavailable error
    """
    error = aiohttp.ClientError("Connection refused")

    await handle_api_error(
        mock_message,
        error,
        lang="ru",
        operation="get_tariffs"
    )

    mock_send_error.assert_called_once_with(
        mock_message,
        "errors.api_unavailable",
        lang="ru",
        error=error,
        show_support=True,
        state=None,
        operation="get_tariffs"
    )


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
async def test_handle_api_error_generic(mock_send_error, mock_message, mock_state):
    """
    Test API error handling for generic errors.

    Given: Generic Exception
    When: handle_api_error() is called with state
    Then: Sends generic api_error
    """
    error = Exception("Unknown API error")

    await handle_api_error(
        mock_message,
        error,
        lang="ru",
        operation="create_booking",
        state=mock_state
    )

    mock_send_error.assert_called_once_with(
        mock_message,
        "errors.api_error",
        lang="ru",
        error=error,
        show_support=True,
        state=mock_state,
        operation="create_booking"
    )


# ============================================================================
# Test handle_validation_error()
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
async def test_handle_validation_error_phone(mock_send_error, mock_message):
    """
    Test validation error handling for phone field.

    Given: Invalid phone input
    When: handle_validation_error() is called for phone
    Then: Sends invalid_phone error with example
    """
    await handle_validation_error(
        mock_message,
        "phone",
        lang="ru",
        example="+7 900 123-45-67"
    )

    mock_send_error.assert_called_once_with(
        mock_message,
        "errors.invalid_phone",
        lang="ru",
        show_support=False,
        example="+7 900 123-45-67"
    )


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
async def test_handle_validation_error_email(mock_send_error, mock_message):
    """
    Test validation error handling for email field.

    Given: Invalid email input
    When: handle_validation_error() is called for email
    Then: Sends invalid_email error with example
    """
    await handle_validation_error(
        mock_message,
        "email",
        lang="ru",
        example="user@example.com"
    )

    mock_send_error.assert_called_once_with(
        mock_message,
        "errors.invalid_email",
        lang="ru",
        show_support=False,
        example="user@example.com"
    )


@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.send_user_error')
async def test_handle_validation_error_no_example(mock_send_error, mock_callback):
    """
    Test validation error handling without example.

    Given: Invalid input without example provided
    When: handle_validation_error() is called
    Then: Sends error without example parameter
    """
    await handle_validation_error(
        mock_callback,
        "date",
        lang="en"
    )

    mock_send_error.assert_called_once_with(
        mock_callback,
        "errors.invalid_date",
        lang="en",
        show_support=False
    )


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
@patch('bot.utils.error_handler.get_text')
@patch('bot.utils.error_handler.logger')
async def test_send_user_error_send_fails(mock_logger, mock_get_text, mock_message):
    """
    Test behavior when sending error message fails.

    Given: Message.answer() raises exception
    When: send_user_error() is called
    Then: Logs the failure without raising exception
    """
    mock_get_text.return_value = "❌ Ошибка"
    mock_message.answer.side_effect = Exception("Telegram API error")

    # Should not raise exception
    await send_user_error(
        mock_message,
        "errors.general",
        lang="ru"
    )

    # Check that failure was logged
    assert mock_logger.error.call_count >= 1
    last_call = mock_logger.error.call_args_list[-1]
    assert "Не удалось отправить сообщение" in str(last_call)
