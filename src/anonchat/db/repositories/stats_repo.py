"""مخزن آمار — کوئری‌های تحلیلی برای داشبورد."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.models.ban import Ban
from anonchat.models.chat import ChatSession
from anonchat.models.report import Report
from anonchat.models.user import User


class StatsRepository:
    """مخزن کوئری‌های آماری و تحلیلی.

    این مخزن از BaseRepository ارث‌بری نمی‌کند چون چند-جدولی است.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(self) -> dict[str, int | float]:
        """خلاصه‌ی آمار کلی سیستم."""
        total_users = await self._count(User, User.is_registered.is_(True))
        online_users = await self._count(User, User.is_online.is_(True))
        active_chats = await self._count(ChatSession, ChatSession.status == "active")
        pending_reports = await self._count(Report, Report.status == "pending")
        active_bans = await self._count(Ban, Ban.is_active.is_(True))

        # کاربران فعال امروز
        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = await self.session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.last_seen >= cutoff, User.is_registered.is_(True))
        )

        # میانگین مدت گفتگو
        avg_duration = await self._avg_duration()

        return {
            "total_users": total_users,
            "online_users": online_users,
            "active_today": int(active_today or 0),
            "active_chats": active_chats,
            "pending_reports": pending_reports,
            "active_bans": active_bans,
            "avg_chat_duration_min": round(avg_duration, 2),
        }

    async def get_growth(self, days: int = 30) -> list[dict[str, object]]:
        """رشد کاربران در N روز گذشته (روزانه)."""
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        stmt = (
            select(
                func.date(User.created_at).label("day"),
                func.count().label("count"),
            )
            .where(User.created_at >= start, User.is_registered.is_(True))
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
        result = await self.session.execute(stmt)
        return [
            {"date": str(row.day), "count": row.count}
            for row in result.all()
        ]

    async def get_chat_stats(self, days: int = 7) -> dict[str, object]:
        """آمار گفتگو در N روز گذشته."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        total = await self.session.scalar(
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.started_at >= cutoff)
        )
        ended = await self.session.scalar(
            select(func.count())
            .select_from(ChatSession)
            .where(
                ChatSession.started_at >= cutoff,
                ChatSession.status == "ended",
            )
        )
        total_messages = await self.session.scalar(
            select(func.sum(ChatSession.message_count)).where(
                ChatSession.started_at >= cutoff
            )
        )
        return {
            "total_chats": int(total or 0),
            "ended_chats": int(ended or 0),
            "total_messages": int(total_messages or 0),
        }

    async def get_top_users(self, *, metric: str = "xp", limit: int = 10) -> list[User]:
        """جدول رتبه‌بندی کاربران."""
        column = getattr(User, metric, User.xp)
        stmt = (
            select(User)
            .where(User.is_registered.is_(True))
            .order_by(column.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------ #
    #  کمکی
    # ------------------------------------------------------------------ #

    async def _count(self, model, *filters) -> int:
        stmt = select(func.count()).select_from(model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def _avg_duration(self) -> float:
        stmt = select(ChatSession).where(ChatSession.status == "ended")
        result = await self.session.execute(stmt)
        sessions = result.scalars().all()
        if not sessions:
            return 0.0
        total = sum(s.duration_seconds for s in sessions)
        return total / len(sessions) / 60.0
