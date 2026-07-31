"""سرویس گفتگو — مدیریت چرخه‌ی حیات جلسات گفتگو."""

from __future__ import annotations

from typing import TYPE_CHECKING

from anonchat.core.exceptions import (
    UserNotFoundError,
    UserNotInChatError,
)
from anonchat.core.logging import get_logger
from anonchat.core.security import utcnow

if TYPE_CHECKING:
    from anonchat.core.container import Container


class ChatService:
    """سرویس مدیریت جلسات گفتگو."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.chat")

    async def get_active_partner(self, telegram_id: int) -> tuple[int, int, int]:
        """دریافت شناسه‌ی شریک گفتگوی فعال.

        Returns:
            تاپل (chat_session_id, partner_user_id, partner_telegram_id).
        """
        user_repo = self._container.user_repo()
        chat_repo = self._container.chat_repo()

        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)

        session = await chat_repo.get_active_for_user(user.id)
        if session is None:
            raise UserNotInChatError(telegram_id)

        partner_id = (
            session.partner_id if session.user_id == user.id else session.user_id
        )
        partner = await user_repo.get(partner_id)
        if partner is None:
            raise UserNotInChatError(telegram_id)

        return session.id, partner_id, partner.telegram_id

    async def end_chat(
        self,
        telegram_id: int,
        *,
        reason: str = "user_left",
    ) -> tuple[int, int, int] | None:
        """پایان دادن به گفتگوی فعال.

        Returns:
            تاپل (ended_session_id, partner_user_id, partner_telegram_id)
            یا None اگر گفتگویی نباشد.
        """
        user_repo = self._container.user_repo()
        chat_repo = self._container.chat_repo()

        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)

        session = await chat_repo.get_active_for_user(user.id)
        if session is None:
            return None

        partner_id = (
            session.partner_id if session.user_id == user.id else session.user_id
        )
        partner = await user_repo.get(partner_id)

        await chat_repo.end_session(session.id, ended_by=user.id, reason=reason)
        await user_repo.set_chat_state(user.id, False)
        if partner is not None:
            await user_repo.set_chat_state(partner_id, False)

        await chat_repo.commit()
        self._log.info(
            "chat.ended",
            session=session.id,
            by=user.id,
            partner=partner_id,
            reason=reason,
        )
        return (session.id, partner_id, partner.telegram_id if partner else 0)

    async def end_chat_for_partner(self, partner_telegram_id: int) -> int | None:
        """پایان گفتگو از سمت شریک (وقتی شریک قطع می‌کند).

        Returns:
            شناسه‌ی تلگرام کاربری که باید مطلع شود، یا None.
        """
        user_repo = self._container.user_repo()
        chat_repo = self._container.chat_repo()

        user = await user_repo.get_by_telegram_id(partner_telegram_id)
        if user is None:
            return None

        session = await chat_repo.get_active_for_user(user.id)
        if session is None:
            return None

        other_id = (
            session.partner_id if session.user_id == user.id else session.user_id
        )
        other = await user_repo.get(other_id)

        await chat_repo.end_session(
            session.id, ended_by=user.id, reason="partner_left"
        )
        await user_repo.set_chat_state(user.id, False)
        if other is not None:
            await user_repo.set_chat_state(other_id, False)

        await chat_repo.commit()
        return other.telegram_id if other else None

    async def rate_chat(
        self, telegram_id: int, session_id: int, rating: int, favorite: bool = False
    ) -> None:
        """امتیاز دادن به گفتگو و optionally افزودن به محبوب‌ها."""
        user_repo = self._container.user_repo()
        chat_repo = self._container.chat_repo()

        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)

        session = await chat_repo.get(session_id)
        if session is None:
            return

        if rating:
            session.rating = rating
        await chat_repo.commit()

        if favorite:
            partner_id = (
                session.partner_id if session.user_id == user.id else session.user_id
            )
            fav_repo = self._container.favorite_repo()
            existing = await fav_repo.is_favorite(user.id, partner_id)
            if not existing:
                await fav_repo.add_favorite(
                    user_id=user.id, favorite_user_id=partner_id
                )
                await fav_repo.commit()

        # پاداش XP برای امتیازدهن
        await self._container.user_service.add_xp(telegram_id, 5)

    async def get_history(self, telegram_id: int, limit: int = 10) -> list:
        """دریافت تاریخچه‌ی گفتگوهای کاربر."""
        user_repo = self._container.user_repo()
        chat_repo = self._container.chat_repo()
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        return await chat_repo.get_user_history(user.id, limit=limit)

    async def is_in_chat(self, telegram_id: int) -> bool:
        """بررسی اینکه آیا کاربر در گفتگوی فعالی است."""
        user_repo = self._container.user_repo()
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            return False
        return user.is_in_chat

    async def check_idle_chats(self, timeout_minutes: int) -> list[tuple[int, int]]:
        """بررسی گفتگوهای بی‌تحرک برای پایان خودکار.

        Returns:
            لیست تاپل‌های (session_id, idle_user_telegram_id).
        """
        chat_repo = self._container.chat_repo()

        sessions = await chat_repo.get_many(
            filters={"status": "active"},
            limit=500,
        )
        result: list[tuple[int, int]] = []
        cutoff = utcnow().timestamp() - timeout_minutes * 60
        for session in sessions:
            # این یک بررسی ساده است؛ در نسخه کامل باید آخرین پیام را چک کند
            if session.started_at.timestamp() < cutoff and session.message_count == 0:
                result.append((session.id, 0))
        return result
