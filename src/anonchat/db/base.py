"""کلاس پایه‌ی declarative برای مدل‌های SQLAlchemy 2.x.

از سبک جدید (Mapped / mapped_column) استفاده می‌شود که تایپ‌سیف است.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# قرارداد نام‌گذاری برای مهاجرت‌های خودکار Alembic
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """کلاس پایه‌ی تمام مدل‌ها."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def to_dict(self) -> dict[str, Any]:
        """تبدیل مدل به دیکشنری (برای سریال‌سازی و DTO)."""
        result: dict[str, Any] = {}
        for column in self.__table__.columns:  # type: ignore[attr-defined]
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def __repr__(self) -> str:
        pk = getattr(self, "id", "?")
        return f"<{self.__class__.__name__} id={pk}>"


class TimestampMixin:
    """Mixin برای افزودن ستون‌های زمان ایجاد/به‌روزرسانی."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
