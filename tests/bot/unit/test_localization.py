"""
Unit tests for bot.utils.localization module.

Tests cover:
- Localization class initialization
- Translation loading and retrieval
- Language normalization
- Nested key access
- Button text retrieval
- Pluralization
- User language retrieval
"""

import pytest
from unittest.mock import patch, mock_open, MagicMock
import json

from bot.utils.localization import (
    Localization,
    get_localization,
    get_text,
    get_button_text,
    pluralize_hours,
    get_user_language,
)


# Sample translations for testing
SAMPLE_RU_TRANSLATIONS = {
    "welcome": {
        "title": "Добро пожаловать",
        "message": "Привет, {name}!"
    },
    "buttons": {
        "start": "Начать",
        "cancel": "Отмена",
        "back": "Назад"
    },
    "errors": {
        "general": "Произошла ошибка",
        "not_found": "Не найдено"
    },
    "booking": {
        "hours_one": "час",
        "hours_few": "часа",
        "hours_many": "часов"
    }
}

SAMPLE_EN_TRANSLATIONS = {
    "welcome": {
        "title": "Welcome",
        "message": "Hello, {name}!"
    },
    "buttons": {
        "start": "Start",
        "cancel": "Cancel"
    }
}


# ============================================================================
# Test Localization Class Initialization
# ============================================================================

@pytest.mark.unit
@patch('bot.utils.localization.Path')
@patch('builtins.open', new_callable=mock_open, read_data=json.dumps(SAMPLE_RU_TRANSLATIONS))
def test_localization_init_loads_translations(mock_file, mock_path):
    """
    Test Localization initialization loads translation files.

    Given: Translation files exist in locales directory
    When: Localization() is instantiated
    Then: Loads translations for all supported languages
    """
    # Mock path operations
    mock_locale_dir = MagicMock()
    mock_path.return_value.__truediv__.return_value = mock_locale_dir
    mock_locale_dir.__truediv__.return_value.exists.return_value = True

    loc = Localization()

    assert loc.default_language == "ru"
    assert loc.supported_languages == ["ru", "en"]
    # Translations should be loaded (mocked)
    assert isinstance(loc.translations, dict)


@pytest.mark.unit
def test_localization_default_values():
    """
    Test Localization has correct default values.

    Given: Fresh Localization instance
    When: Checking default attributes
    Then: Has expected default language and supported languages
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()

    assert loc.default_language == "ru"
    assert "ru" in loc.supported_languages
    assert "en" in loc.supported_languages


# ============================================================================
# Test normalize_language_code()
# ============================================================================

@pytest.mark.unit
def test_normalize_language_code_russian():
    """
    Test language code normalization for Russian.

    Given: Various Russian language codes
    When: normalize_language_code() is called
    Then: Returns 'ru'
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()

    assert loc.normalize_language_code("ru") == "ru"
    assert loc.normalize_language_code("RU") == "ru"
    assert loc.normalize_language_code("ru_RU") == "ru"
    assert loc.normalize_language_code("Russian") == "ru"


@pytest.mark.unit
def test_normalize_language_code_english():
    """
    Test language code normalization for English.

    Given: Various English language codes
    When: normalize_language_code() is called
    Then: Returns 'en'
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()

    assert loc.normalize_language_code("en") == "en"
    assert loc.normalize_language_code("EN") == "en"
    assert loc.normalize_language_code("en_US") == "en"
    assert loc.normalize_language_code("English") == "en"


@pytest.mark.unit
def test_normalize_language_code_unsupported():
    """
    Test language code normalization for unsupported languages.

    Given: Unsupported language codes
    When: normalize_language_code() is called
    Then: Returns default language 'ru'
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()

    assert loc.normalize_language_code("fr") == "ru"
    assert loc.normalize_language_code("de") == "ru"
    assert loc.normalize_language_code("es") == "ru"
    assert loc.normalize_language_code("unknown") == "ru"


@pytest.mark.unit
def test_normalize_language_code_none_or_empty():
    """
    Test language code normalization for None or empty string.

    Given: None or empty language code
    When: normalize_language_code() is called
    Then: Returns default language 'ru'
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()

    assert loc.normalize_language_code(None) == "ru"
    assert loc.normalize_language_code("") == "ru"


# ============================================================================
# Test _get_nested_translation()
# ============================================================================

@pytest.mark.unit
def test_get_nested_translation_simple_key():
    """
    Test getting translation for simple key path.

    Given: Simple key path like "errors.general"
    When: _get_nested_translation() is called
    Then: Returns translated string
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc._get_nested_translation("ru", "errors.general")
    assert result == "Произошла ошибка"


@pytest.mark.unit
def test_get_nested_translation_nested_key():
    """
    Test getting translation for nested key path.

    Given: Nested key path like "welcome.message"
    When: _get_nested_translation() is called
    Then: Returns translated string
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc._get_nested_translation("ru", "welcome.message")
    assert result == "Привет, {name}!"


@pytest.mark.unit
def test_get_nested_translation_not_found():
    """
    Test getting translation for non-existent key.

    Given: Non-existent key path
    When: _get_nested_translation() is called
    Then: Returns None
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc._get_nested_translation("ru", "nonexistent.key")
    assert result is None


@pytest.mark.unit
def test_get_nested_translation_unsupported_language():
    """
    Test getting translation for unsupported language.

    Given: Language not in translations dict
    When: _get_nested_translation() is called
    Then: Returns None
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc._get_nested_translation("fr", "welcome.title")
    assert result is None


@pytest.mark.unit
def test_get_nested_translation_non_string_value():
    """
    Test getting translation when value is not a string.

    Given: Key path points to a dict, not a string
    When: _get_nested_translation() is called
    Then: Returns None
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    # "welcome" is a dict, not a string
    result = loc._get_nested_translation("ru", "welcome")
    assert result is None


# ============================================================================
# Test get_text()
# ============================================================================

@pytest.mark.unit
def test_get_text_simple():
    """
    Test get_text() with simple key and no formatting.

    Given: Valid key path and language
    When: get_text() is called
    Then: Returns translated string
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc.get_text("ru", "welcome.title")
    assert result == "Добро пожаловать"


@pytest.mark.unit
def test_get_text_with_formatting():
    """
    Test get_text() with string formatting.

    Given: Key with format placeholders and kwargs
    When: get_text() is called with **kwargs
    Then: Returns formatted translated string
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc.get_text("ru", "welcome.message", name="Иван")
    assert result == "Привет, Иван!"


@pytest.mark.unit
def test_get_text_fallback_to_default_language():
    """
    Test get_text() fallback when translation not found.

    Given: Key exists in default language but not in requested language
    When: get_text() is called with unsupported language
    Then: Falls back to default language translation
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {
            "ru": SAMPLE_RU_TRANSLATIONS,
            "en": SAMPLE_EN_TRANSLATIONS
        }

    # "back" button only exists in Russian
    result = loc.get_text("en", "buttons.back")
    assert result == "Назад"


@pytest.mark.unit
def test_get_text_key_not_found():
    """
    Test get_text() when key doesn't exist.

    Given: Non-existent key path
    When: get_text() is called
    Then: Returns key path in brackets
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc.get_text("ru", "nonexistent.key")
    assert result == "[nonexistent.key]"


@pytest.mark.unit
def test_get_text_formatting_error():
    """
    Test get_text() when formatting fails.

    Given: Format string but missing required kwargs
    When: get_text() is called without all required kwargs
    Then: Returns unformatted string
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    # Missing "name" parameter
    result = loc.get_text("ru", "welcome.message")
    assert result == "Привет, {name}!"  # Unformatted


# ============================================================================
# Test get_button_text()
# ============================================================================

@pytest.mark.unit
def test_get_button_text():
    """
    Test get_button_text() retrieves button translations.

    Given: Valid button key
    When: get_button_text() is called
    Then: Returns button text from buttons namespace
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc.get_button_text("ru", "start")
    assert result == "Начать"


@pytest.mark.unit
def test_get_button_text_not_found():
    """
    Test get_button_text() when button doesn't exist.

    Given: Non-existent button key
    When: get_button_text() is called
    Then: Returns key path in brackets
    """
    with patch.object(Localization, 'load_translations'):
        loc = Localization()
        loc.translations = {"ru": SAMPLE_RU_TRANSLATIONS}

    result = loc.get_button_text("ru", "nonexistent")
    assert result == "[buttons.nonexistent]"


# ============================================================================
# Test Global Helper Functions
# ============================================================================

@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
def test_global_get_text(mock_get_loc):
    """
    Test global get_text() function.

    Given: Global get_text() called
    When: Function is invoked
    Then: Delegates to Localization instance
    """
    mock_loc = MagicMock()
    mock_loc.get_text.return_value = "Test translation"
    mock_get_loc.return_value = mock_loc

    result = get_text("ru", "test.key", param="value")

    mock_loc.get_text.assert_called_once_with("ru", "test.key", param="value")
    assert result == "Test translation"


@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
def test_global_get_button_text(mock_get_loc):
    """
    Test global get_button_text() function.

    Given: Global get_button_text() called
    When: Function is invoked
    Then: Delegates to Localization instance
    """
    mock_loc = MagicMock()
    mock_loc.get_button_text.return_value = "Button text"
    mock_get_loc.return_value = mock_loc

    result = get_button_text("en", "start")

    mock_loc.get_button_text.assert_called_once_with("en", "start")
    assert result == "Button text"


@pytest.mark.unit
def test_get_localization_singleton():
    """
    Test get_localization() returns singleton instance.

    Given: Multiple calls to get_localization()
    When: Function is invoked multiple times
    Then: Returns same instance
    """
    # Reset global instance
    import bot.utils.localization as loc_module
    loc_module._localization = None

    with patch.object(Localization, 'load_translations'):
        instance1 = get_localization()
        instance2 = get_localization()

    assert instance1 is instance2


# ============================================================================
# Test pluralize_hours()
# ============================================================================

@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
@patch('bot.utils.localization.get_text')
def test_pluralize_hours_russian_one(mock_get_text, mock_get_loc):
    """
    Test pluralize_hours() for Russian with 1, 21, 31 hours.

    Given: Count ending in 1 (except 11)
    When: pluralize_hours() is called for Russian
    Then: Returns "час" (one hour)
    """
    mock_loc = MagicMock()
    mock_loc.normalize_language_code.return_value = "ru"
    mock_get_loc.return_value = mock_loc
    mock_get_text.return_value = "час"

    assert pluralize_hours(1, "ru") == "час"
    assert pluralize_hours(21, "ru") == "час"
    assert pluralize_hours(31, "ru") == "час"


@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
@patch('bot.utils.localization.get_text')
def test_pluralize_hours_russian_few(mock_get_text, mock_get_loc):
    """
    Test pluralize_hours() for Russian with 2-4, 22-24 hours.

    Given: Count ending in 2, 3, 4 (except 12-14)
    When: pluralize_hours() is called for Russian
    Then: Returns "часа" (few hours)
    """
    mock_loc = MagicMock()
    mock_loc.normalize_language_code.return_value = "ru"
    mock_get_loc.return_value = mock_loc
    mock_get_text.return_value = "часа"

    assert pluralize_hours(2, "ru") == "часа"
    assert pluralize_hours(3, "ru") == "часа"
    assert pluralize_hours(4, "ru") == "часа"
    assert pluralize_hours(22, "ru") == "часа"


@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
@patch('bot.utils.localization.get_text')
def test_pluralize_hours_russian_many(mock_get_text, mock_get_loc):
    """
    Test pluralize_hours() for Russian with 5+, 11-14 hours.

    Given: Count ending in 0, 5-9 or 11-14
    When: pluralize_hours() is called for Russian
    Then: Returns "часов" (many hours)
    """
    mock_loc = MagicMock()
    mock_loc.normalize_language_code.return_value = "ru"
    mock_get_loc.return_value = mock_loc
    mock_get_text.return_value = "часов"

    assert pluralize_hours(5, "ru") == "часов"
    assert pluralize_hours(10, "ru") == "часов"
    assert pluralize_hours(11, "ru") == "часов"
    assert pluralize_hours(12, "ru") == "часов"
    assert pluralize_hours(13, "ru") == "часов"
    assert pluralize_hours(14, "ru") == "часов"
    assert pluralize_hours(100, "ru") == "часов"


@pytest.mark.unit
@patch('bot.utils.localization.get_localization')
def test_pluralize_hours_english(mock_get_loc):
    """
    Test pluralize_hours() for English.

    Given: English language code
    When: pluralize_hours() is called
    Then: Returns "hour" for 1, "hours" for others
    """
    mock_loc = MagicMock()
    mock_loc.normalize_language_code.return_value = "en"
    mock_get_loc.return_value = mock_loc

    assert pluralize_hours(1, "en") == "hour"
    assert pluralize_hours(2, "en") == "hours"
    assert pluralize_hours(5, "en") == "hours"
    assert pluralize_hours(100, "en") == "hours"


# ============================================================================
# Test get_user_language()
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_language_success(mock_api_client):
    """
    Test get_user_language() successful retrieval.

    Given: User exists with language_code in database
    When: get_user_language() is called
    Then: Returns user's language code
    """
    mock_api_client.get_user_by_telegram_id.return_value = {
        "telegram_id": 12345,
        "language_code": "en"
    }

    result = await get_user_language(mock_api_client, 12345)
    assert result == "en"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_language_user_not_found(mock_api_client):
    """
    Test get_user_language() when user not found.

    Given: User doesn't exist in database
    When: get_user_language() is called
    Then: Returns default language 'ru'
    """
    mock_api_client.get_user_by_telegram_id.return_value = None

    result = await get_user_language(mock_api_client, 99999)
    assert result == "ru"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_language_no_language_code(mock_api_client):
    """
    Test get_user_language() when user has no language_code.

    Given: User exists but language_code is None
    When: get_user_language() is called
    Then: Returns default language 'ru'
    """
    mock_api_client.get_user_by_telegram_id.return_value = {
        "telegram_id": 12345,
        "language_code": None
    }

    result = await get_user_language(mock_api_client, 12345)
    assert result == "ru"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_user_language_api_error(mock_api_client):
    """
    Test get_user_language() when API raises error.

    Given: API client raises exception
    When: get_user_language() is called
    Then: Returns default language 'ru' without raising
    """
    mock_api_client.get_user_by_telegram_id.side_effect = Exception("API error")

    result = await get_user_language(mock_api_client, 12345)
    assert result == "ru"
