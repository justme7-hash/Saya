"""هندلرهای تنظیمات."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import (
    language_keyboard,
    main_menu,
    privacy_keyboard,
    settings_menu_keyboard,
)
from anonchat.core.container import get_container
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
_log = get_logger("handler.settings")


@router.message(F.text.in_(["⚙️ تنظیمات", "⚙️ Settings"]))
async def settings_menu(message: Message) -> None:
    """منوی تنظیمات."""
    await message.answer(t("settings_title", "fa"), reply_markup=settings_menu_keyboard("fa"))


@router.callback_query(F.data == "set_language")
async def set_language(callback: CallbackQuery) -> None:
    """نمایش انتخاب زبان."""
    await callback.message.edit_text(  # type: ignore[attr-defined]
        t("language_select", "fa"),
        reply_markup=language_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang_"))
async def change_language(callback: CallbackQuery) -> None:
    """تغییر زبان کاربر."""
    locale = callback.data.split("_", 1)[1]  # type: ignore[union-attr]
    container = get_container()
    from anonchat.schemas.user import ProfileUpdateDTO
    try:
        await container.user_service.update_profile(
            callback.from_user.id, ProfileUpdateDTO(language=locale)
        )
    except Exception as exc:
        _log.error("settings.language_failed", error=str(exc))
    await callback.message.answer(  # type: ignore[attr-defined]
        t("language_changed", locale),
        reply_markup=main_menu(locale),
    )
    await callback.answer()


@router.callback_query(F.data == "set_privacy")
async def privacy_menu(callback: CallbackQuery) -> None:
    """منوی تنظیمات حریم خصوصی."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
    settings = {
        "show_age": getattr(db_user, "show_age", True) if db_user else True,
        "show_country": getattr(db_user, "show_country", True) if db_user else True,
        "show_gender": getattr(db_user, "show_gender", True) if db_user else True,
        "notifications_enabled": getattr(db_user, "notifications_enabled", True) if db_user else True,
    }
    await callback.message.edit_text(  # type: ignore[attr-defined]
        t("settings_privacy_title", "fa"),
        reply_markup=privacy_keyboard("fa", settings),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("privacy_"))
async def toggle_privacy(callback: CallbackQuery) -> None:
    """تغییر یک تنظیم حریم خصوصی."""
    field = callback.data.split("_", 1)[1]  # type: ignore[union-attr]
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
    if db_user is None:
        await callback.answer()
        return

    current = getattr(db_user, field, True)
    new_value = not current
    setattr(db_user, field, new_value)
    await user_repo.update(db_user, **{field: new_value})
    await user_repo.commit()

    settings = {
        "show_age": db_user.show_age,
        "show_country": db_user.show_country,
        "show_gender": db_user.show_gender,
        "notifications_enabled": db_user.notifications_enabled,
    }
    await callback.message.edit_reply_markup(  # type: ignore[attr-defined]
        reply_markup=privacy_keyboard("fa", settings)
    )
    await callback.answer(t("settings_updated", "fa"))
