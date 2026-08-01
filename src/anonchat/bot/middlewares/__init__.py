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
    """بررسی حالت نگهداری — فقط مدیران عبور می‌کنند.

    **نکته مهم:** در aiogram 3.x، ``event`` در middleware از نوع ``Message`` یا
    ``CallbackQuery`` است، نه ``Update``. پس باید هر دو نوع را هندل کنیم.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        container = get_container()
        if container.settings.maintenance_mode:
            user = data.get("event_from_user")
            if user is None or container.settings.is_admin(user.id):
                # مدیران عبور می‌کنند
                return await handler(event, data)

            # کاربر عادی — پیام maintenance بفرست
            # event می‌تواند Message یا CallbackQuery باشد
            from aiogram.types import CallbackQuery, Message

            target_message: Message | None = None
            if isinstance(event, Message):
                target_message = event
            elif isinstance(event, CallbackQuery) and event.message:
                target_message = event.message

            if target_message is not None:
                try:
                    await target_message.answer(t("maintenance_message", "fa"))
                except Exception:
                    pass
            return None
        return await handler(event, data)


class BanCheckMiddleware(BaseMiddleware):
    """بررسی بن کاربر قبل از پردازش.

    در aiogram 3.x، ``event`` از نوع ``Message`` یا ``CallbackQuery`` است.
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
            # event می‌تواند Message یا CallbackQuery باشد
            from aiogram.types import CallbackQuery, Message

            target_message: Message | None = None
            if isinstance(event, Message):
                target_message = event
            elif isinstance(event, CallbackQuery) and event.message:
                target_message = event.message

            if target_message is not None:
                locale = "fa"
                until_text = ""
                if not is_permanent and banned_until:
                    until_text = "\n\n" + t("banned_until", locale).format(
                        until=banned_until.strftime("%Y-%m-%d %H:%M UTC")
                    )
                kind = t("banned_permanent", locale) if is_permanent else ""
                try:
                    await target_message.answer(
                        t("banned_message", locale).format(reason=ban_reason)
                        + until_text
                        + kind
                    )
                except Exception:
                    pass
            return None
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """محدودیت نرخ پیام.

    **نکته مهم:** این میدل‌ور فقط برای ``Message`` اجرا می‌شود، نه ``CallbackQuery``.
    دکمه‌های شیشه‌ای (inline) نباید Rate Limit شوند.

    در aiogram 3.x، ``event`` در middleware از نوع ``Message`` یا ``CallbackQuery``
    است، نه ``Update``.
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

        # فقط برای Message اجرا شود، نه CallbackQuery
        from aiogram.types import CallbackQuery, Message

        if isinstance(event, CallbackQuery):
            return await handler(event, data)

        if not isinstance(event, Message):
            return await handler(event, data)

        container = get_container()
        try:
            await container.security_service.check_rate_limit(user.id)
        except RateLimitExceededError:
            try:
                await event.answer(t("rate_limit_message", "fa"))
            except Exception:
                pass
            return None
        except FloodDetectedError:
            try:
                await event.answer(t("flood_message", "fa"))
            except Exception:
                pass
            return None

        return await handler(event, data)


class RegistrationCheckMiddleware(BaseMiddleware):
    """بررسی ثبت‌نام و به‌روزرسانی وضعیت آنلاین.

    این میدل‌ور:
    - کاربر را از دیتابیس می‌خواند و مقادیر لازم را به data اضافه می‌کند
    - ``is_online`` را روی ``True`` تنظیم می‌کند و ``last_seen`` را آپدیت می‌کند
      (این مهم است چون الگوریتم جستجو فقط کاربران ``is_online=True`` را پیدا می‌کند)
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
                # به‌روزرسانی وضعیت آنلاین و last_seen
                # این مهم است چون جستجو فقط کاربران is_online=True را پیدا می‌کند
                await user_repo.set_online(db_user.id, True)
                await session.commit()

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
