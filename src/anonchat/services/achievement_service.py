"""سرویس دستاوردها — سیستم گیمیفیکیشن.

**نکته‌ی معماری:** تمام عملیات دیتابیس در ``async with container.session()``
انجام می‌شود تا نشست به‌درستی بسته شده و اتصال به pool برگردد.
این الگو از نشت اتصال (connection leak) جلوگیری می‌کند.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container


# کاتالوگ دستاوردهای پیش‌فرض
DEFAULT_ACHIEVEMENTS = [
    {
        "code": "first_chat",
        "name": "اولین گفتگو",
        "description": "اولین گفتگوی ناشناس خود را تجربه کن",
        "icon": "💬",
        "xp_reward": 20,
        "category": "chat",
    },
    {
        "code": "chat_master",
        "name": "استاد گفتگو",
        "description": "۱۰ گفتگو کامل انجام بده",
        "icon": "🗣️",
        "xp_reward": 100,
        "category": "chat",
    },
    {
        "code": "social_butterfly",
        "name": "ماه اجتماعی",
        "description": "۵۰ گفتگو انجام بده",
        "icon": "🦋",
        "xp_reward": 300,
        "category": "chat",
    },
    {
        "code": "referral_starter",
        "name": "دعوت‌کننده",
        "description": "اولین دوست خود را دعوت کن",
        "icon": "👥",
        "xp_reward": 50,
        "category": "social",
    },
    {
        "code": "influencer",
        "name": "تأثیرگذار",
        "description": "۱۰ دوست دعوت کن",
        "icon": "⭐",
        "xp_reward": 200,
        "category": "social",
    },
    {
        "code": "level_5",
        "name": "صعودکننده",
        "description": "به سطح ۵ برس",
        "icon": "📈",
        "xp_reward": 50,
        "category": "level",
    },
    {
        "code": "level_10",
        "name": "حرفه‌ای",
        "description": "به سطح ۱۰ برس",
        "icon": "🏆",
        "xp_reward": 150,
        "category": "level",
    },
    {
        "code": "veteran",
        "name": "کهنه‌کار",
        "description": "۷ روز از عضویتت بگذرد",
        "icon": "🎖️",
        "xp_reward": 80,
        "category": "account",
    },
]


class AchievementService:
    """سرویس مدیریت دستاوردها."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.achievement")

    async def seed_default_achievements(self) -> None:
        """ایجاد دستاوردهای پیش‌فرض در دیتابیس (در زمان راه‌اندازی)."""
        from sqlalchemy import select

        from anonchat.models.achievement import Achievement

        async with self._container.session() as session:
            stmt = select(Achievement).limit(1)
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is not None:
                return  # قبلاً ایجاد شده

            for ach in DEFAULT_ACHIEVEMENTS:
                session.add(Achievement(**ach))
            await session.commit()
        self._log.info("achievement.seeded", count=len(DEFAULT_ACHIEVEMENTS))

    async def check_and_award(self, telegram_id: int) -> list[dict]:
        """بررسی و اعطای دستاوردهای جدید به کاربر.

        Returns:
            لیست دستاوردهای جدید کسب‌شده.
        """
        from sqlalchemy import select

        from anonchat.models.achievement import Achievement, UserAchievement

        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return []

            # دریافت تمام دستاوردها
            stmt = select(Achievement)
            result = await session.execute(stmt)
            all_achievements = result.scalars().all()

            # دریافت دستاوردهای کسب‌شده کاربر
            earned_stmt = select(UserAchievement.achievement_id).where(
                UserAchievement.user_id == user.id
            )
            earned_result = await session.execute(earned_stmt)
            earned_ids = {row[0] for row in earned_result.all()}

            new_achievements: list[dict] = []
            for ach in all_achievements:
                if ach.id in earned_ids:
                    continue
                if await self._meets_criteria(user, ach, session):
                    # اعطای دستاورد
                    ua = UserAchievement(
                        user_id=user.id,
                        achievement_id=ach.id,
                        earned_at=datetime.now(UTC),
                    )
                    session.add(ua)
                    new_achievements.append(
                        {
                            "code": ach.code,
                            "name": ach.name,
                            "icon": ach.icon,
                            "xp_reward": ach.xp_reward,
                        }
                    )
                    # اعطای XP
                    user.xp += ach.xp_reward
                    new_level = max(1, user.xp // 100 + 1)
                    user.level = max(user.level, new_level)

            if new_achievements:
                await session.commit()
                self._log.info(
                    "achievement.awarded",
                    telegram_id=telegram_id,
                    count=len(new_achievements),
                )
            return new_achievements

    async def _meets_criteria(
        self, user, achievement, session: AsyncSession
    ) -> bool:
        """بررسی اینکه آیا کاربر معیار دستاورد را برآورده کرده."""
        code = achievement.code
        if code == "first_chat":
            return user.total_chats >= 1
        if code == "chat_master":
            return user.total_chats >= 10
        if code == "social_butterfly":
            return user.total_chats >= 50
        if code == "level_5":
            return user.level >= 5
        if code == "level_10":
            return user.level >= 10
        if code == "veteran":
            created = user.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            age_days = (datetime.now(UTC) - created).days
            return age_days >= 7
        if code in ("referral_starter", "influencer"):
            referral_repo = self._container.referral_repo_with(session)
            count = await referral_repo.count_referrals(user.id)
            if code == "referral_starter":
                return count >= 1
            return count >= 10
        return False

    async def get_user_achievements(self, telegram_id: int) -> list[dict]:
        """دریافت لیست دستاوردهای کاربر."""
        from sqlalchemy import select

        from anonchat.models.achievement import Achievement, UserAchievement

        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return []

            stmt = (
                select(Achievement, UserAchievement)
                .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
                .where(UserAchievement.user_id == user.id)
                .order_by(UserAchievement.earned_at.desc())
            )
            result = await session.execute(stmt)
            return [
                {
                    "code": ach.code,
                    "name": ach.name,
                    "icon": ach.icon,
                    "description": ach.description,
                    "xp_reward": ach.xp_reward,
                    "earned_at": ua.earned_at.isoformat() if ua.earned_at else None,
                }
                for ach, ua in result.all()
            ]
