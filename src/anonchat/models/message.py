"""مدل پیام.

تمام پیام‌های رله‌شده بین کاربران برای آمار و گزارش‌گیری ذخیره می‌شوند.
محتوای پیام متنی برای حفظ ناشناسی به‌صورت هش‌شده یا خلاصه ذخیره می‌شود —
متن کامل هرگز ذخیره نمی‌شود (حریم خصوصی).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.chat import ChatSession


class Message(Base, TimestampMixin):
    """رکورد یک پیام رله‌شده در گفتگو."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    message_type: Mapped[str] = mapped_column(String(32), nullable=False)
    """text | photo | video | document | voice | audio | sticker | gif |
    video_note | location | contact | poll | animation"""

    # فقط برای پیام متنی: طول ذخیره می‌شود، نه محتوا (حریم خصوصی)
    text_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # خلاصه‌ی هش برای تشخیص اسپم تکراری (نه محتوای قابل خواندن)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # فقط در صورت گزارش، خلاصه‌ی کوتاه محتوا برای بررسی مدیر نگه داشته می‌شود
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_unique_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_forwarded: Mapped[bool] = mapped_column(String(5), default="false", nullable=False)
    is_reply: Mapped[bool] = mapped_column(String(5), default="false", nullable=False)

    chat_session: Mapped[ChatSession] = relationship(
        "ChatSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} type={self.message_type}>"
