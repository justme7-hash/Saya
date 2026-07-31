"""ابزارهای کمکی ربات."""

from __future__ import annotations

from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message


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
        except Exception:
            pass
    except Exception:
        try:
            await callback.message.answer(  # type: ignore[attr-defined]
                text, reply_markup=reply_markup, parse_mode=parse_mode
            )
        except Exception:
            pass


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
    except Exception:
        pass


async def safe_answer(
    callback: CallbackQuery,
    text: str | None = None,
    show_alert: bool = False,
) -> None:
    """پاسخ امن به callback — خطاها را نگه می‌دارد."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except Exception:
        pass
