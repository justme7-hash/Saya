"""بسته‌ی Core — قلب معماری پروژه سایه."""

from anonchat.core.config import Settings, get_settings, settings
from anonchat.core.exceptions import (
    AdminPermissionError,
    ChatError,
    MaintenanceModeError,
    RateLimitExceededError,
    SayaError,
    SecurityError,
    UserBannedError,
    UserError,
    UserNotFoundError,
    ValidationError,
)
from anonchat.core.logging import bind_request_context, configure_logging, get_logger
from anonchat.core.security import (
    compute_risk_score,
    generate_referral_code,
    sanitize_bio,
    sanitize_nickname,
    sanitize_text,
    utcnow,
    validate_age,
    validate_country_code,
    validate_interests,
    validate_language_code,
)

__all__ = [
    # config
    "Settings",
    "get_settings",
    "settings",
    # logging
    "configure_logging",
    "get_logger",
    "bind_request_context",
    # exceptions
    "SayaError",
    "UserError",
    "UserNotFoundError",
    "UserBannedError",
    "ChatError",
    "SecurityError",
    "RateLimitExceededError",
    "MaintenanceModeError",
    "ValidationError",
    "AdminPermissionError",
    # security
    "sanitize_text",
    "sanitize_nickname",
    "sanitize_bio",
    "validate_age",
    "validate_country_code",
    "validate_language_code",
    "validate_interests",
    "generate_referral_code",
    "compute_risk_score",
    "utcnow",
]
