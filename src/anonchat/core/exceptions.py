"""سلسله‌مراتب استثناهای دامنه‌ای پروژه.

تمام خطاهای کسب‌وکار باید از این سلسله‌مراتب ارث‌بری کنند تا در لایه
پیش‌رفتار (Middleware) به‌صورت متمرکز مدیریت شوند.
"""

from __future__ import annotations


class SayaError(Exception):
    """ریشه‌ی تمام استثناهای دامنه‌ای."""

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__


# ---------------------------------------------------------------------------
#  خطاهای کاربر
# ---------------------------------------------------------------------------
class UserError(SayaError):
    """خطای عمومی مرتبط با کاربر."""


class UserNotFoundError(UserError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"کاربر {user_id} یافت نشد.", code="USER_NOT_FOUND")
        self.user_id = user_id


class UserAlreadyRegisteredError(UserError):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"کاربر {user_id} قبلاً ثبت‌نام کرده است.", code="USER_ALREADY_REGISTERED"
        )
        self.user_id = user_id


class UserBannedError(UserError):
    """کاربر بن شده و اجازه‌ی استفاده ندارد."""

    def __init__(self, user_id: int, until: object = None, reason: str = "") -> None:
        super().__init__(
            f"کاربر {user_id} بن شده است. دلیل: {reason}",
            code="USER_BANNED",
        )
        self.user_id = user_id
        self.until = until
        self.reason = reason


class RegistrationIncompleteError(UserError):
    def __init__(self, user_id: int, missing: list[str]) -> None:
        super().__init__(
            f"ثبت‌نام ناقص است. موارد ناقص: {', '.join(missing)}",
            code="REGISTRATION_INCOMPLETE",
        )
        self.missing = missing


# ---------------------------------------------------------------------------
#  خطاهای گفتگو و Matchmaking
# ---------------------------------------------------------------------------
class ChatError(SayaError):
    """خطای مرتبط با گفتگو."""


class UserNotInChatError(ChatError):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"کاربر {user_id} در گفتگوی فعالی نیست.", code="NOT_IN_CHAT"
        )
        self.user_id = user_id


class UserAlreadyInChatError(ChatError):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"کاربر {user_id} هم‌اکنون در گفتگو است.", code="ALREADY_IN_CHAT"
        )
        self.user_id = user_id


class PartnerNotFoundError(ChatError):
    def __init__(self) -> None:
        super().__init__("مخاطب یافت نشد.", code="PARTNER_NOT_FOUND")


class NoAvailablePartnerError(ChatError):
    """هیچ کاربر مناسبی برای اتصال وجود ندارد."""

    def __init__(self) -> None:
        super().__init__(
            "در حال حاضر کاربر مناسبی برای گفتگو وجود ندارد.",
            code="NO_AVAILABLE_PARTNER",
        )


class QueueTimeoutError(ChatError):
    def __init__(self) -> None:
        super().__init__(
            "زمان انتظار در صف به پایان رسید.", code="QUEUE_TIMEOUT"
        )


# ---------------------------------------------------------------------------
#  خطاهای امنیتی
# ---------------------------------------------------------------------------
class SecurityError(SayaError):
    """خطای امنیتی — باید در Security Log ثبت شود."""


class RateLimitExceededError(SecurityError):
    def __init__(self, user_id: int, limit: int, window: int) -> None:
        super().__init__(
            f"کاربر {user_id} سقف {limit} پیام در {window} ثانیه را نقض کرد.",
            code="RATE_LIMIT_EXCEEDED",
        )
        self.user_id = user_id
        self.limit = limit
        self.window = window


class SuspiciousActivityError(SecurityError):
    def __init__(self, user_id: int, reason: str, risk_score: int) -> None:
        super().__init__(
            f"رفتار مشکوک از کاربر {user_id}: {reason} (risk={risk_score})",
            code="SUSPICIOUS_ACTIVITY",
        )
        self.user_id = user_id
        self.reason = reason
        self.risk_score = risk_score


class FloodDetectedError(SecurityError):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"تشخیص Flood از کاربر {user_id}.", code="FLOOD_DETECTED"
        )
        self.user_id = user_id


# ---------------------------------------------------------------------------
#  خطاهای پیکربندی و زیرساخت
# ---------------------------------------------------------------------------
class ConfigError(SayaError):
    """خطای پیکربندی."""


class DatabaseError(SayaError):
    """خطای پایگاه داده."""


class MaintenanceModeError(SayaError):
    """ربات در حالت نگهداری است."""

    def __init__(self) -> None:
        super().__init__(
            "ربات در حالت نگهداری است. بعداً تلاش کنید.",
            code="MAINTENANCE_MODE",
        )


class ValidationError(SayaError):
    """خطای اعتبارسنجی ورودی."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            f"ورودی نامعتبر برای فیلد «{field}»: {reason}",
            code="VALIDATION_ERROR",
        )
        self.field = field
        self.reason = reason


class AdminPermissionError(SayaError):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            f"کاربر {user_id} دسترسی مدیر ندارد.", code="ADMIN_PERMISSION_DENIED"
        )
        self.user_id = user_id
