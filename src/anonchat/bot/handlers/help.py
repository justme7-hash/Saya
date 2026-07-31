"""هندلرهای راهنما و آمار کاربر."""

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
_log = get_logger("handler.help")


@router.message(F.text.in_(["❓ راهنما", "❓ Help"]))
@router.message(F.text == "/help")
async def help_command(message: Message, state: FSMContext) -> None:
    """نمایش راهنما."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    await message.answer(
        f"❓ {t('help_title', 'fa')}\n\n{t('help_text', 'fa')}",
        reply_markup=main_menu("fa"),
    )


@router.message(F.text.in_(["📊 آمار من", "📊 My stats"]))
@router.message(F.text == "/stats")
async def my_stats(message: Message, state: FSMContext) -> None:
    """نمایش آمار کاربر."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    try:
        stats = await container.stats_service.get_user_stats(message.from_user.id)
    except Exception as exc:
        _log.error("stats.user_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    if not stats:
        await message.answer(t("error_not_registered", "fa"))
        return

    text = (
        f"📊 {t('stats_title', 'fa')}\n\n"
        f"📈 {t('stats_level', 'fa')}: {stats.get('level', 1)}\n"
        f"⭐ {t('stats_xp', 'fa')}: {stats.get('xp', 0)}\n"
        f"💬 {t('stats_chats', 'fa')}: {stats.get('total_chats', 0)}\n"
        f"📤 {t('stats_sent', 'fa')}: {stats.get('total_messages_sent', 0)}\n"
        f"📥 {t('stats_received', 'fa')}: {stats.get('total_messages_received', 0)}\n"
    )
    await message.answer(text, reply_markup=main_menu("fa"))


@router.message(F.text == "/leaderboard")
async def leaderboard(message: Message, state: FSMContext) -> None:
    """نمایش جدول رتبه‌بندی."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است، آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    try:
        top = await container.stats_service.get_leaderboard(metric="xp", limit=10)
    except Exception as exc:
        _log.error("stats.leaderboard_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return

    if not top:
        await message.answer("هنوز جدول رتبه‌بندی آماده نیست.")
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 جدول رتبه‌بندی\n\n"
    for i, user in enumerate(top):
        medal = medals[i] if i < 3 else f"{i + 1}."
        # top لیستی از dictها است (از stats_service.get_leaderboard)
        nickname = user.get("nickname") if isinstance(user, dict) else getattr(user, "nickname", None)
        level = user.get("level") if isinstance(user, dict) else getattr(user, "level", 0)
        xp = user.get("xp") if isinstance(user, dict) else getattr(user, "xp", 0)
        text += f"{medal} {nickname or 'ناشناس'} — سطح {level} ({xp} XP)\n"

    await message.answer(text, reply_markup=main_menu("fa"))
