"""تست‌های ابزارهای امنیتی."""

from __future__ import annotations

import pytest

from anonchat.core.security import (
    compute_risk_score,
    generate_referral_code,
    sanitize_bio,
    sanitize_nickname,
    sanitize_text,
    validate_age,
    validate_country_code,
    validate_interests,
    validate_language_code,
)


class TestSanitizeText:
    """تست پاک‌سازی متن."""

    def test_removes_control_chars(self) -> None:
        assert sanitize_text("hello\x00world") == "helloworld"

    def test_truncates_long_text(self) -> None:
        result = sanitize_text("a" * 100, max_length=10)
        assert len(result) == 10

    def test_strips_whitespace(self) -> None:
        assert sanitize_text("  hello  ") == "hello"

    def test_empty_input(self) -> None:
        assert sanitize_text("") == ""

    def test_collapses_multiple_spaces(self) -> None:
        assert sanitize_text("a    b") == "a  b"


class TestSanitizeNickname:
    """تست پاک‌سازی نام مستعار."""

    def test_valid_english(self) -> None:
        assert sanitize_nickname("JohnDoe") == "JohnDoe"

    def test_valid_persian(self) -> None:
        assert sanitize_nickname("علی رضا") == "علی رضا"

    def test_too_short(self) -> None:
        with pytest.raises(ValueError):
            sanitize_nickname("a")

    def test_too_long(self) -> None:
        with pytest.raises(ValueError):
            sanitize_nickname("a" * 50)

    def test_special_chars_rejected(self) -> None:
        with pytest.raises(ValueError):
            sanitize_nickname("<script>")


class TestSanitizeBio:
    """تست پاک‌سازی بیو."""

    def test_valid_bio(self) -> None:
        bio = sanitize_bio("سلام، من به موسیقی علاقه دارم")
        assert bio == "سلام، من به موسیقی علاقه دارم"

    def test_rejects_dangerous_chars(self) -> None:
        with pytest.raises(ValueError):
            sanitize_bio("hello <script>alert(1)</script>")

    def test_none_passes(self) -> None:
        assert sanitize_bio("") == ""


class TestValidateAge:
    """تست اعتبارسنجی سن."""

    @pytest.mark.parametrize("age", [13, 18, 25, 60, 120])
    def test_valid_ages(self, age: int) -> None:
        assert validate_age(age) == age

    @pytest.mark.parametrize("age", [0, 5, 12, 121, 200, -5])
    def test_invalid_ages(self, age: int) -> None:
        with pytest.raises(ValueError):
            validate_age(age)


class TestValidateCountryCode:
    """تست اعتبارسنجی کد کشور."""

    def test_valid_uppercase(self) -> None:
        assert validate_country_code("IR") == "IR"

    def test_normalizes_to_uppercase(self) -> None:
        assert validate_country_code("us") == "US"

    def test_invalid_length(self) -> None:
        with pytest.raises(ValueError):
            validate_country_code("USA")

    def test_invalid_chars(self) -> None:
        with pytest.raises(ValueError):
            validate_country_code("12")


class TestValidateLanguageCode:
    """تست اعتبارسنجی کد زبان."""

    def test_valid(self) -> None:
        assert validate_language_code("fa") == "fa"

    def test_normalizes(self) -> None:
        assert validate_language_code("EN") == "en"

    def test_invalid(self) -> None:
        with pytest.raises(ValueError):
            validate_language_code("farsi")


class TestValidateInterests:
    """تست اعتبارسنجی علایق."""

    def test_valid_list(self) -> None:
        result = validate_interests(["موسیقی", "ورزش", "کتاب"])
        assert len(result) == 3

    def test_deduplication(self) -> None:
        result = validate_interests(["music", "Music", "MUSIC"])
        assert len(result) == 1

    def test_max_items(self) -> None:
        result = validate_interests([f"item{i}" for i in range(20)])
        assert len(result) == 15

    def test_empty_filtered(self) -> None:
        result = validate_interests(["", "  ", "valid"])
        assert result == ["valid"]


class TestGenerateReferralCode:
    """تست تولید کد رفرال."""

    def test_format(self) -> None:
        code = generate_referral_code(123456789)
        assert code.startswith("SAYA-")
        assert len(code) == 10  # SAYA- + 5 chars

    def test_uniqueness(self) -> None:
        codes = {generate_referral_code(i) for i in range(100)}
        # احتمال تصادم بسیار کم است
        assert len(codes) >= 95


class TestComputeRiskScore:
    """تست محاسبه امتیاز ریسک."""

    def test_clean_user(self) -> None:
        score = compute_risk_score(
            reports_count=0,
            bans_count=0,
            rate_limit_hits=0,
            account_age_days=100,
            messages_per_minute=1.0,
        )
        assert score == 0

    def test_new_account_risk(self) -> None:
        score = compute_risk_score(account_age_days=1)
        assert score == 20

    def test_reports_increase_risk(self) -> None:
        score = compute_risk_score(reports_count=3, account_age_days=100)
        assert score == 24  # 3*8

    def test_capped_at_100(self) -> None:
        score = compute_risk_score(
            reports_count=10,
            bans_count=5,
            rate_limit_hits=10,
            account_age_days=1,
            messages_per_minute=15,
        )
        assert score == 100

    def test_high_message_rate(self) -> None:
        score = compute_risk_score(
            account_age_days=100, messages_per_minute=15
        )
        assert score == 15
