"""تنظیم بات و دیسپچر."""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import ErrorEvent, TelegramObject

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


async def _error_handler(event: ErrorEvent) -> None:
    """هندلر خطای سراسری — تمام خطاهای handler را log می‌کند.

    بدون این، aiogram خطاها را می‌بلعد و هیچ اثری در لاگ نمی‌ماند.
    traceback کامل را به‌صورت خطوط جداگانه log می‌کند تا در Railway
    قابل خواندن باشد.
    """
    import traceback

    update = event.update
    exception = event.exception

    # لاگ خطای اصلی
    _log.error(
        "bot.handler_error",
        update_type=type(update).__name__ if update else "unknown",
        update_id=getattr(update, "update_id", None),
        error_type=type(exception).__name__,
        error=str(exception),
    )

    # traceback کامل را خط به خط log کن
    tb_lines = traceback.format_exception(
        type(exception), exception, exception.__traceback__
    )
    for line in "".join(tb_lines).splitlines():
        _log.error("bot.traceback", line=line)


def create_dispatcher() -> Dispatcher:
    """ساخت دیسپچر با میدل‌ورها و روترها."""
    dp = Dispatcher()

    # ثبت میدل‌ورها
    for middleware_cls in MIDDLEWARES:
        dp.message.outer_middleware(middleware_cls())
        dp.callback_query.outer_middleware(middleware_cls())

    # ثبت روتر اصلی
    dp.include_router(get_main_router())

    # ثبت هندلر خطای سراسری با register (روش صحیح در aiogram 3.x)
    dp.errors.register(_error_handler)

    _log.info("bot.dispatcher_created")
    return dp
