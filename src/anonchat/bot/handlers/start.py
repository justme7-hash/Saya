"""هندلرهای شروع و دستور پایه."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from anonchat.bot.keyboards import main_menu, start_keyboard
from anonchat.core.container import get_container
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
_log = get_logger("handler.start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """دستور /start — ورود به ربات با پشتیبانی از رفرال."""
    container = get_container()
    user = message.from_user
    if user is None:
        return

    # استخراج کد رفرال از پارامتر (در صورت وجود)
    referral_code = None
    if message.text and len(message.text.split()) > 1:
        referral_code = message.text.split(maxsplit=1)[1].strip()

    try:
        db_user, created = await container.user_service.get_or_create(
            user.id, language=container.settings.default_locale, referral_code=referral_code
        )
    except Exception as exc:
        _log.error("start.user_create_failed", user_id=user.id, error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    locale = getattr(db_user, "language", None) or container.settings.default_locale

    if db_user.is_registered:
        nickname = getattr(db_user, "nickname", None) or "دوست"
        await message.answer(
            t("welcome_back", locale).format(nickname=nickname),
            reply_markup=main_menu(locale),
        )
    else:
        await message.answer(
            t("welcome", locale),
            reply_markup=start_keyboard(locale),
        )


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """نمایش منوی اصلی."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"
        is_registered = bool(db_user and db_user.is_registered)
        nickname = getattr(db_user, "nickname", None) if db_user else None
    if is_registered:
        await message.answer(t("welcome_back", locale).format(nickname=nickname or "دوست"),
                            reply_markup=main_menu(locale))
    else:
        await message.answer(t("welcome", locale), reply_markup=start_keyboard(locale))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state) -> None:
    """لغو هر عملیات در حال انجام."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"
    await state.clear()
    await message.answer(t("cancel_text", locale), reply_markup=main_menu(locale))
