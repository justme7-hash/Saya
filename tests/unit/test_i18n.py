"""تست i18n."""

from __future__ import annotations

from anonchat.i18n import get_i18n, t


class TestI18n:
    """تست سیستم ترجمه."""

    def test_loads_farsi(self) -> None:
        i18n = get_i18n()
        assert "fa" in i18n.supported_locales
        text = i18n.get("welcome", "fa")
        assert "سایه" in text or "خوش آمدید" in text

    def test_loads_english(self) -> None:
        i18n = get_i18n()
        text = i18n.get("welcome", "en")
        assert "Welcome" in text or "Saya" in text

    def test_falls_back_to_default(self) -> None:
        text = t("welcome", "fr")  # فرانسوی پشتیبانی نمی‌شود
        # باید به فارسی برگردد
        assert text != "welcome"

    def test_missing_key_returns_key(self) -> None:
        text = t("nonexistent.key.xyz", "fa")
        assert text == "nonexistent.key.xyz"

    def test_parameter_substitution(self) -> None:
        text = t("welcome_back", "fa", nickname="علی")
        assert "علی" in text

    def test_t_shortcut(self) -> None:
        text = t("help_title", "fa")
        assert "راهنما" in text
