"""مدل علاقه‌مندی — کاربرانی که پس از پایان گفتگو به‌عنوان محبوب نشانه‌گذاری شده‌اند."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from anonchat.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from anonchat.models.user import User


class Favorite(Base, TimestampMixin):
    """کاربر محبوب پس از پایان گفتگو."""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "favorite_user_id", name="uq_favorites_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    favorite_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(
        "User", foreign_keys=[user_id], back_populates="favorites"
    )

    def __repr__(self) -> str:
        return f"<Favorite user={self.user_id} fav={self.favorite_user_id}>"
