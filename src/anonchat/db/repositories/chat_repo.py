"""مخزن گفتگو."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.chat import ChatSession


class ChatRepository(BaseRepository[ChatSession]):
    """مخزن عملیات جلسه‌ی گفتگو."""

    model = ChatSession

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_active_for_user(self, user_id: int) -> ChatSession | None:
        """دریافت گفتگوی فعال کاربر."""
        stmt = (
            select(ChatSession)
            .where(
                (ChatSession.user_id == user_id)
                | (ChatSession.partner_id == user_id),
                ChatSession.status == "active",
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_session(
        self, *, user_id: int, partner_id: int
    ) -> ChatSession:
        """ایجاد جلسه‌ی گفتگو جدید."""
        session = ChatSession(
            user_id=user_id,
            partner_id=partner_id,
            status="active",
            started_at=datetime.now(UTC),
        )
        return await self.add(session)

    async def end_session(
        self,
        session_id: int,
        *,
        ended_by: int,
        reason: str,
    ) -> ChatSession | None:
        """پایان دادن به جلسه‌ی گفتگو."""
        session = await self.get(session_id)
        if session is None:
            return None
        session.status = "ended"
        session.ended_at = datetime.now(UTC)
        session.end_reason = reason
        session.ended_by = ended_by
        await self.session.flush()
        return session

    async def increment_message_count(self, session_id: int) -> None:
        """افزایش شمارنده‌ی پیام گفتگو."""
        session = await self.get(session_id)
        if session is not None:
            session.message_count += 1
            await self.session.flush()

    async def get_active_count(self) -> int:
        """تعداد گفتگوهای فعال."""
        return await self.count(status="active")

    async def get_average_duration(self, hours: int = 24) -> float:
        """میانگین مدت گفتگوها در N ساعت گذشته (دقیقه)."""
        cutoff = datetime.now(UTC).timestamp() - hours * 3600
        cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)
        stmt = select(ChatSession).where(
            ChatSession.status == "ended",
            ChatSession.ended_at >= cutoff_dt,
        )
        result = await self.session.execute(stmt)
        sessions = result.scalars().all()
        if not sessions:
            return 0.0
        total = sum(s.duration_seconds for s in sessions)
        return total / len(sessions) / 60.0

    async def get_user_history(
        self, user_id: int, *, limit: int = 20, offset: int = 0
    ) -> list[ChatSession]:
        """تاریخچه‌ی گفتگوهای کاربر."""
        stmt = (
            select(ChatSession)
            .where(
                (ChatSession.user_id == user_id)
                | (ChatSession.partner_id == user_id)
            )
            .order_by(ChatSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_today(self) -> int:
        """تعداد گفتگوهای شروع‌شده امروز."""
        cutoff = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count()).select_from(ChatSession).where(
            ChatSession.started_at >= cutoff
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
