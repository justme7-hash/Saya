"""مخزن رفرال."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.referral import Referral


class ReferralRepository(BaseRepository[Referral]):
    """مخزن دعوت‌ها."""

    model = Referral

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_referral(
        self, *, referrer_id: int, referred_id: int, reward_xp: int = 0
    ) -> Referral:
        """ثبت دعوت جدید."""
        referral = Referral(
            referrer_id=referrer_id,
            referred_id=referred_id,
            reward_xp=reward_xp,
            reward_given=reward_xp == 0,
        )
        return await self.add(referral)

    async def get_by_referred(self, referred_id: int) -> Referral | None:
        """دریافت رکورد رفرال بر اساس کاربر دعوت‌شده."""
        return await self.get_by(referred_id=referred_id)

    async def mark_rewarded(self, referral_id: int) -> None:
        """علامت‌گذاری رفرال به‌عنوان پاداش‌داده‌شده."""
        referral = await self.get(referral_id)
        if referral is not None:
            referral.reward_given = True
            await self.session.flush()

    async def count_referrals(self, referrer_id: int) -> int:
        """تعداد دعوت‌های موفق یک کاربر."""
        return await self.count(referrer_id=referrer_id)

    async def get_pending_rewards(self, referrer_id: int) -> list[Referral]:
        """دریافت رفرال‌هایی که پاداش نداده‌ایم."""
        stmt = (
            select(Referral)
            .where(
                Referral.referrer_id == referrer_id,
                Referral.reward_given.is_(False),
            )
            .order_by(Referral.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
