"""سیستم بین‌المللی‌سازی (i18n) — پشتیبانی از چند زبان.

زبان‌های پشتیبانی‌شده:
- fa (فارسی) — زبان پیش‌فرض
- en (انگلیسی)

تمام رشته‌های نمایشی کاربر از این لایه عبور می‌کنند تا افزودن
زبان جدید بدون تغییر هندلرها ممکن باشد.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from anonchat.core.logging import get_logger

_LOCALES_DIR = Path(__file__).parent / "locales"
_SUPPORTED_LOCALES = ("fa", "en")
_DEFAULT_LOCALE = "fa"

_log = get_logger("i18n")


class I18n:
    """مدیریت ترجمه‌ها."""

    def __init__(self) -> None:
        self._translations: dict[str, dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        """بارگذاری فایل‌های ترجمه."""
        for locale in _SUPPORTED_LOCALES:
            path = _LOCALES_DIR / f"{locale}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    # فلت کردن کلیدهای نقطه‌دار
                    self._translations[locale] = self._flatten(data)
                    _log.debug("i18n.loaded", locale=locale, keys=len(self._translations[locale]))
                except Exception as exc:
                    _log.error("i18n.load_failed", locale=locale, error=str(exc))
                    self._translations[locale] = {}
            else:
                _log.warning("i18n.file_missing", locale=locale, path=str(path))
                self._translations[locale] = {}

    @staticmethod
    def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
        """فلت کردن دیکشنری تو در تو به کلیدهای نقطه‌دار."""
        result: dict[str, str] = {}
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(I18n._flatten(value, full_key))
            else:
                result[full_key] = str(value)
        return result

    def get(
        self,
        key: str,
        locale: str = _DEFAULT_LOCALE,
        **kwargs: Any,
    ) -> str:
        """دریافت رشته‌ی ترجمه‌شده با جایگذاری پارامترها.

        اگر کلید در زبان مورد نظر یافت نشود، به زبان پیش‌فرض برمی‌گردد.
        اگر در آن هم نبود، خود کلید برگردانده می‌شود.
        """
        if locale not in _SUPPORTED_LOCALES:
            locale = _DEFAULT_LOCALE

        text = self._translations.get(locale, {}).get(key)
        if text is None:
            text = self._translations.get(_DEFAULT_LOCALE, {}).get(key)
        if text is None:
            _log.warning("i18n.key_missing", key=key, locale=locale)
            return key

        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    @property
    def supported_locales(self) -> tuple[str, ...]:
        return _SUPPORTED_LOCALES

    @property
    def default_locale(self) -> str:
        return _DEFAULT_LOCALE


# نمونه‌ی singleton
_i18n: I18n | None = None


def get_i18n() -> I18n:
    """دسترسی به نمونه‌ی singleton i18n."""
    global _i18n
    if _i18n is None:
        _i18n = I18n()
    return _i18n


def t(key: str, locale: str = _DEFAULT_LOCALE, **kwargs: Any) -> str:
    """میان‌بر برای ترجمه."""
    return get_i18n().get(key, locale, **kwargs)
