"""مدل کاربر.

هر کاربر تلگرام یک رکورد در این جدول دارد. شامل پروفایل، تنظیمات
حریم خصوصی، امتیاز XP/Level و وضعیت آنلاین.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.achievement import UserAchievement
    from anonchat.models.ban import Ban
    from anonchat.models.chat import ChatSession
    from anonchat.models.favorite import Favorite
    from anonchat.models.referral import Referral
    from anonchat.models.report import Report


class User(Base, TimestampMixin):
    """کاربر ربات سایه."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False
    )
    """شناسه عددی کاربر در تلگرام."""

    # --- پروفایل ---
    nickname: Mapped[str | None] = mapped_column(String(30), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str] = mapped_column(String(16), default="unspecified", nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="fa", nullable=False)
    interests: Mapped[str | None] = mapped_column(Text, nullable=True)
    """علایق به‌صورت رشته‌ی جدا شده با کاما."""
    profile_photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- تنظیمات حریم خصوصی ---
    show_age: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_country: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_gender: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # --- وضعیت ---
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_searching: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_in_chat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- گیمیفیکیشن ---
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    referral_code: Mapped[str] = mapped_column(
        String(16), unique=True, index=True, nullable=False
    )
    referred_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- امنیت ---
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- آمار ---
    total_chats: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_messages_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- روابط ---
    chat_sessions: Mapped[list[ChatSession]] = relationship(
        "ChatSession",
        foreign_keys="ChatSession.user_id",
        back_populates="user",
        lazy="selectin",
    )
    reports_made: Mapped[list[Report]] = relationship(
        "Report", foreign_keys="Report.reporter_id", back_populates="reporter"
    )
    reports_received: Mapped[list[Report]] = relationship(
        "Report", foreign_keys="Report.reported_id", back_populates="reported"
    )
    bans: Mapped[list[Ban]] = relationship(
        "Ban", foreign_keys="Ban.user_id", back_populates="user"
    )
    favorites: Mapped[list[Favorite]] = relationship(
        "Favorite", foreign_keys="Favorite.user_id", back_populates="user"
    )
    referrals_made: Mapped[list[Referral]] = relationship(
        "Referral", foreign_keys="Referral.referrer_id", back_populates="referrer"
    )
    achievements: Mapped[list[UserAchievement]] = relationship(
        "UserAchievement", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User tg={self.telegram_id} nick={self.nickname!r}>"
