"""مخزن کاربر."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from anonchat.db.repositories.base import BaseRepository
from anonchat.models.user import User


class UserRepository(BaseRepository[User]):
    """مخزن عملیات کاربر."""

    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """دریافت کاربر بر اساس شناسه تلگرام."""
        return await self.get_by(telegram_id=telegram_id)

    async def get_by_referral_code(self, code: str) -> User | None:
        """دریافت کاربر بر اساس کد رفرال."""
        return await self.get_by(referral_code=code)

    async def create_user(
        self,
        *,
        telegram_id: int,
        referral_code: str,
        language: str = "fa",
        referred_by_id: int | None = None,
    ) -> User:
        """ایجاد کاربر جدید (قبل از تکمیل ثبت‌نام)."""
        user = User(
            telegram_id=telegram_id,
            referral_code=referral_code,
            language=language,
            referred_by_id=referred_by_id,
        )
        return await self.add(user)

    async def complete_registration(
        self, user_id: int, **fields: Any
    ) -> User | None:
        """تکمیل ثبت‌نام با فیلدهای پروفایل."""
        fields["is_registered"] = True
        await self.session.execute(
            update(User).where(User.id == user_id).values(**fields)
        )
        await self.session.flush()
        return await self.get(user_id)

    async def set_online(self, user_id: int, online: bool) -> None:
        """تنظیم وضعیت آنلاین کاربر."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                is_online=online,
                last_seen=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def set_online_by_telegram(
        self, telegram_id: int, online: bool
    ) -> None:
        """تنظیم وضعیت آنلاین بر اساس شناسه تلگرام."""
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(
                is_online=online,
                last_seen=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def set_chat_state(self, user_id: int, in_chat: bool) -> None:
        """تنظیم وضعیت در-گفتگو."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_in_chat=in_chat, is_searching=False)
        )
        await self.session.flush()

    async def set_searching(self, user_id: int, searching: bool) -> None:
        """تنظیم وضعیت جستجوی مخاطب."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_searching=searching)
        )
        await self.session.flush()

    async def add_xp(self, user_id: int, amount: int) -> User | None:
        """افزودن امتیاز XP و محاسبه‌ی سطح."""
        user = await self.get(user_id)
        if user is None:
            return None
        user.xp += amount
        # فرمول سطح: هر ۱۰۰ امتیاز = یک سطح
        new_level = max(1, user.xp // 100 + 1)
        user.level = max(user.level, new_level)
        await self.session.flush()
        return user

    async def add_xp_by_telegram(self, telegram_id: int, amount: int) -> User | None:
        """افزودن XP بر اساس شناسه تلگرام."""
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return None
        user.xp += amount
        new_level = max(1, user.xp // 100 + 1)
        user.level = max(user.level, new_level)
        await self.session.flush()
        return user

    async def update_risk_score(self, user_id: int, score: int) -> None:
        """به‌روزرسانی امتیاز ریسک."""
        await self.session.execute(
            update(User).where(User.id == user_id).values(risk_score=score)
        )
        await self.session.flush()

    async def increment_warnings(self, user_id: int) -> int:
        """افزایش شمارنده‌ی هشدارها."""
        user = await self.get(user_id)
        if user is None:
            return 0
        user.warnings_count += 1
        await self.session.flush()
        return user.warnings_count

    async def increment_stats(
        self, user_id: int, *, chats: int = 0, sent: int = 0, received: int = 0
    ) -> None:
        """افزایش آمار کاربر."""
        user = await self.get(user_id)
        if user is None:
            return
        if chats:
            user.total_chats += chats
        if sent:
            user.total_messages_sent += sent
        if received:
            user.total_messages_received += received
        await self.session.flush()

    async def search_available_partners(
        self,
        *,
        exclude_ids: list[int],
        gender: str | None = None,
        country: str | None = None,
        language: str | None = None,
        age_min: int | None = None,
        age_max: int | None = None,
        limit: int = 50,
    ) -> list[User]:
        """جستجوی کاربران موجود برای اتصال.

        کاربران کاندید باید:
        - ثبت‌نام کرده باشند
        - بن نباشند
        - آنلاین و در حال جستجو باشند
        - در گفتگو نباشند
        - در لیست exclude نباشند
        """
        stmt = select(User).where(
            User.is_registered.is_(True),
            User.is_blocked.is_(False),
            User.is_online.is_(True),
            User.is_searching.is_(True),
            User.is_in_chat.is_(False),
            ~User.id.in_(exclude_ids) if exclude_ids else True,
        )
        if gender and gender != "any":
            stmt = stmt.where(User.gender == gender)
        if country:
            stmt = stmt.where(User.country == country)
        if language:
            stmt = stmt.where(User.language == language)
        if age_min is not None:
            stmt = stmt.where(User.age >= age_min)
        if age_max is not None:
            stmt = stmt.where(User.age <= age_max)
        # مرتب‌سازی بر اساس زمان انتظار (قدیمی‌ترین در صف اول)
        stmt = stmt.order_by(User.updated_at.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_registered(self) -> int:
        """تعداد کاربران ثبت‌نام‌شده."""
        return await self.count(is_registered=True)

    async def count_online(self) -> int:
        """تعداد کاربران آنلاین."""
        return await self.count(is_online=True)

    async def count_active_today(self) -> int:
        """تعداد کاربران فعال در ۲۴ ساعت گذشته."""
        cutoff = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = select(func.count()).select_from(User).where(
            User.last_seen >= cutoff, User.is_registered.is_(True)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_recent_partners(self, user_id: int, limit: int = 10) -> list[int]:
        """دریافت شناسه‌ی شرکای اخیر برای جلوگیری از اتصال مجدد."""
        from anonchat.models.chat import ChatSession

        stmt = (
            select(ChatSession.partner_id)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]
