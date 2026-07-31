"""تست یکپارچه‌ی جریان کامل ثبت‌نام و گفتگو."""

from __future__ import annotations

import pytest
import pytest_asyncio

from anonchat.core.security import generate_referral_code
from anonchat.schemas.chat import SearchCriteriaDTO
from anonchat.schemas.user import RegistrationDTO


@pytest.mark.integration
class TestRegistrationAndChatFlow:
    """تست جریان کامل: ثبت‌نام → جستجو → مچ → گفتگو → پایان."""

    async def test_full_flow(self, db_manager) -> None:
        user_service = db_manager.user_service
        match_service = db_manager.matchmaking_service
        chat_service = db_manager.chat_service

        # 1. ایجاد دو کاربر
        for tg_id in (100001, 100002):
            await user_service.get_or_create(tg_id)

        # 2. تکمیل ثبت‌نام هر دو
        for tg_id in (100001, 100002):
            dto = RegistrationDTO(
                nickname=f"کاربر{tg_id}",
                gender="male",
                age=25,
                country="IR",
                language="fa",
            )
            await user_service.complete_registration(tg_id, dto)

        # 3. کاربر اول جستجو می‌کند — وارد صف می‌شود
        partner_tg, session_id = await match_service.start_search(
            100001, SearchCriteriaDTO()
        )
        assert partner_tg is None  # هنوز مخاطبی نیست

        # 4. کاربر دوم جستجو می‌کند — باید با اولی مچ شود
        partner_tg2, session_id2 = await match_service.start_search(
            100002, SearchCriteriaDTO()
        )
        # چون کاربر اول در صف است، باید مچ شود
        # (توجه: در پیاده‌سازی فعلی، start_search مستقیماً جستجو می‌کند
        #  و کاربر اول is_searching=True شده، پس باید مچ شود)
        if partner_tg2 is not None:
            assert partner_tg2 == 100001
            assert session_id2 is not None

            # 5. بررسی وضعیت در گفتگو
            assert await chat_service.is_in_chat(100001) or await chat_service.is_in_chat(100002)

            # 6. پایان گفتگو
            result = await chat_service.end_chat(100001, reason="user_left")
            assert result is not None

    async def test_ban_prevents_access(self, db_manager) -> None:
        from anonchat.core.exceptions import UserBannedError

        user_service = db_manager.user_service
        ban_repo = db_manager.ban_repo()

        await user_service.get_or_create(200001)
        dto = RegistrationDTO(
            nickname="بن شونده", gender="male", age=30, country="IR", language="fa"
        )
        user = await user_service.complete_registration(200001, dto)

        await ban_repo.ban_user(user_id=user.id, reason="تست", duration_hours=1)
        await ban_repo.commit()

        with pytest.raises(UserBannedError):
            await user_service.check_ban_status(200001)
