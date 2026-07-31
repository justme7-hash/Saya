"""مدل دستاورد و دستاوردهای کاربر — سیستم گیمیفیکیشن."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class Achievement(Base, TimestampMixin):
    """تعریف یک دستاورد (کاتالوگ)."""

    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(16), default="🏆", nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="general", nullable=False)

    def __repr__(self) -> str:
        return f"<Achievement code={self.code}>"


class UserAchievement(Base, TimestampMixin):
    """دستاورد کسب‌شده توسط یک کاربر."""

    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    achievement_id: Mapped[int] = mapped_column(
        ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False
    )
    earned_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="achievements")
    achievement: Mapped[Achievement] = relationship("Achievement")

    def __repr__(self) -> str:
        return f"<UserAchievement user={self.user_id} ach={self.achievement_id}>"
