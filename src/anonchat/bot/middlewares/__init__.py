"""میدل‌ورهای ربات.

ترتیب اجرا:
1. LoggingMiddleware — لاگ همه‌ی آپدیت‌ها
2. MaintenanceMiddleware — بررسی حالت نگهداری
3. BanCheckMiddleware — بررسی بن کاربر
4. RateLimitMiddleware — محدودیت نرخ
5. DatabaseMiddleware — تزریق نشست دیتابیس
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from anonchat.core.container import get_container
from anonchat.core.exceptions import (
    FloodDetectedError,
    MaintenanceModeError,
    RateLimitExceededError,
    UserBannedError,
)
from anonchat.core.logging import bind_request_context, get_logger
from anonchat.i18n import t

_log = get_logger("middleware")


class LoggingMiddleware(BaseMiddleware):
    """لاگ‌گذاری تمام آپدیت‌ها با شناسه کاربر."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is not None:
            bind_request_context(user_id=user.id, username=user.username)
            _log.info(
                "update.received",
                update_type=type(event).__name__,
                user_id=user.id,
            )
        return await handler(event, data)


class MaintenanceMiddleware(BaseMiddleware):
    """بررسی حالت نگهداری — فقط مدیران عبور می‌کنند."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        container = get_container()
        # بررسی فلگ تنظیمات محیطی
        if container.settings.maintenance_mode:
            user = data.get("event_from_user")
            if user is None or not container.settings.is_admin(user.id):
                if isinstance(event, Update) and event.message:
                    locale = "fa"
                    await event.message.answer(t("maintenance_message", locale))
                return None
        return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    """بررسی بن کاربر قبل از پردازش."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        container = get_container()
        # مدیران از بررسی بن معافند
        if container.settings.is_admin(user.id):
            return await handler(event, data)

        ban_repo = container.ban_repo()
        ban = await ban_repo.get_active_ban_by_telegram(user.id)
        if ban is not None:
            if isinstance(event, Update) and event.message:
                locale = "fa"
                until_text = ""
                if not ban.is_permanent and ban.banned_until:
                    until_text = "\n\n" + t("banned_until", locale).format(
                        until=ban.banned_until.strftime("%Y-%m-%d %H:%M UTC")
                    )
                kind = t("banned_permanent", locale) if ban.is_permanent else ""
                await event.message.answer(
                    t("banned_message", locale).format(reason=ban.reason)
                    + until_text
                    + kind
                )
            return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """محدودیت نرخ پیام."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        container = get_container()
        try:
            await container.security_service.check_rate_limit(user.id)
        except RateLimitExceededError:
            if isinstance(event, Update) and event.message:
                await event.message.answer(t("rate_limit_message", "fa"))
            return None
        except FloodDetectedError:
            if isinstance(event, Update) and event.message:
                await event.message.answer(t("flood_message", "fa"))
            return None

        return await handler(event, data)


class RegistrationCheckMiddleware(BaseMiddleware):
    """بررسی ثبت‌نام برای دستورهای نیازمند."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        container = get_container()
        user_repo = container.user_repo()
        db_user = await user_repo.get_by_telegram_id(user.id)

        # تزریق کاربر دیتابیس به data برای استفاده در هندلر
        if db_user is not None:
            data["db_user"] = db_user
            data["locale"] = db_user.language or container.settings.default_locale

        return await handler(event, data)


# لیست میدل‌ورها به ترتیب اجرا
MIDDLEWARES = [
    LoggingMiddleware,
    MaintenanceMiddleware,
    BanCheckMiddleware,
    RateLimitMiddleware,
    RegistrationCheckMiddleware,
]
