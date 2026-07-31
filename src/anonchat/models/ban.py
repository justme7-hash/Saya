"""مدل بن کاربر — موقت یا دائم."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class Ban(Base, TimestampMixin):
    """رکورد بن یک کاربر."""

    __tablename__ = "bans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    banned_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    """اگر بن موقت باشد، زمان پایان؛ اگر دائم، NULL."""

    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    banned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    """مدیری که بن کرده، یا NULL برای بن خودکار."""

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    unbanned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    unbanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(
        "User", foreign_keys=[user_id], back_populates="bans"
    )

    @property
    def is_expired(self) -> bool:
        """آیا بن منقضی شده؟"""
        if self.is_permanent:
            return False
        if self.banned_until is None:
            return False
        # SQLite ممکن است datetime را naive ذخیره کند — هردو حالت را پوشش بده
        until = self.banned_until
        now = datetime.now(UTC)
        if until.tzinfo is None:
            until = until.replace(tzinfo=UTC)
        return now >= until

    def __repr__(self) -> str:
        kind = "permanent" if self.is_permanent else "temporary"
        return f"<Ban user={self.user_id} kind={kind} active={self.is_active}>"
