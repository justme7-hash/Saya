"""هندلرهای ثبت‌نام — جریان تکمیلی پروفایل."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import cancel_keyboard, gender_keyboard, main_menu
from anonchat.bot.states.fsm import RegistrationStates
from anonchat.core.container import get_container
from anonchat.core.logging import get_logger
from anonchat.core.security import (
    sanitize_bio,
    sanitize_nickname,
    validate_age,
    validate_country_code,
    validate_interests,
)
from anonchat.i18n import t
from anonchat.schemas.user import RegistrationDTO

router = Router()
_log = get_logger("handler.registration")


@router.callback_query(F.data == "register")
async def start_registration(callback: CallbackQuery, state: FSMContext) -> None:
    """شروع فرآیند ثبت‌نام."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    if db_user and db_user.is_registered:
        await callback.answer(t("already_registered", locale))
        return

    await state.set_state(RegistrationStates.waiting_nickname)
    await callback.message.answer(  # type: ignore[attr-defined]
        t("reg_nickname", locale),
        reply_markup=cancel_keyboard(locale),
    )
    await callback.answer()


@router.message(RegistrationStates.waiting_nickname)
async def process_nickname(message: Message, state: FSMContext) -> None:
    """پردازش نام مستعار."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(message.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    try:
        nickname = sanitize_nickname(message.text or "")
    except ValueError:
        await message.answer(t("reg_nickname_invalid", locale))
        return

    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationStates.waiting_gender)
    await message.answer(t("reg_gender", locale), reply_markup=gender_keyboard(locale))


@router.callback_query(
    RegistrationStates.waiting_gender,
    F.data.startswith("gender_"),
)
async def process_gender(callback: CallbackQuery, state: FSMContext) -> None:
    """پردازش جنسیت."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    gender = callback.data.split("_", 1)[1]  # type: ignore[union-attr]
    await state.update_data(gender=gender)
    await state.set_state(RegistrationStates.waiting_age)
    await callback.message.answer(t("reg_age", locale))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(RegistrationStates.waiting_age)
async def process_age(message: Message, state: FSMContext) -> None:
    """پردازش سن."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(message.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    try:
        age = validate_age(int(message.text or "0"))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        await message.answer(t("reg_age_invalid", locale))
        return

    await state.update_data(age=age)
    await state.set_state(RegistrationStates.waiting_country)
    await message.answer(t("reg_country", locale))


@router.message(RegistrationStates.waiting_country)
async def process_country(message: Message, state: FSMContext) -> None:
    """پردازش کشور."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(message.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    try:
        country = validate_country_code(message.text or "")  # type: ignore[arg-type]
    except ValueError:
        await message.answer(t("reg_country_invalid", locale))
        return

    await state.update_data(country=country)
    await state.set_state(RegistrationStates.waiting_bio)
    await message.answer(t("reg_bio", locale))


@router.message(RegistrationStates.waiting_bio)
async def process_bio(message: Message, state: FSMContext) -> None:
    """پردازش بیو."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(message.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    text = (message.text or "").strip()
    bio = None
    if text.lower() != "skip" and text:
        try:
            bio = sanitize_bio(text)
        except ValueError:
            await message.answer(t("error_invalid_input", locale))
            return

    await state.update_data(bio=bio)
    await state.set_state(RegistrationStates.waiting_interests)
    await message.answer(t("reg_interests", locale))


@router.message(RegistrationStates.waiting_interests)
async def process_interests(message: Message, state: FSMContext) -> None:
    """پردازش علایق و تکمیل ثبت‌نام."""
    container = get_container()
    user_repo = container.user_repo()
    db_user = await user_repo.get_by_telegram_id(message.from_user.id)
    locale = getattr(db_user, "language", None) or "fa"

    text = (message.text or "").strip()
    interests: list[str] = []
    if text.lower() != "skip" and text:
        try:
            interests = validate_interests([i.strip() for i in text.split(",")])
        except ValueError:
            await message.answer(t("error_invalid_input", locale))
            return

    data = await state.get_data()
    try:
        dto = RegistrationDTO(
            nickname=data["nickname"],
            gender=data.get("gender", "unspecified"),
            age=data["age"],
            country=data["country"],
            language=locale,
            bio=data.get("bio"),
            interests=interests,
        )
    except Exception as exc:
        _log.error("registration.dto_failed", error=str(exc))
        await message.answer(t("error_generic", locale))
        await state.clear()
        return

    try:
        await container.user_service.complete_registration(message.from_user.id, dto)
    except Exception as exc:
        _log.error("registration.failed", user_id=message.from_user.id, error=str(exc))
        await message.answer(t("error_generic", locale))
        await state.clear()
        return

    # بررسی دستاوردها
    try:
        new_achievements = await container.achievement_service.check_and_award(
            message.from_user.id
        )
    except Exception:
        new_achievements = []

    await state.clear()
    await message.answer(
        t("reg_complete", locale),
        reply_markup=main_menu(locale),
    )

    # نمایش دستاوردهای جدید
    for ach in new_achievements:
        await message.answer(
            t("achievement_earned", locale).format(
                icon=ach["icon"],
                name=ach["name"],
                description=ach["description"],
                xp=ach["xp_reward"],
            )
        )
