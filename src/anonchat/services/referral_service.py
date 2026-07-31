"""سرویس رفرال و گیمیفیکیشن.

**نکته‌ی معماری:** تمام عملیات دیتابیس در ``async with container.session()``
انجام می‌شود تا نشست به‌درستی بسته شده و اتصال به pool برگردد.
این الگو از نشت اتصال (connection leak) جلوگیری می‌کند.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anonchat.core.config import get_settings
from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container


class ReferralService:
    """سرویس مدیریت دعوت‌ها و پاداش‌ها."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.referral")
        self._settings = get_settings()

    async def process_referral_reward(
        self, *, referrer_id: int, referred_id: int
    ) -> None:
        """پردازش پاداش دعوت وقتی کاربر دعوت‌شده ثبت‌نام را کامل می‌کند."""
        async with self._container.session() as session:
            referral_repo = self._container.referral_repo_with(session)
            user_repo = self._container.user_repo_with(session)

            # بررسی اینکه آیا رکورد رفرال وجود دارد
            referral = await referral_repo.get_by_referred(referred_id)
            if referral is None:
                # ایجاد رکورد اگر وجود ندارد
                referral = await referral_repo.create_referral(
                    referrer_id=referrer_id,
                    referred_id=referred_id,
                    reward_xp=self._settings.referral_reward_xp,
                )
            elif referral.reward_given:
                return  # قبلاً پاداش داده شده

            # اعطای XP به معرف
            await user_repo.add_xp(
                referrer_id, self._settings.referral_reward_xp
            )
            referral.reward_given = True
            referral.reward_xp = self._settings.referral_reward_xp
            await session.commit()

        self._log.info(
            "referral.rewarded",
            referrer=referrer_id,
            referred=referred_id,
            xp=self._settings.referral_reward_xp,
        )

    async def get_referral_stats(self, telegram_id: int) -> dict:
        """دریافت آمار رفرال کاربر."""
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            referral_repo = self._container.referral_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return {}
            count = await referral_repo.count_referrals(user.id)
            return {
                "referral_code": user.referral_code,
                "referral_link": f"https://t.me/SayaAnonBot?start={user.referral_code}",
                "total_referrals": count,
                "xp_earned": count * self._settings.referral_reward_xp,
            }

    async def claim_daily_reward(self, telegram_id: int) -> tuple[bool, int]:
        """دریافت پاداش روزانه ورود.

        Returns:
            تاپل (آیا دریافت شد؟, مقدار XP).
        """
        # بررسی اینکه آیا امروز گرفته شده
        async with self._container.session() as session:
            from sqlalchemy import select

            from anonchat.models.settings import Setting

            today_key = f"daily_reward_{telegram_id}_{self._today_key()}"
            stmt = select(Setting).where(Setting.key == today_key)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                return False, 0

            # ثبت دریافت
            setting = Setting(
                key=today_key,
                value="true",
                value_type="bool",
                description="پاداش روزانه",
            )
            session.add(setting)
            await session.commit()

        # اعطای XP
        await self._container.user_service.add_xp(
            telegram_id, self._settings.daily_login_xp
        )
        self._log.info(
            "referral.daily_reward",
            telegram_id=telegram_id,
            xp=self._settings.daily_login_xp,
        )
        return True, self._settings.daily_login_xp

    @staticmethod
    def _today_key() -> str:
        from datetime import UTC, datetime

        return datetime.now(UTC).strftime("%Y%m%d")
