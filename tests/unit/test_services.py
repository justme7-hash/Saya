"""تست سرویس‌ها."""

from __future__ import annotations

import pytest

from anonchat.core.security import generate_referral_code
from anonchat.schemas.user import RegistrationDTO


@pytest.mark.unit
class TestUserService:
    """تست سرویس کاربر."""

    async def test_get_or_create_new_user(self, db_manager) -> None:
        service = db_manager.user_service
        user, created = await service.get_or_create(888888)
        assert created is True
        assert user.telegram_id == 888888
        assert user.referral_code.startswith("SAYA-")

        # دریافت مجدد — نباید ایجاد شود
        user2, created2 = await service.get_or_create(888888)
        assert created2 is False
        assert user2.telegram_id == 888888

    async def test_complete_registration(self, db_manager) -> None:
        service = db_manager.user_service
        await service.get_or_create(777777)

        dto = RegistrationDTO(
            nickname="کاربر تست",
            gender="female",
            age=22,
            country="IR",
            language="fa",
            bio="بیو",
            interests=["موسیقی", "ورزش"],
        )
        user = await service.complete_registration(777777, dto)
        assert user.is_registered is True
        assert user.nickname == "کاربر تست"
        assert user.age == 22
        assert "موسیقی" in (user.interests or "")

    async def test_add_xp(self, db_manager, sample_user) -> None:
        service = db_manager.user_service
        level = await service.add_xp(sample_user.telegram_id, 50)
        assert level == 1  # 50 XP -> level 1

        level = await service.add_xp(sample_user.telegram_id, 60)
        assert level == 2  # 110 XP -> level 2


@pytest.mark.unit
class TestMatchmakingService:
    """تست سرویس matchmaking."""

    async def test_search_no_partner(self, db_manager) -> None:
        from anonchat.schemas.chat import SearchCriteriaDTO

        service = db_manager.user_service
        match_service = db_manager.matchmaking_service

        # ایجاد کاربر ثبت‌نام‌شده
        await service.get_or_create(555555)
        dto = RegistrationDTO(
            nickname="تست", gender="male", age=20, country="IR", language="fa"
        )
        await service.complete_registration(555555, dto)

        # جستجو — نباید مخاطبی پیدا شود
        partner_tg, session_id = await match_service.start_search(
            555555, SearchCriteriaDTO()
        )
        assert partner_tg is None
        assert session_id is None

    async def test_cancel_search(self, db_manager) -> None:
        service = db_manager.matchmaking_service
        # lgoon به‌صورت دستی به صف اضافه کن
        service._queue[12345] = (None, None)  # type: ignore[arg-type]
        result = await service.cancel_search(12345)
        assert result is True
        assert 12345 not in service._queue


@pytest.mark.unit
class TestReferralService:
    """تست سرویس رفرال."""

    async def test_referral_stats(self, db_manager, sample_user) -> None:
        service = db_manager.referral_service
        stats = await service.get_referral_stats(sample_user.telegram_id)
        assert stats["referral_code"] == sample_user.referral_code
        assert "referral_link" in stats
        assert stats["total_referrals"] == 0
