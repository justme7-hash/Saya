"""ابزارهای امنیتی مشترک.

شامل:
- هش امن برای شناسه‌های داخلی (نه رمز عبور — ربات بدون احراز هویت پسورد است).
- پاک‌سازی ورودی کاربر برای جلوگیری از تزریق و کاراکترهای مخرب.
- اعتبارسنجی نام کاربری، سن، کد کشور.
- تولید شناسه‌ی رفرال.
- امضای امن برای توکن‌های یک‌بار مصرف.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import string
from datetime import UTC, datetime
from typing import Literal

from anonchat.core.config import get_settings

# ---------------------------------------------------------------------------
#  الگوهای اعتبارسنجی
# ---------------------------------------------------------------------------
_NICKNAME_RE = re.compile(r"^[\w\u0600-\u06FF\u0750-\u077F][\w\u0600-\u06FF\u0750-\u077F\s_.-]{1,28}$")
_BIO_RE = re.compile(r"^[^<>&;`]{0,300}$", re.DOTALL)
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}$")

# کاراکترهای خطرناک که در ورودی کاربر حذف می‌شوند
_DANGEROUS_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

Gender = Literal["male", "female", "other", "unspecified"]
Locale = Literal["fa", "en"]

# ---------------------------------------------------------------------------
#  پاک‌سازی ورودی
# ---------------------------------------------------------------------------

def sanitize_text(text: str, max_length: int | None = None) -> str:
    """پاک‌سازی متن کاربر از کاراکترهای کنترلی و مخرب.

    Args:
        text: متن خام ورودی.
        max_length: حداکثر طول مجاز (اگر None از تنظیمات استفاده می‌شود).

    Returns:
        متن پاک‌شده.
    """
    if not text:
        return ""
    limit = max_length or get_settings().max_text_length
    cleaned = _DANGEROUS_CHARS.sub("", text).strip()
    # نرمال‌سازی فضاهای خالی اضافی
    cleaned = re.sub(r"\s{3,}", "  ", cleaned)
    return cleaned[:limit]


def sanitize_nickname(nickname: str) -> str:
    """اعتبارسنجی و پاک‌سازی نام مستعار."""
    cleaned = sanitize_text(nickname, max_length=30)
    if not _NICKNAME_RE.match(cleaned):
        raise ValueError(
            "نام مستعار باید ۲ تا ۳۰ کاراکتر باشد و فقط شامل حروف، اعداد و فاصله باشد."
        )
    return cleaned


def sanitize_bio(bio: str) -> str:
    """اعتبارسنجی و پاک‌سازی بیوگرافی."""
    cleaned = sanitize_text(bio, max_length=300)
    if cleaned and not _BIO_RE.match(cleaned):
        raise ValueError("بیو حاوی کاراکترهای غیرمجاز است.")
    return cleaned


def validate_age(age: int) -> int:
    """اعتبارسنجی سن کاربر (۱۳ تا ۱۲۰ سال)."""
    if not 13 <= age <= 120:
        raise ValueError("سن باید بین ۱۳ تا ۱۲۰ سال باشد.")
    return age


def validate_country_code(code: str) -> str:
    """اعتبارسنجی کد کشور بر اساس استاندارد ISO 3166-1 alpha-2."""
    upper = code.upper().strip()
    if not _COUNTRY_RE.match(upper):
        raise ValueError("کد کشور باید دو حرف لاتین باشد (مثل IR, US).")
    return upper


def validate_language_code(code: str) -> str:
    """اعتبارسنجی کد زبان (ISO 639-1)."""
    lower = code.lower().strip()
    if not _LANGUAGE_RE.match(lower):
        raise ValueError("کد زبان باید ۲ تا ۳ حرف لاتین باشد (مثل fa, en).")
    return lower


def validate_interests(interests: list[str]) -> list[str]:
    """اعتبارسنجی لیست علایق."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in interests:
        text = sanitize_text(item, max_length=40)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            cleaned.append(text)
    if len(cleaned) > 15:
        cleaned = cleaned[:15]
    return cleaned


# ---------------------------------------------------------------------------
#  هش و شناسه
# ---------------------------------------------------------------------------

def hash_telegram_id(user_id: int) -> str:
    """تولید هش یک‌طرفه از شناسه تلگرام برای لاگ‌های امنیتی."""
    token = get_settings().token.encode()
    return hmac.new(token, str(user_id).encode(), hashlib.sha256).hexdigest()[:16]


def generate_referral_code(user_id: int) -> str:
    """تولید کد رفرال یکتا و کوتاه برای کاربر."""
    alphabet = string.ascii_uppercase + string.digits
    # ترکیب user_id با entropy تصادفی برای غیرقابل حدس بودن
    seed = f"{user_id}:{secrets.token_hex(4)}"
    digest = hashlib.blake2b(seed.encode(), digest_size=5).digest()
    code = "".join(alphabet[b % len(alphabet)] for b in digest)
    return f"SAYA-{code}"


def generate_token_signature(payload: str) -> str:
    """امضای HMAC برای توکن‌های یک‌بار مصرف (مثل بازیابی)."""
    token = get_settings().token.encode()
    return hmac.new(token, payload.encode(), hashlib.sha256).hexdigest()


def verify_token_signature(payload: str, signature: str) -> bool:
    """بررسی اعتبار امضا با مقایسه‌ی ثابت-زمان."""
    expected = generate_token_signature(payload)
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
#  امتیاز ریسک
# ---------------------------------------------------------------------------

def compute_risk_score(
    *,
    reports_count: int = 0,
    bans_count: int = 0,
    rate_limit_hits: int = 0,
    account_age_days: int = 0,
    messages_per_minute: float = 0.0,
) -> int:
    """محاسبه‌ی امتیاز ریسک کاربر (۰ تا ۱۰۰).

    الگوریتم وزن‌دهی:
    - گزارش‌ها: هر گزارش ۸ امتیاز
    - بن‌های قبلی: هر بن ۱۵ امتیاز
    - نقض Rate Limit: هر بار ۵ امتیاز
    - حساب جدید (< ۳ روز): ۲۰ امتیاز
    - سرعت پیام بالا (> ۱۰ پیام/دقیقه): ۱۵ امتیاز

    Returns:
        عدد صحیح بین ۰ تا ۱۰۰.
    """
    score = (
        min(reports_count * 8, 40)
        + min(bans_count * 15, 45)
        + min(rate_limit_hits * 5, 20)
    )
    if account_age_days < 3:
        score += 20
    if messages_per_minute > 10:
        score += 15
    return min(score, 100)


# ---------------------------------------------------------------------------
#  کمکی
# ---------------------------------------------------------------------------

def utcnow() -> datetime:
    """زمان فعلی UTC با آگاهی از تایم‌زون."""
    return datetime.now(UTC)


def mask_token(token: str) -> str:
    """ماسک کردن توکن برای نمایش امن در لاگ‌ها."""
    if not token or len(token) < 12:
        return "***"
    return f"{token[:6]}...{token[-4:]}"
