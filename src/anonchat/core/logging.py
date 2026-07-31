"""ساختار لاگ‌گذاری متمرکز بر پایه ``structlog``.

دو فرمت پشتیبانی می‌شود:
- ``json``: برای محیط پروداکشن (قابل پردازش توسط ELK / Loki).
- ``console``: برای توسعه با رنگ و خوانایی بالا توسط ``rich``.

همچنین چند فیلتر سفارشی برای حساس‌سازی توکن‌ها اضافه شده است.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import structlog
from rich.console import Console
from rich.logging import RichHandler

from anonchat.core.config import get_settings

# الگوهای حساسی که باید در لاگ ماسک شوند
_TOKEN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "***BOT_TOKEN***"),
    (re.compile(r"postgresql(?:\+\w+)?://[^@\s]+@"), "postgresql://***:***@"),
    (re.compile(r"sqlite:///(?:[^?\s]+/)?(\w+\.db)"), r"sqlite:///***\1"),
]


def _redact_sensitive(value: Any) -> Any:
    """ماسک کردن مقادیر حساس در رشته‌ها."""
    if isinstance(value, str):
        redacted = value
        for pattern, replacement in _TOKEN_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted
    if isinstance(value, dict):
        return {k: _redact_sensitive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_sensitive(v) for v in value)
    return value


def _redact_processor(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor برای ماسک کردن داده‌ی حساس در رخدادهای لاگ."""
    return {k: _redact_sensitive(v) for k, v in event_dict.items()}  # type: ignore[return-value]


def configure_logging() -> structlog.BoundLogger:
    """تنظیم و پیکربندی سیستم لاگ.

    Returns:
        لاگر اصلی پروژه.
    """
    cfg = get_settings()

    # سطح لاگ stdlib
    logging.basicConfig(
        level=cfg.log_level,
        format="%(message)s" if cfg.log_format == "console" else "%(message)s",
        handlers=(
            [RichHandler(console=Console(stderr=True), rich_tracebacks=True, show_path=False)]
            if cfg.log_format == "console"
            else [logging.StreamHandler()]
        ),
    )

    # سایلنت کردن کتابخانه‌های پرفشار
    for noisy in ("aiogram.event", "aiogram.middleware", "httpx", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _redact_processor,
    ]

    if cfg.log_format == "json":
        renderer: Any = structlog.processors.JSONRenderer(ensure_ascii=False)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.MODULE,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, cfg.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger("saya")


def get_logger(name: str = "saya") -> structlog.BoundLogger:
    """دریافت لاگر باند‌شده با نام ماژول."""
    return structlog.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    """اتصال مقادیر به context لاگ (مثل user_id) برای ردیابی درخواست."""
    structlog.contextvars.clear_contextvars()
    for key, value in kwargs.items():
        if value is not None:
            structlog.contextvars.bind_contextvars(**{key: value})
