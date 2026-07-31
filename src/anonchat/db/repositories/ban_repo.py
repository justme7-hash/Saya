"""مخزن بن."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.ban import Ban


class BanRepository(BaseRepository[Ban]):
    """مخزن عملیات بن."""

    model = Ban

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_active_ban(self, user_id: int) -> Ban | None:
        """دریافت بن فعال یک کاربر (اگر وجود دارد)."""
        stmt = (
            select(Ban)
            .where(Ban.user_id == user_id, Ban.is_active.is_(True))
            .order_by(Ban.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        ban = result.scalar_one_or_none()
        if ban is not None and ban.is_expired:
            # اگر بن منقضی است، آن را غیرفعال و commit کنیم تا همه تراکنش‌ها وضعیت را ببینند
            ban.is_active = False
            await self.session.flush()
            await self.session.commit()
            return None
        return ban

    async def get_active_ban_by_telegram(self, telegram_id: int) -> Ban | None:
        """دریافت بن فعال بر اساس شناسه تلگرام کاربر."""
        from anonchat.models.user import User

        stmt = (
            select(Ban)
            .join(User, User.id == Ban.user_id)
            .where(User.telegram_id == telegram_id, Ban.is_active.is_(True))
            .order_by(Ban.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        ban = result.scalar_one_or_none()
        if ban is not None and ban.is_expired:
            # بن منقضی — غیرفعال کن و commit تا خواننده‌های بعدی آن را نبینند
            ban.is_active = False
            await self.session.flush()
            await self.session.commit()
            return None
        return ban

    async def ban_user(
        self,
        *,
        user_id: int,
        reason: str,
        banned_by: int | None = None,
        duration_hours: int | None = None,
        permanent: bool = False,
    ) -> Ban:
        """بن کردن کاربر.

        Args:
            user_id: شناسه کاربر.
            reason: دلیل بن.
            banned_by: شناسه مدیر (یا None برای خودکار).
            duration_hours: مدت بن موقت (اگر permanent=False).
            permanent: بن دائم.
        """
        banned_until = None
        if not permanent and duration_hours is not None:
            banned_until = datetime.now(UTC) + timedelta(hours=duration_hours)

        ban = Ban(
            user_id=user_id,
            is_permanent=permanent,
            banned_until=banned_until,
            reason=reason,
            banned_by=banned_by,
            is_active=True,
        )
        return await self.add(ban)

    async def unban_user(self, user_id: int, *, unbanned_by: int) -> bool:
        """لغو بن فعال کاربر."""
        ban = await self.get_active_ban(user_id)
        if ban is None:
            return False
        ban.is_active = False
        ban.unbanned_by = unbanned_by
        ban.unbanned_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.commit()
        return True

    async def get_user_bans(self, user_id: int) -> list[Ban]:
        """تاریخچه‌ی بن‌های کاربر."""
        stmt = (
            select(Ban)
            .where(Ban.user_id == user_id)
            .order_by(Ban.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_expired(self) -> int:
        """غیرفعال کردن بن‌های منقضی. برتعداد پاک‌شده برمی‌گرداند."""
        stmt = select(Ban).where(
            Ban.is_active.is_(True),
            Ban.is_permanent.is_(False),
        )
        result = await self.session.execute(stmt)
        count = 0
        for ban in result.scalars().all():
            if ban.is_expired:
                ban.is_active = False
                count += 1
        if count:
            await self.session.flush()
            await self.session.commit()
        return count
