"""تست مخازن — بررسی عملیات CRUD."""

from __future__ import annotations

import pytest

from anonchat.core.security import generate_referral_code


@pytest.mark.unit
class TestUserRepository:
    """تست مخزن کاربر."""

    async def test_create_and_get_user(self, db_manager) -> None:
        repo = db_manager.user_repo()
        user = await repo.create_user(
            telegram_id=999999,
            referral_code=generate_referral_code(999999),
        )
        await repo.commit()

        fetched = await repo.get_by_telegram_id(999999)
        assert fetched is not None
        assert fetched.telegram_id == 999999
        assert fetched.is_registered is False

    async def test_complete_registration(self, db_manager, sample_user) -> None:
        repo = db_manager.user_repo()
        updated = await repo.complete_registration(
            sample_user.id,
            nickname="تست کاربر",
            gender="male",
            age=25,
            country="IR",
            language="fa",
            bio="بیو تست",
            interests="موسیقی,ورزش",
        )
        await repo.commit()
        assert updated is not None
        assert updated.is_registered is True
        assert updated.nickname == "تست کاربر"
        assert updated.age == 25

    async def test_add_xp_and_level(self, db_manager, sample_user) -> None:
        repo = db_manager.user_repo()
        user = await repo.add_xp(sample_user.id, 150)
        await repo.commit()
        assert user is not None
        assert user.xp == 150
        assert user.level == 2  # 150 // 100 + 1 = 2

    async def test_set_online_by_telegram(self, db_manager, sample_user) -> None:
        repo = db_manager.user_repo()
        await repo.set_online_by_telegram(sample_user.telegram_id, True)
        await repo.commit()
        user = await repo.get_by_telegram_id(sample_user.telegram_id)
        assert user is not None
        assert user.is_online is True

    async def test_get_recent_partners_empty(self, db_manager, sample_user) -> None:
        repo = db_manager.user_repo()
        partners = await repo.get_recent_partners(sample_user.id)
        assert partners == []


@pytest.mark.unit
class TestBanRepository:
    """تست مخزن بن."""

    async def test_ban_and_get(self, db_manager, sample_user) -> None:
        repo = db_manager.ban_repo()
        await repo.ban_user(
            user_id=sample_user.id,
            reason="تست بن",
            duration_hours=24,
        )
        await repo.commit()

        ban = await repo.get_active_ban(sample_user.id)
        assert ban is not None
        assert ban.is_active is True
        assert ban.is_permanent is False
        assert ban.reason == "تست بن"

    async def test_unban(self, db_manager, sample_user) -> None:
        repo = db_manager.ban_repo()
        await repo.ban_user(
            user_id=sample_user.id, reason="تست", duration_hours=1
        )
        await repo.commit()

        result = await repo.unban_user(sample_user.id, unbanned_by=1)
        await repo.commit()
        assert result is True

        ban = await repo.get_active_ban(sample_user.id)
        assert ban is None

    async def test_permanent_ban(self, db_manager, sample_user) -> None:
        repo = db_manager.ban_repo()
        await repo.ban_user(
            user_id=sample_user.id, reason="بن دائم", permanent=True
        )
        await repo.commit()
        ban = await repo.get_active_ban(sample_user.id)
        assert ban is not None
        assert ban.is_permanent is True


@pytest.mark.unit
class TestChatRepository:
    """تست مخزن گفتگو."""

    async def test_create_and_get_active(self, db_manager) -> None:
        from anonchat.core.security import generate_referral_code

        user_repo = db_manager.user_repo()
        user1 = await user_repo.create_user(
            telegram_id=111, referral_code=generate_referral_code(111)
        )
        user2 = await user_repo.create_user(
            telegram_id=222, referral_code=generate_referral_code(222)
        )
        await user_repo.commit()

        chat_repo = db_manager.chat_repo()
        session = await chat_repo.create_session(
            user_id=user1.id, partner_id=user2.id
        )
        await chat_repo.commit()

        active = await chat_repo.get_active_for_user(user1.id)
        assert active is not None
        assert active.status == "active"

    async def test_end_session(self, db_manager) -> None:
        from anonchat.core.security import generate_referral_code

        user_repo = db_manager.user_repo()
        user1 = await user_repo.create_user(
            telegram_id=333, referral_code=generate_referral_code(333)
        )
        user2 = await user_repo.create_user(
            telegram_id=444, referral_code=generate_referral_code(444)
        )
        await user_repo.commit()

        chat_repo = db_manager.chat_repo()
        session = await chat_repo.create_session(
            user_id=user1.id, partner_id=user2.id
        )
        await chat_repo.commit()

        ended = await chat_repo.end_session(
            session.id, ended_by=user1.id, reason="test"
        )
        await chat_repo.commit()
        assert ended is not None
        assert ended.status == "ended"
        assert ended.end_reason == "test"
