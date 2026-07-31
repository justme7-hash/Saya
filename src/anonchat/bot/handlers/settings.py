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
from anonchat.bot.utils import safe_answer, safe_edit_reply_markup, safe_edit_text
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
    # باگ: edit_text روی پیام غیرمتنی خطا می‌داد؛ از safe_edit_text استفاده می‌کنیم.
    await safe_edit_text(
        callback,
        t("language_select", "fa"),
        reply_markup=language_keyboard(),
    )
    await safe_answer(callback)


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
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        # مقادیر را داخل نشست استخراج می‌کنیم تا از DetachedInstanceError جلوگیری شود.
        settings = {
            "show_age": getattr(db_user, "show_age", True) if db_user else True,
            "show_country": getattr(db_user, "show_country", True) if db_user else True,
            "show_gender": getattr(db_user, "show_gender", True) if db_user else True,
            "notifications_enabled": getattr(db_user, "notifications_enabled", True) if db_user else True,
        }
    # باگ: edit_text روی پیام غیرمتنی خطا می‌داد؛ از safe_edit_text استفاده می‌کنیم.
    await safe_edit_text(
        callback,
        t("settings_privacy_title", "fa"),
        reply_markup=privacy_keyboard("fa", settings),
    )
    await safe_answer(callback)


@router.callback_query(F.data.startswith("privacy_"))
async def toggle_privacy(callback: CallbackQuery) -> None:
    """تغییر یک تنظیم حریم خصوصی."""
    field = callback.data.split("_", 1)[1]  # type: ignore[union-attr]
    container = get_container()
    # باگ DetachedInstanceError: تمام مقادیر مورد نیاز را داخل async with و قبل از
    # commit استخراج می‌کنیم تا پس از بسته‌شدن نشست به آبجکت SQLAlchemy دسترسی
    # نداشته باشیم.
    settings: dict[str, bool] = {}
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        if db_user is None:
            await safe_answer(callback)
            return

        current = getattr(db_user, field, True)
        new_value = not current
        await user_repo.update(db_user, **{field: new_value})
        # مقادیر را قبل از commit و داخل نشست استخراج می‌کنیم
        settings = {
            "show_age": db_user.show_age,
            "show_country": db_user.show_country,
            "show_gender": db_user.show_gender,
            "notifications_enabled": db_user.notifications_enabled,
        }
        await session.commit()
    # باگ: edit_reply_markup روی پیام غیرمتنی خطا می‌داد؛ از safe_edit_reply_markup استفاده می‌کنیم.
    await safe_edit_reply_markup(
        callback,
        reply_markup=privacy_keyboard("fa", settings),
    )
    await safe_answer(callback, t("settings_updated", "fa"))
