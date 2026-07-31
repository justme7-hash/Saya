"""مخزن گزارش‌ها."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.report import Report


class ReportRepository(BaseRepository[Report]):
    """مخزن عملیات گزارش‌های کاربران."""

    model = Report

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_report(
        self,
        *,
        reporter_id: int,
        reported_id: int,
        reason: str,
        description: str | None = None,
        chat_session_id: int | None = None,
    ) -> Report:
        """ایجاد گزارش جدید."""
        report = Report(
            reporter_id=reporter_id,
            reported_id=reported_id,
            reason=reason,
            description=description,
            chat_session_id=chat_session_id,
            status="pending",
        )
        return await self.add(report)

    async def get_pending(self, *, limit: int = 50, offset: int = 0) -> list[Report]:
        """دریافت گزارش‌های در انتظار بررسی."""
        return await self.get_many(
            filters={"status": "pending"},
            limit=limit,
            offset=offset,
            order_by=Report.created_at.asc(),
        )

    async def count_pending(self) -> int:
        """تعداد گزارش‌های در انتظار."""
        return await self.count(status="pending")

    async def count_active_for_user(self, user_id: int) -> int:
        """تعداد گزارش‌های فعال علیه یک کاربر."""
        return await self.count(reported_id=user_id, status="pending")

    async def resolve_report(
        self,
        report_id: int,
        *,
        status: str,
        reviewed_by: int,
        admin_note: str | None = None,
    ) -> Report | None:
        """بررسی و تعیین تکلیف گزارش."""
        report = await self.get(report_id)
        if report is None:
            return None
        report.status = status
        report.reviewed_by = reviewed_by
        report.reviewed_at = datetime.now(UTC)
        report.admin_note = admin_note
        await self.session.flush()
        return report

    async def count_today(self) -> int:
        """تعداد گزارش‌های امروز."""
        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count()).select_from(Report).where(
            Report.created_at >= cutoff
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
