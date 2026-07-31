"""مدل لاگ امنیتی — ثبت رویدادهای امنیتی برای حسابرسی."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from anonchat.db.base import Base, TimestampMixin


class SecurityLog(Base, TimestampMixin):
    """رکورد رویداد امنیتی."""

    __tablename__ = "security_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    """rate_limit | flood | suspicious | ban | unban | warning | report | login"""

    severity: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    """debug | info | warning | error | critical"""

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SecurityLog type={self.event_type} severity={self.severity}>"


class AuditLog(Base, TimestampMixin):
    """رکورد حسابرسی — عملیات مدیران."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    """ban | unban | block | broadcast | config_change | maintenance"""
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog admin={self.admin_id} action={self.action}>"
