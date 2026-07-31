"""هندلرهای گفتگو — رله‌ی پیام و کنترل گفتگو."""

from __future__ import annotations

import hashlib

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import (
    main_menu,
    report_reason_keyboard,
)
from anonchat.bot.states.fsm import ChatStates
from anonchat.core.container import get_container
from anonchat.core.exceptions import UserNotFoundError, UserNotInChatError
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
router.message.filter(F.from_user.is_not(None))
_log = get_logger("handler.chat")


@router.message(F.text.in_(["🛑 پایان گفتگو", "🛑 End chat"]))
async def end_chat(message: Message, state: FSMContext) -> None:
    """پایان گفتگو توسط کاربر."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    try:
        result = await container.chat_service.end_chat(
            message.from_user.id, reason="user_left"
        )
    except (UserNotInChatError, UserNotFoundError):
        await message.answer(t("error_not_in_chat", locale))
        return

    if result is None:
        await message.answer(t("error_not_in_chat", locale))
        return

    session_id, partner_id, partner_tg = result
    await state.clear()
    await message.answer(t("chat_ended", locale), reply_markup=main_menu(locale))

    # اطلاع به شریک
    if partner_tg:
        bot = message.bot
        async with container.session() as session:
            user_repo = container.user_repo_with(session)
            partner_user = await user_repo.get_by_telegram_id(partner_tg)
            partner_locale = getattr(partner_user, "language", None) or "fa"
        try:
            await bot.send_message(  # type: ignore[union-attr]
                partner_tg,
                t("chat_partner_ended", partner_locale),
                reply_markup=main_menu(partner_locale),
            )
        except Exception as exc:
            _log.error("chat.notify_partner_end_failed", error=str(exc))

    # پاکسازی کش امنیتی
    container.security_service.reset_user_state(message.from_user.id)
    if partner_tg:
        container.security_service.reset_user_state(partner_tg)

    # بررسی دستاوردها
    await container.achievement_service.check_and_award(message.from_user.id)


@router.message(F.text.in_(["🔄 پیدا کردن فرد جدید", "🔄 Find new partner"]))
async def find_new(message: Message, state: FSMContext) -> None:
    """پایان گفتگو فعلی و شروع جستجوی جدید."""
    container = get_container()
    try:
        await container.chat_service.end_chat(message.from_user.id, reason="find_new")
    except (UserNotInChatError, UserNotFoundError):
        pass
    # هدایت به هندلر جستجو
    await state.clear()
    # شبیه‌سازی کلیک جستجو
    from anonchat.bot.handlers.search import start_search
    await start_search(message, state)


@router.message(F.text.in_(["⭐ افزودن به محبوب‌ها", "⭐ Add to favorites"]))
async def add_favorite(message: Message) -> None:
    """افزودن شریک فعلی به محبوب‌ها."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    try:
        session_id, partner_id, partner_tg = await container.chat_service.get_active_partner(
            message.from_user.id
        )
    except (UserNotInChatError, UserNotFoundError):
        await message.answer(t("error_not_in_chat", locale))
        return

    async with container.session() as session:
        fav_repo = container.favorite_repo_with(session)
        existing = await fav_repo.is_favorite(db_user.id, partner_id)  # type: ignore[arg-type]
        if existing:
            already_fav = True
        else:
            await fav_repo.add_favorite(user_id=db_user.id, favorite_user_id=partner_id)  # type: ignore[arg-type]
            await session.commit()
            already_fav = False

    if already_fav:
        await message.answer("⭐ این کاربر قبلاً در محبوب‌های شماست.")
    else:
        await message.answer("⭐ به محبوب‌ها اضافه شد.")


@router.message(F.text.in_(["🚩 گزارش مخاطب", "🚩 Report partner"]))
async def start_report(message: Message, state: FSMContext) -> None:
    """شروع فرآیند گزارش مخاطب."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    try:
        await container.chat_service.get_active_partner(message.from_user.id)
    except (UserNotInChatError, UserNotFoundError):
        await message.answer(t("error_not_in_chat", locale))
        return

    await state.set_state(ChatStates.reporting)
    await message.answer(
        t("chat_report_prompt", locale),
        reply_markup=report_reason_keyboard(locale),
    )


@router.callback_query(ChatStates.reporting, F.data.startswith("report_"))
async def process_report(callback: CallbackQuery, state: FSMContext) -> None:
    """پردازش گزارش."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    reason = callback.data.split("_", 1)[1]  # type: ignore[union-attr]

    try:
        session_id, partner_id, partner_tg = await container.chat_service.get_active_partner(
            callback.from_user.id
        )
    except (UserNotInChatError, UserNotFoundError):
        await callback.answer(t("error_not_in_chat", locale))
        return

    await container.security_service.report_user(
        reporter_telegram_id=callback.from_user.id,
        reported_telegram_id=partner_tg,
        reason=reason,
        chat_session_id=session_id,
    )

    await state.clear()
    await callback.message.answer(t("report_filed", locale))  # type: ignore[attr-defined]
    await callback.answer()


# ---------------------------------------------------------------------------
#  رله‌ی پیام — همه‌ی انواع پیام هنگام گفتگو
# ---------------------------------------------------------------------------

@router.message()
async def relay_message(message: Message, state: FSMContext) -> None:
    """رله‌ی پیام کاربر به شریک گفتگو.

    این هندلر به‌عنوان fallback برای تمام پیام‌هایی که در گفتگو هستند عمل می‌کند.
    """
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"
        is_registered = bool(db_user and db_user.is_registered)
        is_in_chat = bool(db_user and db_user.is_in_chat)

    if not is_registered:
        # کاربر ثبت‌نام نکرده — پیام راهنما
        if not message.text or not message.text.startswith("/"):
            await message.answer(t("error_not_registered", locale))
        return

    if not is_in_chat:
        # کاربر در گفتگو نیست — اگر پیام متنی و دستور نیست، راهنمایی کن
        if message.text and not message.text.startswith("/") and message.text not in (
            "🔍 جستجوی مخاطب", "🔍 Find a partner",
            "⚙️ تنظیمات", "⚙️ Settings",
            "👤 پروفایل من", "👤 My profile",
            "📊 آمار من", "📊 My stats",
            "👥 دعوت دوستان", "👥 Invite friends",
            "❓ راهنما", "❓ Help",
            "🔗 لینک ناشناس من",
            "❌ لغو", "❌ Cancel",
        ):
            await message.answer(
                "برای شروع گفتگو از منوی اصلی «🔍 جستجوی مخاطب» را انتخاب کنید.",
                reply_markup=main_menu(locale),
            )
        return

    # کاربر در گفتگو است — رله‌ی پیام
    try:
        session_id, partner_id, partner_tg = await container.chat_service.get_active_partner(
            message.from_user.id
        )
    except (UserNotInChatError, UserNotFoundError):
        await message.answer(t("error_not_in_chat", locale))
        return

    # تشخیص Flood
    text_content = message.text or message.caption or ""
    content_hash = hashlib.sha256(text_content.encode()).hexdigest()[:32] if text_content else None
    try:
        await container.security_service.detect_flood(message.from_user.id, content_hash)
    except Exception:
        await message.answer(t("flood_message", locale))
        return

    # ارسال chat action (در حال تایپ) به شریک
    await container.message_service.send_chat_action(
        message.bot, partner_tg, "typing"  # type: ignore[arg-type]
    )

    # رله‌ی پیام
    success = await container.message_service.relay(
        message.bot,  # type: ignore[arg-type]
        message,
        partner_telegram_id=partner_tg,
        chat_session_id=session_id,
        sender_telegram_id=message.from_user.id,
    )

    if not success:
        await message.answer(t("error_generic", locale))
