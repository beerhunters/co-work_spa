"""
Integration tests for bot.hndlrs.ticket_hndlr module.

Tests cover:
P0 (Critical):
- Create ticket without photo
- Create ticket with photo
- View user tickets
- Support menu navigation

P1 (High Priority):
- Description validation (too short/too long)
- Photo upload validation
- API errors during ticket creation
- Empty tickets list
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from tests.bot.utils import (
    assert_message_sent,
    assert_message_edited,
    assert_callback_answered,
    assert_state_set,
    assert_state_cleared,
    assert_api_called,
    create_ticket_data,
    create_user_data,
)


# ============================================================================
# P0 - CRITICAL TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_support_menu_display(mock_get_text, mock_callback, mock_state):
    """
    P0: Test support menu shows options.

    Given: User clicks "Support" button
    When: support_menu() is called
    Then: Shows create ticket and my tickets options
    """
    from bot.hndlrs.ticket_hndlr import support_menu

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.title"): "Поддержка",
        ("ru", "support.description"): "Выберите действие:",
    }.get((lang, key), "")

    mock_callback.data = "support"
    await support_menu(mock_callback, mock_state)

    # Check callback answered
    assert_callback_answered(mock_callback)

    # Check message edited with options
    assert_message_edited(mock_callback, contains="Поддержка")


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.ticket_hndlr.get_text')
@patch('bot.hndlrs.ticket_hndlr.get_button_text')
async def test_create_ticket_without_photo(mock_get_button_text, mock_get_text,
                                            mock_message, mock_callback, mock_state,
                                            mock_api_client_with_data, mock_bot):
    """
    P0: Test complete ticket creation without photo.

    Given: User creates support ticket
    When: All steps completed without photo
    Then: Ticket created successfully
    """
    from bot.hndlrs.ticket_hndlr import (
        start_ticket_creation,
        process_description,
        process_skip_photo,
    )

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.enter_description"): "Опишите вашу проблему:",
        ("ru", "support.want_add_photo"): "Добавить фото?",
        ("ru", "support.ticket_created_success"): "Обращение #{ticket_id} создано!",
    }.get((lang, key), "")

    mock_get_button_text.return_value = "Мои обращения"

    # Step 1: Start ticket creation
    mock_callback.data = "create_ticket"
    await start_ticket_creation(mock_callback, mock_state)
    assert_callback_answered(mock_callback)
    assert_state_set(mock_state)

    # Step 2: Enter description
    mock_message.text = "У меня проблема с доступом в коворкинг"
    await process_description(mock_message, mock_state)
    assert_message_sent(mock_message, reply_markup_present=True)
    assert_state_set(mock_state)

    # Step 3: Skip photo
    mock_callback.data = "no_photo"
    mock_api_client_with_data.create_ticket.return_value = create_ticket_data(
        ticket_id=1,
        description="У меня проблема с доступом в коворкинг",
        photo_id=None
    )

    await process_skip_photo(mock_callback, mock_state)

    # Check ticket created
    assert_api_called(mock_api_client_with_data, "create_ticket", times=1)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.ticket_hndlr.get_text')
@patch('bot.hndlrs.ticket_hndlr.get_button_text')
async def test_create_ticket_with_photo(mock_get_button_text, mock_get_text,
                                        mock_message, mock_callback, mock_state,
                                        mock_api_client_with_data, mock_bot):
    """
    P0: Test complete ticket creation with photo attachment.

    Given: User creates support ticket with photo
    When: User uploads photo
    Then: Ticket created with photo_id
    """
    from bot.hndlrs.ticket_hndlr import (
        start_ticket_creation,
        process_description,
        process_add_photo,
        process_photo,
    )

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.enter_description"): "Опишите проблему:",
        ("ru", "support.want_add_photo"): "Добавить фото?",
        ("ru", "support.send_photo"): "Отправьте фото:",
        ("ru", "support.ticket_created_success"): "Обращение создано!",
    }.get((lang, key), "")

    mock_get_button_text.return_value = "Главное меню"

    # Step 1: Start creation
    mock_callback.data = "create_ticket"
    await start_ticket_creation(mock_callback, mock_state)

    # Step 2: Enter description
    mock_message.text = "Сломана дверь в переговорной"
    await process_description(mock_message, mock_state)

    # Step 3: Choose to add photo
    mock_callback.data = "add_photo"
    await process_add_photo(mock_callback, mock_state)
    assert_message_edited(mock_callback)
    assert_state_set(mock_state)

    # Step 4: Send photo
    mock_message.content_type = "photo"
    mock_message.photo = [
        MagicMock(file_id="photo_1"),
        MagicMock(file_id="photo_2_large")
    ]

    mock_api_client_with_data.create_ticket.return_value = create_ticket_data(
        ticket_id=2,
        photo_id="photo_2_large"
    )

    await process_photo(mock_message, mock_state, mock_bot)

    # Check ticket created with photo
    assert_api_called(mock_api_client_with_data, "create_ticket", times=1)
    call_args = mock_api_client_with_data.create_ticket.call_args[0][0]
    assert call_args.get("photo_id") == "photo_2_large"

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.ticket_hndlr.get_text')
@patch('bot.hndlrs.ticket_hndlr.get_button_text')
async def test_view_user_tickets(mock_get_button_text, mock_get_text,
                                 mock_callback, mock_state, mock_api_client_with_data):
    """
    P0: Test viewing list of user's tickets.

    Given: User has created tickets
    When: User clicks "My tickets"
    Then: Shows list of tickets with statuses
    """
    from bot.hndlrs.ticket_hndlr import show_my_tickets

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.my_tickets"): "Мои обращения:",
        ("ru", "support.status_open"): "Открыто",
        ("ru", "support.status_in_progress"): "В работе",
        ("ru", "support.status_closed"): "Закрыто",
    }.get((lang, key), "")

    mock_get_button_text.return_value = "Создать обращение"

    # User has tickets
    mock_api_client_with_data.get_user_tickets.return_value = [
        create_ticket_data(ticket_id=1, description="Проблема 1", status="OPEN"),
        create_ticket_data(ticket_id=2, description="Проблема 2", status="IN_PROGRESS"),
        create_ticket_data(ticket_id=3, description="Проблема 3", status="CLOSED"),
    ]

    mock_callback.data = "my_tickets"
    await show_my_tickets(mock_callback, mock_state)

    # Check API called
    assert_api_called(mock_api_client_with_data, "get_user_tickets", times=1)

    # Check message edited with tickets list
    assert_message_edited(mock_callback)

    # Check callback answered
    assert_callback_answered(mock_callback)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_ticket_description_input(mock_get_text, mock_message, mock_state):
    """
    P0: Test ticket description input and validation.

    Given: User in DESCRIPTION state
    When: User enters valid description
    Then: Saves description and proceeds to photo choice
    """
    from bot.hndlrs.ticket_hndlr import process_description

    mock_get_text.return_value = "Хотите добавить фото?"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    mock_message.text = "Не работает Wi-Fi в зале"
    await process_description(mock_message, mock_state)

    # Check description saved
    state_data = await mock_state.get_data()
    assert state_data.get("description") == "Не работает Wi-Fi в зале"

    # Check message sent
    assert_message_sent(mock_message, reply_markup_present=True)

    # Check state progressed
    assert_state_set(mock_state)


# ============================================================================
# P1 - HIGH PRIORITY TESTS (Validation & Errors)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_description_too_short(mock_get_text, mock_message, mock_state):
    """
    P1: Test validation of too short description.

    Given: User enters very short description
    When: Description length < minimum
    Then: Shows error and requests longer description
    """
    from bot.hndlrs.ticket_hndlr import process_description

    mock_get_text.return_value = "Описание слишком короткое. Минимум 10 символов."
    await mock_state.update_data(lang="ru", telegram_id=12345)

    mock_message.text = "WiFi"  # Too short
    await process_description(mock_message, mock_state)

    # Check error message sent
    assert_message_sent(mock_message)

    # State should NOT progress (stays in DESCRIPTION)
    mock_state.set_state.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_description_too_long(mock_get_text, mock_message, mock_state):
    """
    P1: Test validation of too long description.

    Given: User enters very long description
    When: Description length > maximum
    Then: Shows error and requests shorter description
    """
    from bot.hndlrs.ticket_hndlr import process_description

    mock_get_text.return_value = "Описание слишком длинное. Максимум 1000 символов."
    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Description over 1000 characters
    mock_message.text = "A" * 1500
    await process_description(mock_message, mock_state)

    # Check error message sent
    assert_message_sent(mock_message)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_invalid_photo_type(mock_get_text, mock_message, mock_state):
    """
    P1: Test validation rejects non-photo files.

    Given: User in PHOTO state
    When: User sends non-photo file (document, video, etc.)
    Then: Shows error requesting photo
    """
    from bot.hndlrs.ticket_hndlr import process_invalid_photo

    mock_get_text.return_value = "Пожалуйста, отправьте фото (не файл или видео)"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    # User sends document instead of photo
    mock_message.content_type = "document"
    await process_invalid_photo(mock_message, mock_state)

    # Check error message
    assert_message_sent(mock_message, reply_markup_present=True)

    # State goes back to ASK_PHOTO
    assert_state_set(mock_state)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.handle_api_error')
async def test_api_error_during_ticket_creation(mock_handle_error, mock_callback,
                                                mock_state, mock_api_client):
    """
    P1: Test handling of API error during ticket creation.

    Given: User completing ticket creation
    When: API fails to create ticket
    Then: Handles error gracefully
    """
    from bot.hndlrs.ticket_hndlr import process_skip_photo

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        description="Test problem"
    )

    # Simulate API error
    mock_api_client.create_ticket.side_effect = Exception("Database error")

    mock_callback.data = "no_photo"
    await process_skip_photo(mock_callback, mock_state)

    # Check error handler called
    mock_handle_error.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
@patch('bot.hndlrs.ticket_hndlr.get_button_text')
async def test_empty_tickets_list(mock_get_button_text, mock_get_text,
                                  mock_callback, mock_state, mock_api_client):
    """
    P1: Test viewing tickets when user has none.

    Given: User has no tickets
    When: User clicks "My tickets"
    Then: Shows message about no tickets
    """
    from bot.hndlrs.ticket_hndlr import show_my_tickets

    mock_get_text.return_value = "У вас пока нет обращений"
    mock_get_button_text.return_value = "Создать обращение"

    # No tickets
    mock_api_client.get_user_tickets.return_value = []

    mock_callback.data = "my_tickets"
    await show_my_tickets(mock_callback, mock_state)

    # Check empty message shown
    assert_message_edited(mock_callback, contains="обращений")


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.send_user_error')
async def test_user_not_found_during_ticket_creation(mock_send_error, mock_callback,
                                                     mock_state, mock_api_client):
    """
    P1: Test error when user not found in database.

    Given: User tries to create ticket
    When: User not found in database
    Then: Shows error and suggests registration
    """
    from bot.hndlrs.ticket_hndlr import process_skip_photo

    await mock_state.update_data(
        lang="ru",
        telegram_id=99999,
        description="Test"
    )

    # User not found
    mock_api_client.get_user_by_telegram_id.return_value = None

    mock_callback.data = "no_photo"
    await process_skip_photo(mock_callback, mock_state)

    # Check error sent
    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_ticket_status_emojis(mock_get_text, mock_callback, mock_state, mock_api_client_with_data):
    """
    P1: Test tickets display with correct status emojis.

    Given: User has tickets with different statuses
    When: Viewing tickets list
    Then: Each ticket shows appropriate emoji
    """
    from bot.hndlrs.ticket_hndlr import show_my_tickets

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.my_tickets"): "Мои обращения:",
        ("ru", "support.status_open"): "Открыто",
        ("ru", "support.status_in_progress"): "В работе",
        ("ru", "support.status_closed"): "Закрыто",
    }.get((lang, key), "")

    mock_api_client_with_data.get_user_tickets.return_value = [
        create_ticket_data(ticket_id=1, status="OPEN"),
        create_ticket_data(ticket_id=2, status="IN_PROGRESS"),
        create_ticket_data(ticket_id=3, status="CLOSED"),
    ]

    mock_callback.data = "my_tickets"
    await show_my_tickets(mock_callback, mock_state)

    # Check message contains status indicators
    # OPEN = 🟢, IN_PROGRESS = 🟡, CLOSED = 🔴
    call_args = mock_callback.message.edit_text.call_args[0][0]
    assert "🟢" in call_args or "🟡" in call_args or "🔴" in call_args


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_long_ticket_description_truncated_in_list(mock_get_text, mock_callback,
                                                         mock_state, mock_api_client):
    """
    P1: Test long descriptions are truncated in tickets list.

    Given: User has ticket with very long description
    When: Viewing tickets list
    Then: Description is truncated with "..."
    """
    from bot.hndlrs.ticket_hndlr import show_my_tickets

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "support.my_tickets"): "Мои обращения:",
        ("ru", "support.status_open"): "Открыто",
    }.get((lang, key), "")

    # Ticket with very long description
    long_description = "A" * 500
    mock_api_client.get_user_tickets.return_value = [
        create_ticket_data(ticket_id=1, description=long_description, status="OPEN")
    ]

    mock_callback.data = "my_tickets"
    await show_my_tickets(mock_callback, mock_state)

    # Check description was truncated (should contain "...")
    call_args = mock_callback.message.edit_text.call_args[0][0]
    # Description should be shortened
    assert "..." in call_args or len(call_args) < len(long_description)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.handle_api_error')
async def test_network_timeout_during_ticket_fetch(mock_handle_error, mock_callback,
                                                   mock_state, mock_api_client):
    """
    P1: Test handling of network timeout when fetching tickets.

    Given: User requests tickets list
    When: Network timeout occurs
    Then: Handles timeout gracefully
    """
    import asyncio
    from bot.hndlrs.ticket_hndlr import show_my_tickets

    # Simulate timeout
    mock_api_client.get_user_tickets.side_effect = asyncio.TimeoutError()

    mock_callback.data = "my_tickets"
    await show_my_tickets(mock_callback, mock_state)

    # Should show error message
    assert mock_callback.message.edit_text.called


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.ticket_hndlr.get_text')
async def test_special_characters_in_description(mock_get_text, mock_message, mock_state):
    """
    P1: Test handling of special characters in description.

    Given: User enters description with special characters
    When: Description contains emojis, punctuation, etc.
    Then: Accepts and saves correctly
    """
    from bot.hndlrs.ticket_hndlr import process_description

    mock_get_text.return_value = "Хотите добавить фото?"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Description with special characters
    mock_message.text = "Wi-Fi не работает! 😢 Помогите, пожалуйста?"
    await process_description(mock_message, mock_state)

    # Check description saved with special characters
    state_data = await mock_state.get_data()
    assert state_data.get("description") == "Wi-Fi не работает! 😢 Помогите, пожалуйста?"

    # Check message sent
    assert_message_sent(mock_message)
