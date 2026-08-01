"""هندلرهای پیام ناشناس — ارسال، دریافت، پاسخ و فوروارد.

جریان:
1. فرستنده روی لینک ناشناس کلیک می‌کند → /start anon_{code}
2. ربات وارد حالت composing_message می‌شود
3. فرستنده پیام می‌فرستد → ربات به گیرنده رله می‌کند
4. گیرنده پیام را با دکمه‌های پاسخ/فوروارد می‌بیند
5. گیرنده می‌تواند پاسخ دهد یا به کانال/گروه فوروارد کند
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import (
    anon_link_keyboard,
    anon_message_keyboard,
    cancel_keyboard,
    main_menu,
)
from anonchat.bot.states.fsm import AnonymousStates
from anonchat.bot.utils import reset_user_state
from anonchat.core.container import get_container
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
router.message.filter(F.from_user.is_not(None))
_log = get_logger("handler.anon")


def _parse_anon_msg_id(callback_data: str) -> int | None:
    """استخراج امن msg_id از callback_data.

    callback_data مثل «anon_reply_123» است. این تابع 123 را برمی‌گرداند.
    اگر فرمت نامعتبر باشد، None برمی‌گرداند (بدون IndexError یا ValueError).
    """
    try:
        parts = callback_data.split("_", 2)
        if len(parts) < 3:
            return None
        return int(parts[2])
    except (ValueError, TypeError, IndexError):
        return None


# ---------------------------------------------------------------------------
#  نمایش لینک ناشناس (برای صاحب لینک)
# ---------------------------------------------------------------------------

@router.message(F.text == "🔗 لینک ناشناس من")
async def show_anon_link(message: Message, state: FSMContext) -> None:
    """نمایش لینک پیام ناشناس کاربر."""
    container = get_container()
    # اگر کاربر در حال عملیات دیگری است (مثل composing_message)،
    # آن را لغو کن و state را پاک کن.
    await reset_user_state(container, message.from_user.id, state)
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"
        is_registered = bool(db_user and db_user.is_registered)

    if not is_registered:
        await message.answer(t("error_not_registered", locale))
        return

    try:
        link = await container.anon_message_service.get_anon_link(message.from_user.id)
    except Exception as exc:
        _log.error("anon.link_failed", error=str(exc))
        await message.answer(t("error_generic", locale))
        return

    await message.answer(
        t("anon_link_text", locale).format(link=link),
        reply_markup=anon_link_keyboard(locale, link),
    )


@router.callback_query(F.data == "anon_copy_link")
async def copy_anon_link(callback: CallbackQuery) -> None:
    """نمایش لینک ناشناس به‌صورت کپی‌شدنی.

    چون Bot API امکان کپی مستقیم در کلیپ‌بورد را ندارد، لینک را در یک پیام
    جداگانه با فرمت `<code>` نمایش می‌دهیم تا کاربر با کلیک روی آن کپی کند.
    """
    container = get_container()
    try:
        link = await container.anon_message_service.get_anon_link(callback.from_user.id)
    except Exception as exc:
        _log.error("anon.copy_link_failed", error=str(exc))
        await callback.answer("خطا در دریافت لینک", show_alert=True)
        return

    await callback.message.answer(  # type: ignore[attr-defined]
        f"📋 لینک ناشناس شما (برای کپی کلیک کنید):\n\n<code>{link}</code>"
    )
    await callback.answer("لینک نمایش داده شد")


# ---------------------------------------------------------------------------
#  شروع ارسال پیام ناشناس (برای فرستنده — از deep link)
# ---------------------------------------------------------------------------

async def start_anon_compose(message: Message, state: FSMContext, anon_code: str) -> None:
    """شروع حالت ارسال پیام ناشناس.

    این متد از start.py صدا زده می‌شود وقتی کاربر روی لینک ناشناس کلیک می‌کند.
    """
    container = get_container()
    try:
        recipient_tg = await container.anon_message_service.resolve_recipient(anon_code)
    except Exception:
        recipient_tg = None

    if recipient_tg is None:
        await message.answer(t("anon_recipient_not_found", "fa"))
        return

    if recipient_tg == message.from_user.id:
        await message.answer("شما نمی‌توانید به خودتان پیام ناشناس بفرستید! 😄")
        return

    # بررسی Rate Limit
    allowed = await container.anon_message_service.check_rate_limit(message.from_user.id)
    if not allowed:
        await message.answer(t("anon_rate_limited", "fa"))
        return

    # ذخیره‌ی اطلاعات در state
    await state.update_data(
        anon_recipient_tg=recipient_tg,
        anon_code=anon_code,
    )
    await state.set_state(AnonymousStates.composing_message)

    await message.answer(
        t("anon_compose_intro", "fa"),
        reply_markup=cancel_keyboard("fa"),
    )


# ---------------------------------------------------------------------------
#  دریافت پیام از فرستنده ناشناس
# ---------------------------------------------------------------------------

@router.message(AnonymousStates.composing_message)
async def receive_anon_message(message: Message, state: FSMContext) -> None:
    """دریافت پیام از فرستنده و رله به گیرنده."""
    container = get_container()

    # اگر متن لغو بود
    if message.text and message.text.strip() in ("❌ لغو", "❌ Cancel", "/cancel"):
        await state.clear()
        await message.answer(t("anon_cancelled", "fa"), reply_markup=main_menu("fa"))
        return

    data = await state.get_data()
    recipient_tg = data.get("anon_recipient_tg")
    if recipient_tg is None:
        await state.clear()
        await message.answer(t("error_generic", "fa"))
        return

    # ذخیره و رله
    success = await container.anon_message_service.save_and_relay(
        message.bot,  # type: ignore[arg-type]
        message,
        recipient_telegram_id=recipient_tg,
        sender_telegram_id=message.from_user.id,
    )

    await state.clear()

    if success:
        await message.answer(t("anon_sent_success", "fa"), reply_markup=main_menu("fa"))
    else:
        await message.answer(
            t("anon_rate_limited", "fa"),
            reply_markup=main_menu("fa"),
        )


# ---------------------------------------------------------------------------
#  پاسخ به پیام ناشناس (برای صاحب لینک)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("anon_reply_"))
async def start_reply(callback: CallbackQuery, state: FSMContext) -> None:
    """شروع پاسخ به یک پیام ناشناس."""
    msg_id = _parse_anon_msg_id(callback.data or "")  # type: ignore[arg-type]
    if msg_id is None:
        _log.warning("anon.invalid_callback_data", data=callback.data)
        try:
            await callback.answer("خطا: داده نامعتبر", show_alert=True)
        except Exception:
            pass
        return
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    await state.update_data(anon_reply_to=msg_id)
    await state.set_state(AnonymousStates.replying)

    await callback.message.answer(  # type: ignore[attr-defined]
        t("anon_reply_prompt", locale),
        reply_markup=cancel_keyboard(locale),
    )
    await callback.answer()


@router.message(AnonymousStates.replying)
async def process_reply(message: Message, state: FSMContext) -> None:
    """پردازش پاسخ صاحب لینک."""
    if message.text and message.text.strip() in ("❌ لغو", "❌ Cancel", "/cancel"):
        await state.clear()
        await message.answer(t("anon_cancelled", "fa"), reply_markup=main_menu("fa"))
        return

    data = await state.get_data()
    msg_id = data.get("anon_reply_to")
    if msg_id is None:
        await state.clear()
        await message.answer(t("error_generic", "fa"))
        return

    container = get_container()
    success = await container.anon_message_service.reply_to_anon(
        message.bot,  # type: ignore[arg-type]
        message,
        anon_msg_id=msg_id,
        sender_telegram_id=message.from_user.id,
    )

    await state.clear()

    if success:
        await message.answer(t("anon_reply_sent", "fa"), reply_markup=main_menu("fa"))
    else:
        await message.answer(t("error_generic", "fa"), reply_markup=main_menu("fa"))


# ---------------------------------------------------------------------------
#  فوروارد پیام ناشناس به کانال/گروه
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("anon_fwd_"))
async def start_forward(callback: CallbackQuery, state: FSMContext) -> None:
    """شروع فوروارد پیام ناشناس — کاربر باید یک پیام از کانال/گروه فوروارد کند.

    فیلتر فقط با ``anon_fwd_`` شروع می‌شود. ``anon_fwd_channel_`` و
    ``anon_fwd_group_`` با هندلرهای جداگانه (در صورت نیاز) مدیریت می‌شوند.
    در اینجا فقط ``anon_fwd_{msg_id}`` (بدون channel/group) هندل می‌شود.
    """
    # بررسی اینکه channel_ یا group_ نباشد
    if callback.data and ("anon_fwd_channel_" in callback.data or "anon_fwd_group_" in callback.data):
        # این callback برای این هندلر نیست — اجازه دهیم به هندلر بعدی برود
        # ولی در aiogram، وقتی هندلر match شد، نمی‌توان رد کرد. پس return می‌کنیم.
        try:
            await callback.answer()
        except Exception:
            pass
        return

    msg_id = _parse_anon_msg_id(callback.data or "")  # type: ignore[arg-type]
    if msg_id is None:
        _log.warning("anon.invalid_callback_data", data=callback.data)
        try:
            await callback.answer("خطا: داده نامعتبر", show_alert=True)
        except Exception:
            pass
        return
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    await state.update_data(anon_fwd_msg_id=msg_id)
    await state.set_state(AnonymousStates.waiting_forward_target)

    await callback.message.answer(  # type: ignore[attr-defined]
        t("anon_forward_prompt", locale),
        reply_markup=cancel_keyboard(locale),
    )
    await callback.answer()


@router.message(AnonymousStates.waiting_forward_target, F.forward_origin)
async def process_forward_target(message: Message, state: FSMContext) -> None:
    """پردازش مقصد فوروارد — کاربر یک پیام از کانال/گروه فوروارد کرده.

    ما از forward_origin برای تشخیص chat_id مقصد استفاده می‌کنیم.
    سپس پیام ناشناس را به آن چت فوروارد می‌کنیم.
    """
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(message.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    data = await state.get_data()
    msg_id = data.get("anon_fwd_msg_id")
    if msg_id is None:
        await state.clear()
        await message.answer(t("error_generic", locale))
        return

    # تشخیص chat_id مقصد از forward_origin
    # باگ: در aiogram 3.x نوع forward_origin ممکن است CHANNEL/CHAT/USER باشد.
    # اگر کاربر پیام فوروارد‌شده از یک کاربر خصوصی بفرستد، نوع MessageOriginUser است
    # و sender_chat ندارد — باید پیام خطای مناسب نمایش دهیم.
    target_chat_id = None
    is_private_user_origin = False
    if message.forward_origin:
        from aiogram.enums import MessageOriginType
        origin = message.forward_origin
        if origin.type == MessageOriginType.CHANNEL:
            target_chat_id = origin.chat.id
        elif origin.type == MessageOriginType.CHAT:
            target_chat_id = origin.sender_chat.id if origin.sender_chat else None
        elif origin.type == MessageOriginType.USER:
            # فوروارد از کاربر خصوصی — chat_id گروه/کانال در دسترس نیست
            is_private_user_origin = True

    if target_chat_id is None:
        if is_private_user_origin:
            await message.answer(
                "❌ نمی‌توان پیام ناشناس را به یک کاربر خصوصی فوروارد کرد. "
                "لطفاً یک پیام از کانال یا گروه فوروارد کنید.",
            )
        else:
            await message.answer(
                "❌ نمی‌توانستم مقصد را تشخیص دهم. یک پیام از کانال/گروه فوروارد کنید.",
            )
        return

    # فوروارد پیام ناشناس
    success = await container.anon_message_service.forward_to_chat(
        message.bot,  # type: ignore[arg-type]
        anon_msg_id=msg_id,
        target_chat_id=target_chat_id,
    )

    await state.clear()

    if success:
        await message.answer(
            t("anon_forward_success", locale),
            reply_markup=main_menu(locale),
        )
    else:
        await message.answer(
            t("anon_forward_failed", locale),
            reply_markup=main_menu(locale),
        )


# ---------------------------------------------------------------------------
#  علامت‌گذاری به‌عنوان خوانده‌شده
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("anon_read_"))
async def mark_read(callback: CallbackQuery) -> None:
    """علامت‌گذاری پیام ناشناس به‌عنوان خوانده‌شده."""
    msg_id = _parse_anon_msg_id(callback.data or "")  # type: ignore[arg-type]
    if msg_id is None:
        _log.warning("anon.invalid_callback_data", data=callback.data)
        try:
            await callback.answer("خطا: داده نامعتبر", show_alert=True)
        except Exception:
            pass
        return
    container = get_container()
    await container.anon_message_service.mark_as_read(msg_id)
    await callback.answer(t("anon_marked_read", "fa"))


# ---------------------------------------------------------------------------
#  صندوق پیام‌های ناشناس
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "anon_inbox")
async def show_inbox(callback: CallbackQuery) -> None:
    """نمایش صندوق پیام‌های ناشناس."""
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    unread = await container.anon_message_service.get_unread_count(callback.from_user.id)
    messages = await container.anon_message_service.get_user_anon_messages(
        callback.from_user.id, limit=10
    )

    if not messages:
        await callback.message.answer(t("anon_inbox_empty", locale))  # type: ignore[attr-defined]
        await callback.answer()
        return

    text = f"{t('anon_inbox_title', locale)}\n"
    text += f"{t('anon_inbox_count', locale).format(count=unread)}\n\n"

    for msg in messages:
        status = "🔵" if not msg.is_read else "⚪"
        text += f"{status} <b>{msg.sender_display_name}</b> — {msg.message_type}"
        if msg.text_content:
            preview = msg.text_content[:50]
            if len(msg.text_content) > 50:
                preview += "..."
            text += f"\n   📝 {preview}"
        text += f"\n   📅 {msg.created_at.strftime('%Y-%m-%d %H:%M')}"
        text += "\n\n"

    await callback.message.answer(text[:4000])  # type: ignore[attr-defined]
    await callback.answer()


# ---------------------------------------------------------------------------
#  لغو عملیات ناشناس
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "anon_cancel")
async def cancel_anon_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """لغو از دکمه‌ی اینلاین."""
    await state.clear()
    container = get_container()
    async with container.session() as session:
        user_repo = container.user_repo_with(session)
        db_user = await user_repo.get_by_telegram_id(callback.from_user.id)
        locale = getattr(db_user, "language", None) or "fa"

    await callback.message.answer(  # type: ignore[attr-defined]
        t("anon_cancelled", locale),
        reply_markup=main_menu(locale),
    )
    await callback.answer()


@router.message(AnonymousStates.composing_message, F.text == "/cancel")
@router.message(AnonymousStates.replying, F.text == "/cancel")
@router.message(AnonymousStates.waiting_forward_target, F.text == "/cancel")
async def cancel_anon_command(message: Message, state: FSMContext) -> None:
    """لغو با دستور /cancel."""
    await state.clear()
    await message.answer(t("anon_cancelled", "fa"), reply_markup=main_menu("fa"))
