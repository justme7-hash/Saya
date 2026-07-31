"""هندلرهای پنل مدیریت."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.bot.keyboards import admin_panel_keyboard
from anonchat.bot.states.fsm import AdminStates
from anonchat.core.container import get_container
from anonchat.core.exceptions import UserNotFoundError
from anonchat.core.logging import get_logger
from anonchat.i18n import t

router = Router()
_log = get_logger("handler.admin")


@router.message(F.text == "/admin")
async def admin_panel(message: Message) -> None:
    """ورود به پنل مدیریت."""
    container = get_container()
    if not container.settings.is_admin(message.from_user.id):
        await message.answer(t("admin_only", "fa"))
        return
    await message.answer(t("admin_panel", "fa"), reply_markup=admin_panel_keyboard("fa"))


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery) -> None:
    """نمایش آمار سیستم."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    try:
        stats = await container.admin_service.get_stats_overview()
    except Exception as exc:
        _log.error("admin.stats_failed", error=str(exc))
        await callback.message.answer(t("error_generic", "fa"))  # type: ignore[attr-defined]
        await callback.answer()
        return

    text = (
        f"📊 آمار سیستم\n\n"
        f"👥 کل کاربران: {stats.get('total_users', 0)}\n"
        f"🟢 آنلاین: {stats.get('online_users', 0)}\n"
        f"📅 فعال امروز: {stats.get('active_today', 0)}\n"
        f"💬 گفتگوهای فعال: {stats.get('active_chats', 0)}\n"
        f"🚩 گزارش‌های در انتظار: {stats.get('pending_reports', 0)}\n"
        f"🚫 بن‌های فعال: {stats.get('active_bans', 0)}\n"
        f"⏱️ میانگین مدت گفتگو: {stats.get('avg_chat_duration_min', 0):.1f} دقیقه\n"
    )
    await callback.message.answer(text)  # type: ignore[attr-defined]
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery) -> None:
    """لیست کاربران."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    try:
        result = await container.admin_service.get_user_list(page=1, per_page=10)
    except Exception as exc:
        _log.error("admin.users_failed", error=str(exc))
        await callback.message.answer(t("error_generic", "fa"))  # type: ignore[attr-defined]
        await callback.answer()
        return

    text = f"👥 مدیریت کاربران (صفحه ۱ از {result['pages']})\n\n"
    for u in result["users"]:
        text += (
            f"• {u.nickname or '—'} (ID: {u.telegram_id})\n"
            f"  سطح {u.level} | {u.total_chats} گفتگو | ریسک: {u.risk_score}\n\n"
        )
    await callback.message.answer(text[:4000])  # type: ignore[attr-defined]
    await callback.answer()


@router.callback_query(F.data == "admin_reports")
async def admin_reports(callback: CallbackQuery) -> None:
    """گزارش‌های در انتظار."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    try:
        reports = await container.admin_service.get_pending_reports(limit=10)
    except Exception as exc:
        _log.error("admin.reports_failed", error=str(exc))
        await callback.message.answer(t("error_generic", "fa"))  # type: ignore[attr-defined]
        await callback.answer()
        return

    if not reports:
        await callback.message.answer("✅ هیچ گزارش در انتظاری وجود ندارد.")  # type: ignore[attr-defined]
        await callback.answer()
        return

    text = "🚩 گزارش‌های در انتظار\n\n"
    for r in reports:
        text += f"• گزارش #{r.id}\n  دلیل: {r.reason}\n  گزارش‌دهنده: {r.reporter_id}\n\n"
    await callback.message.answer(text[:4000])  # type: ignore[attr-defined]
    await callback.answer()


@router.callback_query(F.data == "admin_ban")
async def admin_ban_start(callback: CallbackQuery, state: FSMContext) -> None:
    """شروع فرآیند بن."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    await state.set_state(AdminStates.waiting_ban_input)
    await callback.message.answer(t("admin_ban_prompt", "fa"))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(AdminStates.waiting_ban_input)
async def admin_ban_process(message: Message, state: FSMContext) -> None:
    """پردازش بن کاربر."""
    container = get_container()
    from anonchat.schemas.admin import BanActionDTO
    text = (message.text or "").strip()
    parts = text.split(" - ", 1)
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("فرمت نامعتبر. مثال: 123456789 - دلیل بن")
        return
    telegram_id = int(parts[0])
    reason = parts[1]
    try:
        await container.admin_service.ban_user(
            BanActionDTO(user_telegram_id=telegram_id, reason=reason, permanent=False, duration_hours=24),
            message.from_user.id,
        )
    except UserNotFoundError:
        await message.answer(t("admin_user_not_found", "fa"))
        await state.clear()
        return
    except Exception as exc:
        _log.error("admin.ban_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        await state.clear()
        return
    await state.clear()
    await message.answer(t("admin_banned", "fa"), reply_markup=admin_panel_keyboard("fa"))


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    """شروع ارسال پیام همگانی."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.message.answer(t("admin_broadcast_prompt", "fa"))  # type: ignore[attr-defined]
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_text)
async def admin_broadcast_process(message: Message, state: FSMContext) -> None:
    """پردازش ارسال پیام همگانی."""
    container = get_container()
    from anonchat.schemas.admin import BroadcastDTO
    text = (message.text or "").strip()
    if not text:
        await message.answer("متن خالی است.")
        return
    try:
        count = await container.admin_service.broadcast(
            message.bot,  # type: ignore[arg-type]
            BroadcastDTO(message=text, target="all"),
            message.from_user.id,
        )
    except Exception as exc:
        _log.error("admin.broadcast_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        await state.clear()
        return
    await state.clear()
    await message.answer(
        t("admin_broadcast_sent", "fa").format(count=count),
        reply_markup=admin_panel_keyboard("fa"),
    )


@router.callback_query(F.data == "admin_maintenance")
async def admin_maintenance_toggle(callback: CallbackQuery) -> None:
    """تغییر وضعیت حالت نگهداری."""
    container = get_container()
    if not container.settings.is_admin(callback.from_user.id):
        await callback.answer(t("admin_only", "fa"))
        return
    current = container.settings.maintenance_mode
    new_state = not current
    try:
        await container.admin_service.set_maintenance(new_state, callback.from_user.id)
    except Exception as exc:
        _log.error("admin.maintenance_failed", error=str(exc))
        await callback.answer(t("error_generic", "fa"))
        return
    # آپدیت تنظیمات در حافظه
    container.settings.maintenance_mode = new_state
    msg = t("admin_maintenance_on", "fa") if new_state else t("admin_maintenance_off", "fa")
    await callback.message.answer(msg)  # type: ignore[attr-defined]
    await callback.answer()


@router.message(F.text == "/unban")
async def admin_unban(message: Message) -> None:
    """لغو بن با فرمت: /unban TELEGRAM_ID"""
    container = get_container()
    if not container.settings.is_admin(message.from_user.id):
        await message.answer(t("admin_only", "fa"))
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("فرمت: /unban TELEGRAM_ID")
        return
    telegram_id = int(parts[1])
    try:
        result = await container.admin_service.unban_user(telegram_id, message.from_user.id)
    except UserNotFoundError:
        await message.answer(t("admin_user_not_found", "fa"))
        return
    except Exception as exc:
        _log.error("admin.unban_failed", error=str(exc))
        await message.answer(t("error_generic", "fa"))
        return
    if result:
        await message.answer(t("admin_unbanned", "fa"))
    else:
        await message.answer("این کاربر بن نشده است.")
