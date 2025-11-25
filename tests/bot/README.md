# Telegram Bot Tests

Comprehensive test suite for the Coworking Management System Telegram bot.

## 📋 Overview

This test suite covers all bot functionality including:
- **Registration flow** - User registration with FSM states
- **Booking flow** - Tariff selection, date/time input, payment processing
- **Support tickets** - Ticket creation with photo attachments
- **Middlewares** - FSM timeout, ban checking, error logging
- **Error handling** - All error categories and user-facing messages
- **Localization** - Message translations and formatting

**Total Tests**: ~90 tests covering P0 (critical) and P1 (high priority) scenarios

## 🚀 Quick Start

### Running All Bot Tests

```bash
# From project root
pytest tests/bot/

# With verbose output
pytest tests/bot/ -v

# With coverage report
pytest tests/bot/ --cov=bot --cov-report=html
```

### Running Specific Test Categories

```bash
# Unit tests only (error handler, localization)
pytest tests/bot/unit/

# Handler tests only
pytest tests/bot/handlers/

# Middleware tests only
pytest tests/bot/middlewares/

# Specific test file
pytest tests/bot/handlers/test_registration_hndlr.py

# Specific test function
pytest tests/bot/handlers/test_registration_hndlr.py::test_registration_happy_path
```

### Running by Test Markers

```bash
# P0 critical tests only
pytest tests/bot/ -m p0

# P1 high priority tests only
pytest tests/bot/ -m p1

# Skip slow tests
pytest tests/bot/ -m "not slow"
```

## 📁 Test Structure

```
tests/bot/
├── conftest.py              # Shared fixtures (mocks, test data)
├── utils.py                 # Helper functions for assertions
├── README.md                # This file
│
├── unit/                    # Unit tests for utilities
│   ├── test_error_handler.py      (~10 tests)
│   └── test_localization.py       (~12 tests)
│
├── handlers/                # Integration tests for handlers
│   ├── test_registration_hndlr.py (~27 tests)
│   ├── test_booking_hndlr.py      (~25 tests)
│   └── test_ticket_hndlr.py       (~10 tests)
│
└── middlewares/             # Middleware tests
    ├── test_fsm_timeout.py        (~10 tests)
    └── test_ban_check.py          (~5 tests)
```

## 🧪 Test Priorities

Tests are organized by priority level:

### P0 - Critical (Must Pass) ⚠️

These test the essential happy paths that users take:
- Complete registration flow
- Successful booking with payment
- Successful booking without payment (meeting room)
- Ticket creation with/without photo
- Basic API client operations

**Command**: `pytest tests/bot/ -m p0`

### P1 - High Priority (Should Pass) 📌

These test validation, error handling, and edge cases:
- Input validation (phone, email, date, time formats)
- API error responses (network, timeout, not found)
- FSM state transitions and timeouts
- Payment flows (cancel, fail, timeout)
- Middleware functionality

**Command**: `pytest tests/bot/ -m p1`

### P2 - Medium Priority (Nice to Have) 💡

Additional edge cases and optimizations (not yet implemented):
- Performance under load
- Concurrent user sessions
- Retry mechanisms
- Advanced error recovery

## 🔧 Available Fixtures

### Mock Objects (from conftest.py)

```python
def test_example(mock_message, mock_callback, mock_state, mock_api_client):
    """
    All aiogram components are mocked by default.

    Available fixtures:
    - mock_user: Mock Telegram user
    - mock_banned_user: Mock banned user
    - mock_chat: Mock Telegram chat
    - mock_message: Mock message with answer(), edit_text()
    - mock_callback: Mock callback query with answer()
    - mock_bot: Mock Bot instance with send_message(), send_photo()
    - mock_state: Mock FSM context with get_data(), set_state(), clear()
    - mock_api_client: Mock API client with all endpoints
    - mock_api_client_with_data: API client pre-configured with sample responses
    """
    pass
```

### Test Data Builders (from utils.py)

```python
from tests.bot.utils import (
    create_user_data,
    create_tariff_data,
    create_booking_data,
    create_ticket_data
)

def test_with_custom_data():
    user = create_user_data(telegram_id=99999, email="custom@test.com")
    tariff = create_tariff_data(price=1000.0, duration_hours=12)
    # ... use in test
```

### Assertion Helpers (from utils.py)

```python
from tests.bot.utils import (
    assert_message_sent,
    assert_message_edited,
    assert_callback_answered,
    assert_state_cleared,
    assert_state_set,
    assert_error_message_sent,
    assert_api_called
)

async def test_registration():
    # ... call handler

    # Check message was sent
    assert_message_sent(message, contains="Регистрация завершена")

    # Check state was cleared
    assert_state_cleared(state)

    # Check API was called
    assert_api_called(api_client, "create_user", times=1)
```

## ✍️ Writing New Tests

### Basic Test Template

```python
import pytest
from tests.bot.utils import assert_message_sent, assert_state_set

@pytest.mark.asyncio
@pytest.mark.p1  # or p0, p2
async def test_my_feature(mock_message, mock_state, mock_api_client):
    """
    Test description: what this test verifies

    Given: initial conditions
    When: action performed
    Then: expected outcome
    """
    # Arrange
    mock_message.text = "test input"
    mock_state._data = {"lang": "ru"}

    # Act
    from bot.hndlrs.my_handler import my_handler_function
    await my_handler_function(mock_message, mock_state)

    # Assert
    assert_message_sent(mock_message, contains="expected text")
    assert_state_set(mock_state)
```

### Testing FSM States

```python
@pytest.mark.asyncio
async def test_fsm_state_transition(mock_message, mock_state):
    """Test FSM transitions between states."""
    # Set initial state
    await mock_state.set_state("Registration:FULL_NAME")
    await mock_state.update_data(lang="ru")

    # Trigger handler
    mock_message.text = "Иван Иванов"
    await process_full_name(mock_message, mock_state)

    # Verify state changed
    assert_state_set(mock_state, "Registration:PHONE")
```

### Testing Error Handling

```python
from tests.bot.utils import simulate_api_error, assert_error_message_sent

@pytest.mark.asyncio
async def test_api_network_error(mock_message, mock_api_client):
    """Test handling of network errors."""
    # Simulate network error
    simulate_api_error(mock_api_client, "create_user", error_type="network")

    # Trigger handler
    mock_message.text = "test@example.com"
    await process_email(mock_message, mock_state)

    # Verify error message sent
    assert_error_message_sent(mock_message, error_key="api_unavailable")
```

### Testing with Mock API Data

```python
@pytest.mark.asyncio
async def test_with_api_data(mock_message, mock_api_client_with_data):
    """
    Test with pre-configured API responses.

    mock_api_client_with_data comes with:
    - User data (telegram_id=12345)
    - Tariff data (2 tariffs)
    - Booking creation response
    - Ticket creation response
    """
    # API client already configured, just call handler
    await my_handler(mock_message, mock_state)

    # Assertions...
```

## 🐛 Debugging Tests

### Print Mock Call History

```python
def test_debug_calls(mock_message):
    # ... test code

    # Print all calls to answer()
    print(mock_message.answer.call_args_list)

    # Print last call arguments
    print(mock_message.answer.call_args)
```

### Run Single Test with Full Output

```bash
pytest tests/bot/handlers/test_registration_hndlr.py::test_my_test -v -s
```

### Use pytest debugger

```python
def test_with_debugger(mock_message):
    # ... test code

    import pytest; pytest.set_trace()  # Breakpoint

    # Continue testing
```

### Check Coverage for Specific Module

```bash
pytest tests/bot/handlers/test_registration_hndlr.py \
    --cov=bot.hndlrs.registration_hndlr \
    --cov-report=term-missing
```

## 📊 Coverage Goals

| Module | Target Coverage | Current |
|--------|----------------|---------|
| bot/hndlrs/registration_hndlr.py | 85% | TBD |
| bot/hndlrs/booking_hndlr.py | 85% | TBD |
| bot/hndlrs/ticket_hndlr.py | 85% | TBD |
| bot/middlewares/fsm_timeout.py | 90% | TBD |
| bot/utils/error_handler.py | 95% | TBD |
| bot/utils/localization.py | 100% | TBD |

**Overall Target**: >85% code coverage for bot module

## 🔄 CI/CD Integration

Tests run automatically on:
- Every push to `main` branch
- Every pull request
- Nightly at 2 AM UTC

### GitHub Actions Workflow

See `.github/workflows/bot-tests.yml` for configuration.

```yaml
# Workflow runs:
# 1. Install dependencies
# 2. Run pytest with coverage
# 3. Upload coverage report
# 4. Fail PR if coverage < 85%
```

### Local Pre-commit Hook (Optional)

```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
pytest tests/bot/ -m p0 || exit 1
```

## 🆘 Troubleshooting

### "No module named 'bot'"

Make sure you're running pytest from the project root:
```bash
cd /path/to/co-work_spa
pytest tests/bot/
```

### "coroutine was never awaited" warnings

Ensure all test functions that call async handlers are marked with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_my_async_handler(...):
    await my_handler(...)
```

### Mock not being called

Check if the import path in your patch matches the actual usage:
```python
# If handler imports: from utils.api_client import get_api_client
# Then patch: 'utils.api_client.get_api_client'

# NOT: 'bot.hndlrs.registration_hndlr.get_api_client'
```

### API client not mocked

Ensure `mock_get_api_client` autouse fixture is active. It should be by default from conftest.py.

## 📚 Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
- [aiogram testing guide](https://docs.aiogram.dev/en/latest/testing.html)

## 🤝 Contributing

When adding new bot features, please:

1. **Write tests first** (TDD approach recommended)
2. **Mark with appropriate priority**: `@pytest.mark.p0` / `@pytest.mark.p1` / `@pytest.mark.p2`
3. **Add docstrings** explaining Given/When/Then
4. **Use helper functions** from utils.py for consistency
5. **Ensure tests are isolated** - no shared state between tests
6. **Run full test suite** before committing: `pytest tests/bot/`

## 📝 Test Checklist

For each new bot handler or feature:

- [ ] Happy path test (P0)
- [ ] Input validation tests (P1)
- [ ] API error handling tests (P1)
- [ ] FSM state transition tests (P1)
- [ ] Edge cases (empty input, special characters) (P1/P2)
- [ ] Localization for both Russian and English (P1)
- [ ] Timeout scenarios (P1)
- [ ] Middleware interactions (P1)

---

**Last Updated**: 2025-01-24
**Maintained by**: Development Team
**Questions?**: Contact via support tickets in the bot
