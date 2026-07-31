"""سرویس Matchmaking — الگوریتم هوشمند اتصال کاربران.

این سرویس مسئول:
- مدیریت صف انتظار
- جستجوی مخاطب بر اساس معیارها
- جلوگیری از اتصال مجدد به شرکای اخیر
- توزیع عادلانه کاربران (اولویت به قدیمی‌ترین در صف)
- مچ‌سازی بر اساس علایق مشترک (امتیازدهی)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from anonchat.core.config import get_settings
from anonchat.core.exceptions import (
    NoAvailablePartnerError,
    UserAlreadyInChatError,
    UserNotFoundError,
)
from anonchat.core.logging import get_logger
from anonchat.schemas.chat import SearchCriteriaDTO

if TYPE_CHECKING:
    from anonchat.core.container import Container


class MatchmakingService:
    """سرویس جستجو و اتصال مخاطب."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.matchmaking")
        self._settings = get_settings()
        # صف انتظار درون‌حافظه‌ای: telegram_id -> (criteria, joined_at)
        self._queue: dict[int, tuple[SearchCriteriaDTO, datetime]] = {}

    async def start_search(
        self, telegram_id: int, criteria: SearchCriteriaDTO
    ) -> tuple[int | None, int | None]:
        """شروع جستجوی مخاطب.

        Returns:
            تاپل (partner_telegram_id, chat_session_id).
            اگر مچ فوری یافت شود، مقادیر پر شده‌اند؛ در غیر این‌صورت (None, None)
            و کاربر وارد صف می‌شود.
        """
        user_repo = self._container.user_repo()
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        if user.is_in_chat:
            raise UserAlreadyInChatError(telegram_id)

        # علامت‌گذاری کاربر به‌عنوان در حال جستجو
        await user_repo.set_searching(user.id, True)
        await user_repo.commit()

        # دریافت شرکای اخیر برای جلوگیری از اتصال مجدد
        recent = await user_repo.get_recent_partners(
            user.id, limit=self._settings.recent_partner_history
        )
        exclude_ids = [user.id, *recent]

        # جستجوی مخاطب مناسب
        candidates = await user_repo.search_available_partners(
            exclude_ids=exclude_ids,
            gender=criteria.gender if criteria.gender != "any" else None,
            country=criteria.country,
            language=criteria.language,
            age_min=criteria.age_min,
            age_max=criteria.age_max,
            limit=50,
        )

        if candidates:
            # انتخاب بهترین کاندید با امتیازدهی
            partner = self._select_best_candidate(user, candidates, criteria)
            session = await self._create_match(user.id, partner.id)
            return partner.telegram_id, session.id

        # مچ فوری یافت نشد — وارد صف
        self._queue[telegram_id] = (criteria, datetime.now(UTC))
        self._log.info(
            "matchmaking.queued",
            telegram_id=telegram_id,
            queue_size=len(self._queue),
        )
        return None, None

    def _select_best_candidate(
        self, user, candidates: list, criteria: SearchCriteriaDTO
    ):
        """انتخاب بهترین کاندید با الگوریتم امتیازدهی.

        فاکتورها:
        - علایق مشترک (وزن بالا)
        - هم‌کشوری (وزن متوسط)
        - هم‌زبانی (وزن پایین)
        - زمان انتظار در صف (قدیمی‌ترین برتری)
        """
        user_interests = set(
            i.strip() for i in (user.interests or "").split(",") if i.strip()
        )
        scored: list[tuple[int, object]] = []
        for candidate in candidates:
            score = 0
            # علایق مشترک
            cand_interests = set(
                i.strip() for i in (candidate.interests or "").split(",") if i.strip()
            )
            common = user_interests & cand_interests
            score += len(common) * 10
            # هم‌کشوری
            if user.country and candidate.country == user.country:
                score += 5
            # هم‌زبانی
            if candidate.language == user.language:
                score += 3
            # زمان انتظار (قدیمی‌تر = امتیاز بیشتر)
            age_minutes = (
                datetime.now(UTC) - candidate.updated_at.replace(tzinfo=UTC)
                if candidate.updated_at.tzinfo is None
                else datetime.now(UTC) - candidate.updated_at
            ).total_seconds() / 60
            score += min(int(age_minutes), 10)
            scored.append((score, candidate))

        # انتخاب بالاترین امتیاز
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else candidates[0]

    async def _create_match(self, user_id: int, partner_id: int):
        """ایجاد جلسه‌ی گفتگو و به‌روزرسانی وضعیت کاربران."""
        chat_repo = self._container.chat_repo()
        user_repo = self._container.user_repo()

        session = await chat_repo.create_session(
            user_id=user_id, partner_id=partner_id
        )
        await user_repo.set_chat_state(user_id, True)
        await user_repo.set_chat_state(partner_id, True)
        await user_repo.increment_stats(user_id, chats=1)
        await user_repo.increment_stats(partner_id, chats=1)
        await chat_repo.commit()
        self._log.info(
            "matchmaking.matched",
            user=user_id,
            partner=partner_id,
            session=session.id,
        )
        return session

    async def try_match_queued(self, telegram_id: int) -> tuple[int | None, int | None]:
        """تلاش برای مچ کردن یک کاربر که در صف است.

        زمانی فراخوانی می‌شود که کاربر جدیدی وارد صف شود یا کاربری جستجو را شروع کند.
        """
        if telegram_id not in self._queue:
            return None, None
        criteria, _ = self._queue[telegram_id]
        # حذف موقت از صف برای جستجو
        del self._queue[telegram_id]
        try:
            return await self.start_search(telegram_id, criteria)
        except (NoAvailablePartnerError, UserAlreadyInChatError):
            # بازگرداندن به صف
            self._queue[telegram_id] = (criteria, datetime.now(UTC))
            return None, None

    async def cancel_search(self, telegram_id: int) -> bool:
        """لغو جستجوی کاربر و خروج از صف."""
        removed = self._queue.pop(telegram_id, None) is not None
        user_repo = self._container.user_repo()
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is not None:
            await user_repo.set_searching(user.id, False)
            await user_repo.commit()
        if removed:
            self._log.info("matchmaking.cancelled", telegram_id=telegram_id)
        return removed

    def get_queue_size(self) -> int:
        """تعداد کاربران در صف انتظار."""
        return len(self._queue)

    async def cleanup_stale_queue(self, timeout_seconds: int | None = None) -> int:
        """پاک کردن کاربران قدیمی از صف.

        Returns:
            تعداد کاربران حذف‌شده.
        """
        timeout = timeout_seconds or self._settings.match_queue_timeout
        now = datetime.now(UTC)
        stale = [
            tid
            for tid, (_, joined) in self._queue.items()
            if (now - joined).total_seconds() > timeout
        ]
        for tid in stale:
            await self.cancel_search(tid)
        if stale:
            self._log.info("matchmaking.queue_cleaned", removed=len(stale))
        return len(stale)
