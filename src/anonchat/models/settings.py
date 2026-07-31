"""مدل تنظیمات سراسری — ذخیره‌ی پیکربندی‌های قابل تغییر در زمان اجرا."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from anonchat.db.base import Base, TimestampMixin


class Setting(Base, TimestampMixin):
    """تنظیمات کلید-مقدار سراسری ربات."""

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), default="string", nullable=False)
    """string | int | bool | json"""
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Setting key={self.key} value={self.value!r}>"


class DailyMission(Base, TimestampMixin):
    """مأموریت روزانه — برای گیمیفیکیشن."""

    __tablename__ = "daily_missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<DailyMission code={self.code}>"
