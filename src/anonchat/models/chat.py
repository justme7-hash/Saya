"""مدل جلسه‌ی گفتگو (Chat Session).

هر گفتگو بین دو کاربر یک رکورد دارد که وضعیت، زمان شروع/پایان،
دلیل پایان و امتیاز را ذخیره می‌کند.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.message import Message
    from anonchat.models.user import User


class ChatSession(Base, TimestampMixin):
    """یک جلسه‌ی گفتگو ناشناس بین دو کاربر."""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    partner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False, index=True
    )
    """active | ended | disconnected | reported"""

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """user_left | partner_left | timeout | report | banned"""

    ended_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    """امتیاز ۱ تا ۵ که کاربر به گفتگو می‌دهد."""

    # --- روابط ---
    user: Mapped[User] = relationship(
        "User", foreign_keys=[user_id], back_populates="chat_sessions"
    )
    partner: Mapped[User] = relationship("User", foreign_keys=[partner_id])
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="chat_session", lazy="selectin"
    )

    @property
    def duration_seconds(self) -> float:
        """مدت زمان گفتگو به ثانیه."""
        end = self.ended_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} status={self.status}>"
