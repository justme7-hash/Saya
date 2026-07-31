"""مدل گزارش کاربر."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class Report(Base, TimestampMixin):
    """گزارش یک کاربر علیه کاربر دیگر در یک گفتگو."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reported_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chat_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )

    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    """spam | harassment | nsfw | scam | violence | other"""

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), default="pending", nullable=False, index=True
    )
    """pending | reviewed | actioned | dismissed"""

    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    reporter: Mapped[User] = relationship(
        "User", foreign_keys=[reporter_id], back_populates="reports_made"
    )
    reported: Mapped[User] = relationship(
        "User", foreign_keys=[reported_id], back_populates="reports_received"
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} reason={self.reason} status={self.status}>"
