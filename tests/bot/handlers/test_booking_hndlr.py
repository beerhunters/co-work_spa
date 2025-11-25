"""
Integration tests for bot.hndlrs.booking_hndlr module.

Tests cover:
P0 (Critical):
- Complete booking with payment
- Complete booking without payment (meeting room)
- Tariff selection
- Payment successful flow
- Booking cancellation

P1 (High Priority):
- Date validation
- Time validation
- Duration validation
- Promocode application
- Payment timeout
- Payment cancel
- API errors
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from tests.bot.utils import (
    assert_message_sent,
    assert_message_edited,
    assert_callback_answered,
    assert_state_set,
    assert_state_cleared,
    assert_api_called,
    create_tariff_data,
    create_booking_data,
)


# ============================================================================
# P0 - CRITICAL TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_booking_menu_shows_tariffs(mock_get_text, mock_callback, mock_state, mock_api_client_with_data):
    """
    P0: Test booking menu displays available tariffs.

    Given: User clicks "Book" button
    When: booking_menu() handler is called
    Then: Shows list of available tariffs with prices
    """
    from bot.hndlrs.booking_hndlr import booking_menu

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.select_tariff"): "Выберите тариф:",
        ("ru", "booking.tariff_price"): "{price} ₽",
    }.get((lang, key), "")

    mock_callback.data = "booking"
    await booking_menu(mock_callback, mock_state)

    # Check callback answered
    assert_callback_answered(mock_callback)

    # Check message edited with tariffs
    assert_message_edited(mock_callback)

    # Check API called to get tariffs
    assert_api_called(mock_api_client_with_data, "get_tariffs", times=1)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_complete_booking_with_payment(mock_get_text, mock_callback, mock_message,
                                              mock_state, mock_api_client_with_data, mock_bot):
    """
    P0: Test complete booking flow with payment.

    Given: User books paid workspace
    When: All steps completed and payment successful
    Then: Booking created with CONFIRMED status
    """
    from bot.hndlrs.booking_hndlr import (
        process_tariff_selection,
        process_date_input,
        process_time_input,
        process_skip_promocode,
        process_payment_success,
    )

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.enter_date"): "Введите дату (ДД.ММ.ГГГГ):",
        ("ru", "booking.enter_time"): "Введите время (ЧЧ:ММ):",
        ("ru", "booking.enter_promocode"): "Введите промокод или пропустите:",
        ("ru", "booking.payment_required"): "Необходима оплата {price} ₽",
        ("ru", "booking.payment_success"): "Оплата прошла успешно!",
        ("ru", "booking.confirmed"): "Бронирование подтверждено",
    }.get((lang, key), "")

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Step 1: Select tariff (paid workspace)
    mock_callback.data = "select_tariff_1"
    mock_api_client_with_data.get_tariffs.return_value = [
        create_tariff_data(tariff_id=1, price=500.0, requires_payment=True)
    ]
    await process_tariff_selection(mock_callback, mock_state)
    assert_callback_answered(mock_callback)

    # Step 2: Enter date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    mock_message.text = tomorrow
    await process_date_input(mock_message, mock_state)
    assert_message_sent(mock_message)

    # Step 3: Enter time
    mock_message.text = "10:00"
    await process_time_input(mock_message, mock_state)
    assert_message_sent(mock_message)

    # Step 4: Skip promocode
    mock_callback.data = "skip_promocode"
    await process_skip_promocode(mock_callback, mock_state)

    # Step 5: Payment successful
    mock_api_client_with_data.create_booking.return_value = create_booking_data(
        booking_id=1,
        status="CONFIRMED",
        total_price=500.0
    )
    mock_callback.data = "payment_success_1"
    await process_payment_success(mock_callback, mock_state)

    # Check booking created
    assert_api_called(mock_api_client_with_data, "create_booking", times=1)

    # Check success message sent
    assert_callback_answered(mock_callback)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_complete_booking_without_payment(mock_get_text, mock_callback, mock_message,
                                                 mock_state, mock_api_client_with_data):
    """
    P0: Test complete booking flow without payment (meeting room).

    Given: User books free meeting room
    When: All steps completed
    Then: Booking created immediately without payment
    """
    from bot.hndlrs.booking_hndlr import (
        process_tariff_selection,
        process_date_input,
        process_time_input,
    )

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.enter_date"): "Введите дату:",
        ("ru", "booking.enter_time"): "Введите время:",
        ("ru", "booking.confirmed"): "Бронирование подтверждено!",
    }.get((lang, key), "")

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Select free tariff (meeting room)
    mock_callback.data = "select_tariff_2"
    mock_api_client_with_data.get_tariffs.return_value = [
        create_tariff_data(tariff_id=2, name="Переговорная", price=0.0, requires_payment=False)
    ]
    await process_tariff_selection(mock_callback, mock_state)

    # Enter date
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    mock_message.text = tomorrow
    await process_date_input(mock_message, mock_state)

    # Enter time - booking created immediately
    mock_message.text = "14:00"
    mock_api_client_with_data.create_booking.return_value = create_booking_data(
        booking_id=2,
        status="CONFIRMED",
        total_price=0.0
    )
    await process_time_input(mock_message, mock_state)

    # Check booking created
    assert_api_called(mock_api_client_with_data, "create_booking", times=1)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_tariff_selection(mock_get_text, mock_callback, mock_state, mock_api_client_with_data):
    """
    P0: Test tariff selection stores correct data.

    Given: Multiple tariffs available
    When: User selects a specific tariff
    Then: Tariff ID saved in state and proceeds to date input
    """
    from bot.hndlrs.booking_hndlr import process_tariff_selection

    mock_get_text.return_value = "Введите дату бронирования"
    await mock_state.update_data(lang="ru", telegram_id=12345)

    mock_callback.data = "select_tariff_1"
    mock_api_client_with_data.get_tariffs.return_value = [
        create_tariff_data(tariff_id=1)
    ]

    await process_tariff_selection(mock_callback, mock_state)

    # Check tariff_id saved
    state_data = await mock_state.get_data()
    assert state_data.get("tariff_id") == 1

    # Check message edited
    assert_callback_answered(mock_callback)

    # Check state progressed
    assert_state_set(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_booking_cancellation(mock_get_text, mock_callback, mock_state, mock_api_client):
    """
    P0: Test user can cancel booking.

    Given: User in booking flow
    When: User clicks "Cancel" button
    Then: Returns to main menu and clears state
    """
    from bot.hndlrs.booking_hndlr import cancel_booking

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.cancelled"): "Бронирование отменено",
        ("ru", "main_menu.title"): "Главное меню",
    }.get((lang, key), "")

    await mock_state.update_data(lang="ru", tariff_id=1, date="15.01.2025")

    mock_callback.data = "cancel_booking"
    await cancel_booking(mock_callback, mock_state)

    # Check message sent
    assert_callback_answered(mock_callback)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p0
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_payment_success_confirmation(mock_get_text, mock_callback, mock_state, mock_api_client_with_data):
    """
    P0: Test payment success creates and confirms booking.

    Given: User completes payment
    When: Payment webhook confirms success
    Then: Booking status updated to CONFIRMED
    """
    from bot.hndlrs.booking_hndlr import process_payment_success

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.payment_success"): "✅ Оплата успешна!",
        ("ru", "booking.confirmed"): "Ваше бронирование подтверждено",
    }.get((lang, key), "")

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025",
        time="10:00",
        duration=8
    )

    mock_callback.data = "payment_success_1"
    mock_api_client_with_data.create_booking.return_value = create_booking_data(
        booking_id=1,
        status="CONFIRMED"
    )

    await process_payment_success(mock_callback, mock_state)

    # Check booking created
    assert_api_called(mock_api_client_with_data, "create_booking", times=1)

    # Check success message
    assert_callback_answered(mock_callback)

    # Check state cleared
    assert_state_cleared(mock_state)


# ============================================================================
# P1 - HIGH PRIORITY TESTS (Validation & Errors)
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_invalid_date_format(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of invalid date formats.

    Given: User in date input state
    When: User enters invalid date format
    Then: Sends error with correct format example
    """
    from bot.hndlrs.booking_hndlr import process_date_input

    await mock_state.update_data(lang="ru", telegram_id=12345, tariff_id=1)

    invalid_dates = [
        "2025-01-15",  # Wrong format (YYYY-MM-DD)
        "15/01/2025",  # Wrong separator
        "32.01.2025",  # Invalid day
        "15.13.2025",  # Invalid month
        "abc",  # Not a date
    ]

    for invalid_date in invalid_dates:
        mock_message.text = invalid_date
        await process_date_input(mock_message, mock_state)
        mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_past_date_validation(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation prevents booking in the past.

    Given: User enters past date
    When: Date is in the past
    Then: Rejects with error message
    """
    from bot.hndlrs.booking_hndlr import process_date_input

    await mock_state.update_data(lang="ru", telegram_id=12345, tariff_id=1)

    # Yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%d.%m.%Y")
    mock_message.text = yesterday
    await process_date_input(mock_message, mock_state)

    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_invalid_time_format(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of invalid time formats.

    Given: User in time input state
    When: User enters invalid time format
    Then: Sends error with correct format example
    """
    from bot.hndlrs.booking_hndlr import process_time_input

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025"
    )

    invalid_times = [
        "25:00",  # Invalid hour
        "10:60",  # Invalid minute
        "10-00",  # Wrong separator
        "10",  # Missing minutes
        "abc",  # Not a time
    ]

    for invalid_time in invalid_times:
        mock_message.text = invalid_time
        await process_time_input(mock_message, mock_state)
        mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_promocode_application(mock_get_text, mock_message, mock_state, mock_api_client):
    """
    P1: Test promocode application reduces price.

    Given: User enters valid promocode
    When: Promocode is validated
    Then: Discount applied to booking price
    """
    from bot.hndlrs.booking_hndlr import process_promocode_input

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.promocode_applied"): "Промокод применен! Скидка: {discount}%",
        ("ru", "booking.final_price"): "Итого: {price} ₽",
    }.get((lang, key), "")

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025",
        time="10:00"
    )

    # Valid promocode
    mock_api_client.validate_promocode.return_value = {
        "valid": True,
        "discount_percent": 10,
        "code": "DISCOUNT10"
    }

    mock_message.text = "DISCOUNT10"
    await process_promocode_input(mock_message, mock_state)

    # Check API called
    assert_api_called(mock_api_client, "validate_promocode", times=1)

    # Check success message
    assert_message_sent(mock_message)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_invalid_promocode(mock_send_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test invalid promocode handling.

    Given: User enters invalid promocode
    When: Promocode validation fails
    Then: Shows error and allows to continue without discount
    """
    from bot.hndlrs.booking_hndlr import process_promocode_input

    await mock_state.update_data(lang="ru", telegram_id=12345)

    # Invalid promocode
    mock_api_client.validate_promocode.return_value = {
        "valid": False,
        "error": "Promocode not found"
    }

    mock_message.text = "INVALID"
    await process_promocode_input(mock_message, mock_state)

    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_payment_timeout(mock_get_text, mock_callback, mock_state):
    """
    P1: Test payment timeout handling.

    Given: User initiated payment
    When: Payment times out
    Then: Booking cancelled and user notified
    """
    from bot.hndlrs.booking_hndlr import process_payment_timeout

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.payment_timeout"): "⏱ Время оплаты истекло",
        ("ru", "booking.try_again"): "Попробуйте снова",
    }.get((lang, key), "")

    await mock_state.update_data(lang="ru", booking_id=1)

    mock_callback.data = "payment_timeout_1"
    await process_payment_timeout(mock_callback, mock_state)

    # Check message sent
    assert_callback_answered(mock_callback)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_payment_cancelled_by_user(mock_get_text, mock_callback, mock_state):
    """
    P1: Test user-initiated payment cancellation.

    Given: User in payment process
    When: User cancels payment
    Then: Booking not created, returns to main menu
    """
    from bot.hndlrs.booking_hndlr import process_payment_cancel

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.payment_cancelled"): "Оплата отменена",
        ("ru", "main_menu.title"): "Главное меню",
    }.get((lang, key), "")

    await mock_state.update_data(lang="ru", booking_id=1)

    mock_callback.data = "payment_cancel_1"
    await process_payment_cancel(mock_callback, mock_state)

    # Check cancelled message
    assert_callback_answered(mock_callback)

    # Check state cleared
    assert_state_cleared(mock_state)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.handle_api_error')
async def test_api_error_during_booking_creation(mock_handle_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test handling of API error during booking creation.

    Given: User completing booking
    When: API fails to create booking
    Then: Handles error gracefully
    """
    from bot.hndlrs.booking_hndlr import process_time_input

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=2,
        date="15.01.2025",
        requires_payment=False
    )

    # Simulate API error
    mock_api_client.create_booking.side_effect = Exception("Database error")

    mock_message.text = "10:00"
    await process_time_input(mock_message, mock_state)

    # Check error handler called
    mock_handle_error.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_booking_overlap_validation(mock_send_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test validation prevents overlapping bookings.

    Given: User tries to book already occupied time slot
    When: Time slot check reveals conflict
    Then: Rejects booking with error
    """
    from bot.hndlrs.booking_hndlr import process_time_input

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025"
    )

    # Simulate overlap error from API
    mock_api_client.create_booking.return_value = {
        "error": "Time slot already booked"
    }

    mock_message.text = "10:00"
    await process_time_input(mock_message, mock_state)

    # Should handle overlap error
    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_duration_selection(mock_get_text, mock_callback, mock_state):
    """
    P1: Test duration selection for hourly bookings.

    Given: User booking hourly workspace
    When: User selects duration
    Then: Duration saved and proceeds to payment
    """
    from bot.hndlrs.booking_hndlr import process_duration_selection

    mock_get_text.return_value = "Вы выбрали 4 часа"
    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025",
        time="10:00"
    )

    mock_callback.data = "duration_4"
    await process_duration_selection(mock_callback, mock_state)

    # Check duration saved
    state_data = await mock_state.get_data()
    assert state_data.get("duration") == 4

    # Check callback answered
    assert_callback_answered(mock_callback)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_invalid_duration_value(mock_send_error, mock_message, mock_state):
    """
    P1: Test validation of invalid duration values.

    Given: User enters custom duration
    When: Duration is invalid (negative, zero, too large)
    Then: Rejects with error
    """
    from bot.hndlrs.booking_hndlr import process_duration_input

    await mock_state.update_data(lang="ru", telegram_id=12345)

    invalid_durations = [
        "0",  # Zero hours
        "-5",  # Negative
        "100",  # Too many hours
        "abc",  # Not a number
    ]

    for duration in invalid_durations:
        mock_message.text = duration
        await process_duration_input(mock_message, mock_state)
        mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_booking_summary_display(mock_get_text, mock_message, mock_state, mock_api_client_with_data):
    """
    P1: Test booking summary shows all details before payment.

    Given: User completed all inputs
    When: About to proceed to payment
    Then: Shows summary with all booking details
    """
    from bot.hndlrs.booking_hndlr import show_booking_summary

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.summary_title"): "Детали бронирования:",
        ("ru", "booking.summary_tariff"): "Тариф: {tariff}",
        ("ru", "booking.summary_date"): "Дата: {date}",
        ("ru", "booking.summary_time"): "Время: {time}",
        ("ru", "booking.summary_price"): "Цена: {price} ₽",
    }.get((lang, key), "")

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=1,
        date="15.01.2025",
        time="10:00",
        duration=8,
        price=500.0
    )

    await show_booking_summary(mock_message, mock_state)

    # Check summary message sent
    assert_message_sent(mock_message, reply_markup_present=True)


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.handle_api_error')
async def test_network_timeout_during_booking(mock_handle_error, mock_message, mock_state, mock_api_client):
    """
    P1: Test handling of network timeout during booking.

    Given: User creating booking
    When: Network timeout occurs
    Then: Handles timeout with retry option
    """
    import asyncio
    from bot.hndlrs.booking_hndlr import process_time_input

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=2,
        date="15.01.2025"
    )

    # Simulate timeout
    mock_api_client.create_booking.side_effect = asyncio.TimeoutError()

    mock_message.text = "10:00"
    await process_time_input(mock_message, mock_state)

    # Check timeout handled
    mock_handle_error.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.send_user_error')
async def test_tariff_not_available(mock_send_error, mock_callback, mock_state, mock_api_client):
    """
    P1: Test handling when selected tariff is no longer available.

    Given: User selects a tariff
    When: Tariff is no longer available or deleted
    Then: Shows error and returns to tariff selection
    """
    from bot.hndlrs.booking_hndlr import process_tariff_selection

    await mock_state.update_data(lang="ru", telegram_id=12345)

    mock_callback.data = "select_tariff_999"
    mock_api_client.get_tariffs.return_value = []  # No tariffs

    await process_tariff_selection(mock_callback, mock_state)

    mock_send_error.assert_called()


@pytest.mark.asyncio
@pytest.mark.p1
@patch('bot.hndlrs.booking_hndlr.get_text')
async def test_early_morning_booking_warning(mock_get_text, mock_message, mock_state):
    """
    P1: Test warning for very early morning bookings.

    Given: User books before 7 AM
    When: Time is entered
    Then: Shows confirmation that coworking may be closed
    """
    from bot.hndlrs.booking_hndlr import process_time_input

    mock_get_text.side_effect = lambda lang, key, **kwargs: {
        ("ru", "booking.early_warning"): "⚠️ Коворкинг открывается в 8:00",
        ("ru", "booking.confirm_early"): "Подтвердить?",
    }.get((lang, key), "")

    await mock_state.update_data(
        lang="ru",
        telegram_id=12345,
        tariff_id=2,
        date="15.01.2025"
    )

    mock_message.text = "06:00"
    await process_time_input(mock_message, mock_state)

    # Should show warning
    assert_message_sent(mock_message)
