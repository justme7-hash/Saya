"""مدل رفرال — دعوت دوستان."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class Referral(Base, TimestampMixin):
    """رکورد دعوت موفق یک کاربر توسط کاربر دیگر."""

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    referred_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    reward_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    referrer: Mapped[User] = relationship(
        "User", foreign_keys=[referrer_id], back_populates="referrals_made"
    )

    def __repr__(self) -> str:
        return f"<Referral referrer={self.referrer_id} referred={self.referred_id}>"
