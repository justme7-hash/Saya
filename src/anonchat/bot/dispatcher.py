"""تنظیم بات و دیسپچر."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from anonchat.bot.handlers import get_main_router
from anonchat.bot.middlewares import MIDDLEWARES
from anonchat.core.config import get_settings
from anonchat.core.logging import get_logger

_log = get_logger("bot")


def create_bot() -> Bot:
    """ساخت نمونه‌ی بات."""
    settings = get_settings()
    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    return bot


def create_dispatcher() -> Dispatcher:
    """ساخت دیسپچر با میدل‌ورها و روترها."""
    dp = Dispatcher()

    # ثبت میدل‌ورها
    for middleware_cls in MIDDLEWARES:
        dp.message.outer_middleware(middleware_cls())
        dp.callback_query.outer_middleware(middleware_cls())

    # ثبت روتر اصلی
    dp.include_router(get_main_router())

    _log.info("bot.dispatcher_created")
    return dp
