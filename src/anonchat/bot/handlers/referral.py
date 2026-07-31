"""هندلرهای رفرال، پاداش روزانه و دستاوردها."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from anonchat.bot.keyboards import main_menu
from anonchat.bot.utils import reset_user_state
from anonchat.core.container import get_container
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
_log = get_logger("handler.referral")


@router.message(F.text.in_(["👥 دعوت دوستان", "👥 Invite friends"]))
async def referral_info(message: Message, state: FSMContext) -> None:
    """نمایش اطلاعات رفرال و لینک دعوت."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    try:
        stats = await container.referral_service.get_referral_stats(message.from_user.id)
    except Exception as exc:
        _log.error("referral.stats_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    await message.answer(
        t("referral_text", "fa").format(
            link=stats.get("referral_link", ""),
            count=stats.get("total_referrals", 0),
            xp=stats.get("xp_earned", 0),
        ),
        reply_markup=main_menu("fa"),
    )


@router.message(F.text == "/daily")
@router.message(F.text == "🎁 پاداش روزانه")
async def daily_reward(message: Message, state: FSMContext) -> None:
    """دریافت پاداش روزانه."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    try:
        claimed, xp = await container.referral_service.claim_daily_reward(message.from_user.id)
    except Exception as exc:
        _log.error("referral.daily_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    if claimed:
        await message.answer(
            t("daily_reward_claimed", "fa").format(xp=xp),
            reply_markup=main_menu("fa"),
        )
    else:
        await message.answer(t("daily_reward_already", "fa"))


@router.message(F.text == "/achievements")
@router.message(F.text == "🏆 دستاوردها")
async def show_achievements(message: Message, state: FSMContext) -> None:
    """نمایش دستاوردهای کاربر."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    try:
        achievements = await container.achievement_service.get_user_achievements(
            message.from_user.id
        )
    except Exception as exc:
        _log.error("achievements.list_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    if not achievements:
        await message.answer(t("achievements_empty", "fa"), reply_markup=main_menu("fa"))
        return

    text = f"🏆 {t('achievements_title', 'fa')}\n\n"
    for ach in achievements:
        text += f"{ach['icon']} {ach['name']} — {ach['description']}\n"
        if ach.get("earned_at"):
            text += f"   📅 {ach['earned_at'][:10]}\n"
        text += "\n"

    await message.answer(text, reply_markup=main_menu("fa"))
