"""
Internationalization (i18n) utilities using gettext
"""

import gettext
import locale
import os
from pathlib import Path
from typing import Optional


class I18n:
    """Internationalization manager"""

    def __init__(self, language: Optional[str] = None):
        """
        Initialize i18n manager.

        Args:
            language: Language code (e.g., 'en', 'de') or None for system default
        """
        self.locale_dir = self._get_locale_dir()
        self.language = language or self._get_system_language()
        self.translation = None
        self._load_translation()

    def _get_locale_dir(self) -> Path:
        """Get path to locale directory"""
        # Get project root directory
        if hasattr(__import__('sys'), 'frozen'):
            # Running as compiled executable
            import sys
            root = Path(sys.executable).parent
        else:
            # Running as script
            root = Path(__file__).parent.parent.parent

        locale_dir = root / 'locale'

        # Create locale directory if it doesn't exist
        locale_dir.mkdir(exist_ok=True)

        return locale_dir

    def _get_system_language(self) -> str:
        """Get system language code"""
        try:
            # Try to get system locale
            sys_locale, _ = locale.getdefaultlocale()
            if sys_locale:
                # Extract language code (first two characters)
                return sys_locale[:2].lower()
        except Exception:
            pass

        return 'en'  # Default to English

    def _load_translation(self):
        """Load translation for current language"""
        try:
            self.translation = gettext.translation(
                'multideck',
                localedir=str(self.locale_dir),
                languages=[self.language],
                fallback=True
            )
        except Exception as e:
            print(f"Warning: Could not load translation for '{self.language}': {e}")
            # Use NullTranslations as fallback
            self.translation = gettext.NullTranslations()

    def set_language(self, language: str):
        """
        Change current language.

        Args:
            language: Language code (e.g., 'en', 'de')
        """
        self.language = language
        self._load_translation()

    def gettext(self, message: str) -> str:
        """
        Translate a message.

        Args:
            message: Message to translate

        Returns:
            Translated message
        """
        if self.translation:
            return self.translation.gettext(message)
        return message

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """
        Translate a message with plural forms.

        Args:
            singular: Singular form
            plural: Plural form
            n: Count

        Returns:
            Translated message
        """
        if self.translation:
            return self.translation.ngettext(singular, plural, n)
        return singular if n == 1 else plural

    def get_available_languages(self) -> list:
        """
        Get list of available languages.

        Returns:
            List of language codes
        """
        languages = ['en']  # English is always available (fallback)

        if self.locale_dir.exists():
            for item in self.locale_dir.iterdir():
                if item.is_dir() and (item / 'LC_MESSAGES').exists():
                    languages.append(item.name)

        return sorted(set(languages))


# Global i18n instance
_i18n_instance: Optional[I18n] = None


def initialize_i18n(language: Optional[str] = None) -> I18n:
    """
    Initialize global i18n instance.

    Args:
        language: Language code or None for system default

    Returns:
        I18n instance
    """
    global _i18n_instance
    _i18n_instance = I18n(language)
    return _i18n_instance


def get_i18n() -> I18n:
    """
    Get global i18n instance.

    Returns:
        I18n instance
    """
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def _(message: str) -> str:
    """
    Convenience function for translation.

    Args:
        message: Message to translate

    Returns:
        Translated message
    """
    return get_i18n().gettext(message)


# Language names for UI
LANGUAGE_NAMES = {
    'en': 'English',
    'de': 'Deutsch',
}
