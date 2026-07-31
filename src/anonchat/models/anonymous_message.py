"""مدل پیام ناشناس — پیام‌های ارسالی از طریق لینک ناشناس."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class AnonymousMessage(Base, TimestampMixin):
    """پیام ناشناس ارسال‌شده از طریق لینک.

    کاربر یک لینک اختصاصی دارد. دیگران با کلیک روی لینک می‌توانند
    بدون افشای هویت به او پیام بفرستند.
    """

    __tablename__ = "anonymous_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    """شناسه‌ی صاحب لینک (گیرنده)."""

    sender_telegram_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    """شناسه‌ی تلگرام فرستنده ناشناس — فقط برای Rate Limit و anti-spam."""

    sender_display_name: Mapped[str] = mapped_column(
        String(32), default="ناشناس", nullable=False
    )
    """نام نمایشی فرستنده — به گیرنده نشان داده می‌شود (مثل «ناشناس #۵»)."""

    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    """text | photo | video | document | voice | audio | sticker | animation | video_note"""

    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    """متن پیام یا کپشن (برای پیام متنی)."""

    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """آیا گیرنده پیام را دیده است؟"""

    is_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """آیا این پیام پاسخ به پیام ناشناس قبلی است؟"""

    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("anonymous_messages.id", ondelete="SET NULL"), nullable=True
    )
    """اگر پاسخ است، شناسه‌ی پیام اصلی."""

    direction: Mapped[str] = mapped_column(String(8), default="in", nullable=False)
    """in = از ناشناس به صاحب لینک | out = از صاحب لینک به ناشناس"""

    forwarded_to_chat_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    """اگر گیرنده پیام را به کانال/گروه فوروارد کرده، شناسه‌ی آن چت."""

    telegram_message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    """شناسه‌ی پیام در چت گیرنده — برای reply."""

    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_id])

    def __repr__(self) -> str:
        return f"<AnonymousMessage id={self.id} recipient={self.recipient_id} dir={self.direction}>"
