"""ثبت تمام هندلرها در یک مکان."""

from __future__ import annotations

from aiogram import Router

from anonchat.bot.handlers import (
    admin,
    chat,
    help,
    profile,
    referral,
    registration,
    search,
    settings,
    start,
)


def get_main_router() -> Router:
    """ساخت و بازگرداندن روتر اصلی با تمام هندلرها.

    ترتیب مهم است: هندلرهای خاص (مثل پایان گفتگو) باید قبل از
    هندلر رله‌ی پیام عمومی (fallback) قرار گیرند.
    """
    router = Router()
    # ترتیب: start و ثبت‌نام اول، سپس دستورهای خاص، سپس fallback رله
    router.include_router(start.router)
    router.include_router(registration.router)
    router.include_router(admin.router)
    router.include_router(settings.router)
    router.include_router(profile.router)
    router.include_router(referral.router)
    router.include_router(help.router)
    router.include_router(search.router)
    router.include_router(chat.router)  # chat شامل fallback رله پیام است — آخر
    return router


__all__ = [
    "admin",
    "chat",
    "get_main_router",
    "help",
    "profile",
    "referral",
    "registration",
    "search",
    "settings",
    "start",
]
