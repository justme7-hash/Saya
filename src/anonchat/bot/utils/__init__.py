"""ابزارهای کمکی ربات."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container


_logger = get_logger("bot.utils")


def _is_not_modified_error(exc: Exception) -> bool:
    """آیا خطا مربوط به «message is not modified» است؟

    در این حالت نباید پیام جدید بفرستیم (تکرار پیام برای کاربر آزاردهنده است).
    """
    msg = str(exc).lower()
    return "not modified" in msg


async def safe_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: Any = None,
    parse_mode: str | None = None,
) -> None:
    """ویرایش امن پیام callback — اگر edit_text خطا دهد، پیام جدید می‌فرستد.

    این تابع از خطای «message is not modified» (که در این حالت پیام تکراری
    نمی‌فرستیم) و خطاهای پیام بدون متن (مثل عکس‌ها) جلوگیری می‌کند.
    """
    try:
        await callback.message.edit_text(  # type: ignore[attr-defined]
            text, reply_markup=reply_markup, parse_mode=parse_mode
        )
    except TelegramBadRequest as exc:
        # اگر پیام تغییر نکرده، نیازی به فرستادن پیام تکراری نیست.
        if _is_not_modified_error(exc):
            return
        try:
            await callback.message.answer(  # type: ignore[attr-defined]
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as exc2:
            _logger.exception("safe_edit_text.answer_failed", error=str(exc2))
    except Exception as exc:
        try:
            await callback.message.answer(  # type: ignore[attr-defined]
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception as exc2:
            _logger.exception("safe_edit_text.fallback_failed", error=str(exc2))


async def safe_edit_reply_markup(
    callback: CallbackQuery,
    reply_markup: Any = None,
) -> None:
    """ویرایش امن کیبورد اینلاین.

    اگر خطا «message is not modified» باشد، آن را بی‌صدا نادیده می‌گیریم
    (پیام تکراری نمی‌فرستیم).
    """
    try:
        await callback.message.edit_reply_markup(  # type: ignore[attr-defined]
            reply_markup=reply_markup
        )
    except TelegramBadRequest as exc:
        if _is_not_modified_error(exc):
            return
        _logger.exception("safe_edit_reply_markup.telegram_bad_request", error=str(exc))
    except Exception as exc:
        _logger.exception("safe_edit_reply_markup.failed", error=str(exc))


async def safe_answer(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    """پاسخ امن به callback — خطاها را نگه می‌دارد."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception as exc:
        _logger.exception("safe_answer.failed", error=str(exc))


async def reset_user_state(
    container: Container,
    telegram_id: int,
    state: FSMContext,
) -> None:
    """پاک کردن state کاربر و لغو جستجو در صورت نیاز.

    این تابع باید در ابتدای هندلرهای منو (پروفایل، تنظیمات، راهنما و...)
    صدا زده شود تا اگر کاربر در حال انجام عملیاتی است (مثل جستجو یا
    ویرایش پروفایل)، آن عملیات لغو شود و state پاک شود.

    Args:
        container: کانتینر DI.
        telegram_id: شناسه‌ی تلگرام کاربر.
        state: FSM context.
    """
    # بررسی اینکه آیا کاربر در حال جستجو است
    try:
        async with container.session() as session:
            user_repo = container.user_repo_with(session)
            db_user = await user_repo.get_by_telegram_id(telegram_id)
            is_searching = bool(db_user and db_user.is_searching)
    except Exception as exc:
        _logger.exception("reset_user_state.check_search_failed", error=str(exc))
        is_searching = False

    # اگر در حال جستجو است، لغو کن
    if is_searching:
        try:
            await container.matchmaking_service.cancel_search(telegram_id)
        except Exception as exc:
            _logger.exception("reset_user_state.cancel_search_failed", error=str(exc))

    # state را پاک کن
    try:
        await state.clear()
    except Exception as exc:
        _logger.exception("reset_user_state.clear_state_failed", error=str(exc))
