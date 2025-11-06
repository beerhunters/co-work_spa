"""
Система локализации для телеграм бота
"""
import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class Localization:
    """Класс для управления локализацией бота"""
    
    def __init__(self):
        self.translations: Dict[str, Dict[str, Any]] = {}
        self.default_language = "ru"
        self.supported_languages = ["ru", "en"]
        self.load_translations()
    
    def load_translations(self):
        """Загружает переводы из JSON файлов"""
        locales_dir = Path(__file__).parent.parent / "locales"
        
        for lang in self.supported_languages:
            locale_file = locales_dir / f"{lang}.json"
            if locale_file.exists():
                try:
                    with open(locale_file, "r", encoding="utf-8") as f:
                        self.translations[lang] = json.load(f)
                except Exception as e:
                    print(f"Ошибка загрузки локализации для {lang}: {e}")
    
    def get_text(self, language_code: str, key_path: str, **kwargs) -> str:
        """
        Получает переведенный текст по ключу
        
        Args:
            language_code: Код языка (например, 'ru', 'en')
            key_path: Путь к ключу через точку (например, 'welcome.title')
            **kwargs: Параметры для форматирования строки
            
        Returns:
            Переведенный текст
        """
        # Определяем язык (если не поддерживается - используем по умолчанию)
        lang = self.normalize_language_code(language_code)
        
        # Получаем перевод
        translation = self._get_nested_translation(lang, key_path)
        
        # Если перевод не найден для указанного языка, пробуем язык по умолчанию
        if translation is None and lang != self.default_language:
            translation = self._get_nested_translation(self.default_language, key_path)
        
        # Если и так не найден, возвращаем сам ключ
        if translation is None:
            return f"[{key_path}]"
        
        # Форматируем строку с параметрами
        try:
            return translation.format(**kwargs)
        except (KeyError, ValueError):
            return translation
    
    def normalize_language_code(self, language_code: Optional[str]) -> str:
        """
        Нормализует код языка к поддерживаемому
        
        Args:
            language_code: Код языка от пользователя
            
        Returns:
            Нормализованный код языка
        """
        if not language_code:
            return self.default_language
            
        # Берем первые 2 символа и приводим к нижнему регистру
        lang = language_code.lower()[:2]
        
        # Если язык поддерживается - возвращаем его
        if lang in self.supported_languages:
            return lang
            
        return self.default_language
    
    def _get_nested_translation(self, lang: str, key_path: str) -> Optional[str]:
        """
        Получает перевод по вложенному пути ключа
        
        Args:
            lang: Код языка
            key_path: Путь к ключу через точку
            
        Returns:
            Перевод или None если не найден
        """
        if lang not in self.translations:
            return None
            
        keys = key_path.split(".")
        current = self.translations[lang]
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def get_button_text(self, language_code: str, button_key: str) -> str:
        """
        Получает текст для кнопки
        
        Args:
            language_code: Код языка
            button_key: Ключ кнопки
            
        Returns:
            Текст кнопки
        """
        return self.get_text(language_code, f"buttons.{button_key}")


# Глобальный экземпляр локализации
_localization = None


def get_localization() -> Localization:
    """Получает глобальный экземпляр локализации"""
    global _localization
    if _localization is None:
        _localization = Localization()
    return _localization


def get_text(language_code: str, key_path: str, **kwargs) -> str:
    """
    Быстрый доступ к получению переведенного текста
    
    Args:
        language_code: Код языка
        key_path: Путь к ключу
        **kwargs: Параметры для форматирования
        
    Returns:
        Переведенный текст
    """
    return get_localization().get_text(language_code, key_path, **kwargs)


def get_button_text(language_code: str, button_key: str) -> str:
    """
    Быстрый доступ к получению текста кнопки
    
    Args:
        language_code: Код языка
        button_key: Ключ кнопки
        
    Returns:
        Текст кнопки
    """
    return get_localization().get_button_text(language_code, button_key)


def pluralize_hours(count: int, language_code: str = "ru") -> str:
    """
    Возвращает правильную форму слова "час" в зависимости от числа

    Args:
        count: Количество часов
        language_code: Код языка

    Returns:
        Правильная форма слова "час/часа/часов" или "hour/hours"
    """
    lang = get_localization().normalize_language_code(language_code)

    if lang == "ru":
        # Правила русского языка
        if count % 10 == 1 and count % 100 != 11:
            return get_text(lang, "booking.hours_one")
        elif count % 10 in [2, 3, 4] and count % 100 not in [12, 13, 14]:
            return get_text(lang, "booking.hours_few")
        else:
            return get_text(lang, "booking.hours_many")
    else:
        # Для английского и других языков
        return "hour" if count == 1 else "hours"


async def get_user_language(api_client, telegram_id: int) -> str:
    """
    Получает язык пользователя из базы данных

    Args:
        api_client: Клиент API
        telegram_id: Telegram ID пользователя

    Returns:
        Код языка пользователя
    """
    try:
        user = await api_client.get_user_by_telegram_id(telegram_id)
        if user and user.get("language_code"):
            return user.get("language_code", "ru")
    except Exception:
        pass
    return "ru"