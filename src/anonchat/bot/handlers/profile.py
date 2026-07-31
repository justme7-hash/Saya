"""هندلرهای پروفایل و ویرایش آن."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import (
    cancel_keyboard,
    gender_keyboard,
    main_menu,
    profile_edit_keyboard,
)
from anonchat.bot.states.fsm import ProfileEditStates
from anonchat.bot.utils import safe_answer, safe_edit_text
from anonchat.core.container import get_container
from anonchat.core.exceptions import UserNotFoundError
from anonchat.core.logging import get_logger
from anonchat.core.security import (
    sanitize_bio,
    sanitize_nickname,
    validate_age,
    validate_country_code,
    validate_interests,
)
from anonchat.i18n import t
from anonchat.schemas.user import ProfileUpdateDTO

router = Router()
_log = get_logger("handler.profile")


@router.message(F.text.in_(["👤 پروفایل من", "👤 My profile"]))
async def show_profile(message: Message) -> None:
    """نمایش پروفایل کاربر."""
    container = get_container()
    try:
        profile = await container.user_service.get_profile(message.from_user.id)
    except UserNotFoundError:
        await message.answer(t("error_not_registered", "fa"))
        return

    interests_str = "، ".join(profile.interests) if profile.interests else "—"
    gender_map = {
        "male": "👨 مرد",
        "female": "👩 زن",
        "other": "⚧ دیگر",
        "unspecified": "🚫 مشخص نشده",
    }
    text = (
        f"👤 {t('profile_title')}\n\n"
        f"📛 {t('profile_nickname')}: {profile.nickname or '—'}\n"
        f"⚧ {t('profile_gender')}: {gender_map.get(profile.gender, profile.gender)}\n"
        f"📅 {t('profile_age')}: {profile.age or '—'}\n"
        f"🌍 {t('profile_country')}: {profile.country or '—'}\n"
        f"🌐 {t('profile_language')}: {profile.language}\n"
        f"📝 {t('profile_bio')}: {profile.bio or '—'}\n"
        f"🎯 {t('profile_interests')}: {interests_str}\n\n"
        f"📈 {t('profile_level')}: {profile.level}\n"
        f"⭐ {t('profile_xp')}: {profile.xp}\n"
        f"👥 {t('profile_referral_code')}: <code>{profile.referral_code}</code>\n"
        f"💬 {t('profile_total_chats')}: {profile.total_chats}\n"
        f"🟢 {'آنلاین' if profile.is_online else 'آفلاین'}"
    )
    await message.answer(text, reply_markup=profile_edit_keyboard("fa"))


@router.callback_query(F.data == "edit_profile")
@router.callback_query(F.data == "profile_back")
async def edit_profile_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """منوی ویرایش پروفایل."""
    await state.clear()
    # باگ: edit_text روی پیام‌های غیرمتنی (عکس/استیکر) خطا می‌داد و همچنین
    # در صورت عدم تغییر پیام «message is not modified» می‌داد. از safe_edit_text استفاده می‌کنیم.
    await safe_edit_text(
        callback,
        t("profile_edit_what", "fa"),
        reply_markup=profile_edit_keyboard("fa"),
    )
    await safe_answer(callback)


@router.callback_query(F.data == "edit_nickname")
async def edit_nickname_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEditStates.editing_nickname)
    await callback.message.answer(  # type: ignore[attr-defined]
        "نام مستعار جدید را وارد کنید:",
        reply_markup=cancel_keyboard("fa"),
    )
    await callback.answer()


@router.message(ProfileEditStates.editing_nickname)
async def edit_nickname_process(message: Message, state: FSMContext) -> None:
    try:
        nickname = sanitize_nickname(message.text or "")
    except ValueError:
        await message.answer(t("reg_nickname_invalid", "fa"))
        return
    await _update_profile(message, state, ProfileUpdateDTO(nickname=nickname))


@router.callback_query(F.data == "edit_age")
async def edit_age_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEditStates.editing_age)
    await callback.message.answer("سن جدید را وارد کنید:", reply_markup=cancel_keyboard("fa"))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(ProfileEditStates.editing_age)
async def edit_age_process(message: Message, state: FSMContext) -> None:
    try:
        age = validate_age(int(message.text or "0"))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        await message.answer(t("reg_age_invalid", "fa"))
        return
    await _update_profile(message, state, ProfileUpdateDTO(age=age))


@router.callback_query(F.data == "edit_country")
async def edit_country_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEditStates.editing_country)
    await callback.message.answer("کد کشور جدید را وارد کنید:", reply_markup=cancel_keyboard("fa"))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(ProfileEditStates.editing_country)
async def edit_country_process(message: Message, state: FSMContext) -> None:
    try:
        country = validate_country_code(message.text or "")  # type: ignore[arg-type]
    except ValueError:
        await message.answer(t("reg_country_invalid", "fa"))
        return
    await _update_profile(message, state, ProfileUpdateDTO(country=country))


@router.callback_query(F.data == "edit_bio")
async def edit_bio_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEditStates.editing_bio)
    await callback.message.answer("بیو جدید را وارد کنید:", reply_markup=cancel_keyboard("fa"))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(ProfileEditStates.editing_bio)
async def edit_bio_process(message: Message, state: FSMContext) -> None:
    try:
        bio = sanitize_bio(message.text or "")
    except ValueError:
        await message.answer(t("error_invalid_input", "fa"))
        return
    await _update_profile(message, state, ProfileUpdateDTO(bio=bio))


@router.callback_query(F.data == "edit_interests")
async def edit_interests_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ProfileEditStates.editing_interests)
    await callback.message.answer(  # type: ignore[attr-defined]
        "علایق جدید را با کاما وارد کنید:",
        reply_markup=cancel_keyboard("fa"),
    )
    await callback.answer()


@router.message(ProfileEditStates.editing_interests)
async def edit_interests_process(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    interests = validate_interests([i.strip() for i in text.split(",")])
    await _update_profile(message, state, ProfileUpdateDTO(interests=interests))


@router.callback_query(F.data == "edit_gender")
async def edit_gender_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(  # type: ignore[attr-defined]
        t("reg_gender", "fa"),
        reply_markup=gender_keyboard("fa", prefix="editgender"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("editgender_"))
async def edit_gender_process(callback: CallbackQuery, state: FSMContext) -> None:
    gender = callback.data.split("_", 1)[1]  # type: ignore[union-attr]
    container = get_container()
    try:
        await container.user_service.update_profile(
            callback.from_user.id, ProfileUpdateDTO(gender=gender)  # type: ignore[arg-type]
        )
    except Exception as exc:
        _log.error("profile.update_failed", error=str(exc))
    await callback.message.answer("✅ جنسیت به‌روزرسانی شد.")  # type: ignore[attr-defined]
    await callback.answer()


async def _update_profile(message: Message, state: FSMContext, dto: ProfileUpdateDTO) -> None:
    """به‌روزرسانی پروفایل و بازگشت به منو."""
    container = get_container()
    try:
        await container.user_service.update_profile(message.from_user.id, dto)
    except UserNotFoundError:
        await message.answer(t("error_not_registered", "fa"))
        await state.clear()
        return
    except Exception as exc:
        _log.error("profile.update_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        await state.clear()
        return
    await state.clear()
    await message.answer("✅ پروفایل به‌روزرسانی شد.", reply_markup=main_menu("fa"))
