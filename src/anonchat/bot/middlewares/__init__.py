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

        # استخراج اطلاعات بن قبل از بسته‌شدن نشست
        is_banned = False
        is_permanent = False
        banned_until = None
        ban_reason = ""

        async with container.session() as session:
            ban_repo = container.ban_repo_with(session)
            ban = await ban_repo.get_active_ban_by_telegram(user.id)
            if ban is not None:
                is_banned = True
                is_permanent = ban.is_permanent
                banned_until = ban.banned_until
                ban_reason = ban.reason

        if is_banned:
            if isinstance(event, Update) and event.message:
                locale = "fa"
                until_text = ""
                if not is_permanent and banned_until:
                    until_text = "\n\n" + t("banned_until", locale).format(
                        until=banned_until.strftime("%Y-%m-%d %H:%M UTC")
                    )
                kind = t("banned_permanent", locale) if is_permanent else ""
                await event.message.answer(
                    t("banned_message", locale).format(reason=ban_reason)
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
    """بررسی ثبت‌نام برای دستورهای نیازمند.

    این میدل‌ور کاربر را از دیتابیس می‌خواند و مقادیر لازم (language, is_registered)
    را به‌صورت مقادیر اولیه (نه آبجکت SQLAlchemy) به data اضافه می‌کند تا
    از DetachedInstanceError جلوگیری شود.
    """

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
        user_language = None
        is_registered = False
        is_in_chat = False

        async with container.session() as session:
            user_repo = container.user_repo_with(session)
            db_user = await user_repo.get_by_telegram_id(user.id)
            if db_user is not None:
                # مقادیر را قبل از بسته‌شدن نشست استخراج می‌کنیم
                user_language = db_user.language
                is_registered = db_user.is_registered
                is_in_chat = db_user.is_in_chat

        data["user_language"] = user_language or container.settings.default_locale
        data["is_registered"] = is_registered
        data["is_in_chat"] = is_in_chat

        return await handler(event, data)


# لیست میدل‌ورها به ترتیب اجرا
MIDDLEWARES = [
    LoggingMiddleware,
    MaintenanceMiddleware,
    BanCheckMiddleware,
    RateLimitMiddleware,
    RegistrationCheckMiddleware,
]
