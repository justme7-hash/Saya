"""سرویس Matchmaking — الگوریتم هوشمند اتصال کاربران.

این سرویس مسئول:
- مدیریت صف انتظار
- جستجوی مخاطب بر اساس معیارها
- جلوگیری از اتصال مجدد به شرکای اخیر
- توزیع عادلانه کاربران (اولویت به قدیمی‌ترین در صف)
- مچ‌سازی بر اساس علایق مشترک (امتیازدهی)

**نکته‌ی معماری:** تمام عملیات دیتابیس در ``async with container.session()``
انجام می‌شود تا نشست به‌درستی بسته شده و اتصال به pool برگردد.
این الگو از نشت اتصال (connection leak) جلوگیری می‌کند.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

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
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                raise UserNotFoundError(telegram_id)
            if user.is_in_chat:
                raise UserAlreadyInChatError(telegram_id)

            # علامت‌گذاری کاربر به‌عنوان در حال جستجو
            await user_repo.set_searching(user.id, True)
            # commit میانی تا کاربران دیگر در جستجوی همزمان او را ببینند
            await session.commit()

            # دریافت شرکای اخیر برای جلوگیری از اتصال مجدد
            recent = await user_repo.get_recent_partners(
                user.id, limit=self._settings.recent_partner_history
            )
            exclude_ids = [user.id, *recent]

            # جستجوی مخاطب مناسب در دیتابیس
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
                sess = await self._create_match(user.id, partner.id, session)
                # حذف شریک از صف اگر بود
                self._queue.pop(partner.telegram_id, None)
                return partner.telegram_id, sess.id

            # مچ فوری یافت نشد — بررسی صف انتظار درون‌حافظه‌ای
            # کاربرانی که قبلاً جستجو کردند و در صف مانده‌اند
            queued_match = await self._try_match_from_queue(
                user, exclude_ids, criteria, session
            )
            if queued_match is not None:
                partner_tg, sess = queued_match
                return partner_tg, sess.id

            # هنوز مچ نشد — وارد صف
            self._queue[telegram_id] = (criteria, datetime.now(UTC))
            self._log.info(
                "matchmaking.queued",
                telegram_id=telegram_id,
                queue_size=len(self._queue),
            )
            return None, None

    async def _try_match_from_queue(
        self, user, exclude_ids: list[int], criteria: SearchCriteriaDTO, session
    ) -> tuple[int, object] | None:
        """تلاش برای مچ کردن با کاربران در صف انتظار.

        کاربران در صف ممکن است در دیتابیس is_searching=True داشته باشند
        ولی به‌خاطر race condition در جستجوی قبلی پیدا نشده باشند.
        """
        if not self._queue:
            return None

        user_repo = self._container.user_repo_with(session)

        # بررسی تک‌تک کاربران در صف (به ترتیب قدیمی‌ترین اول)
        sorted_queue = sorted(self._queue.items(), key=lambda x: x[1][1])
        for partner_tg_id, (partner_criteria, _) in sorted_queue:
            if partner_tg_id == user.telegram_id:
                continue
            if partner_tg_id in exclude_ids:
                continue

            # دریافت کاربر شریک از دیتابیس
            partner = await user_repo.get_by_telegram_id(partner_tg_id)
            if partner is None or partner.is_in_chat or not partner.is_searching:
                # کاربر دیگر در صف نیست یا در گفتگو است — پاک کن
                self._queue.pop(partner_tg_id, None)
                continue

            # اگر شریک hide_from_search=True دارد، در نتایج نشان داده نمی‌شود
            if getattr(partner, "hide_from_search", False):
                continue

            # بررسی تطابق معیارها (دوطرفه)
            if not self._criteria_match(criteria, partner_criteria, user, partner):
                continue

            # مچ شد!
            self._queue.pop(partner_tg_id, None)
            sess = await self._create_match(user.id, partner.id, session)
            return partner_tg_id, sess

        return None

    @staticmethod
    def _criteria_match(
        my_criteria: SearchCriteriaDTO,
        partner_criteria: SearchCriteriaDTO,
        me,
        partner,
    ) -> bool:
        """بررسی اینکه آیا معیارهای دو کاربر با هم سازگار است."""
        # معیار جنسیت من روی شریک
        if my_criteria.gender and my_criteria.gender != "any":
            if partner.gender != my_criteria.gender:
                return False
        # معیار جنسیت شریک روی من
        if partner_criteria.gender and partner_criteria.gender != "any":
            if me.gender != partner_criteria.gender:
                return False
        # معیار کشور من
        if my_criteria.country and partner.country != my_criteria.country:
            return False
        # معیار کشور شریک
        if partner_criteria.country and me.country != partner_criteria.country:
            return False
        # معیار زبان من
        if my_criteria.language and partner.language != my_criteria.language:
            return False
        # معیار زبان شریک
        if partner_criteria.language and me.language != partner_criteria.language:
            return False
        # معیار سن من
        if my_criteria.age_min and partner.age and partner.age < my_criteria.age_min:
            return False
        if my_criteria.age_max and partner.age and partner.age > my_criteria.age_max:
            return False
        # معیار سن شریک
        if partner_criteria.age_min and me.age and me.age < partner_criteria.age_min:
            return False
        if partner_criteria.age_max and me.age and me.age > partner_criteria.age_max:
            return False
        return True

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
            # با try/except چون updated_at ممکن است در دیتابیس قدیمی NULL یا نامعتبر باشد
            try:
                updated = candidate.updated_at
                if updated is not None:
                    if updated.tzinfo is None:
                        updated = updated.replace(tzinfo=UTC)
                    age_minutes = (datetime.now(UTC) - updated).total_seconds() / 60
                    score += min(int(age_minutes), 10)
            except Exception:
                # اگر خطا در محاسبه زمان، صرفاً امتیاز زمان را نادیده بگیر
                pass
            scored.append((score, candidate))

        # انتخاب بالاترین امتیاز
        if not scored:
            # اگر هیچ امتیازی محاسبه نشد (نباید رخ دهد ولی برای امنیت)
            return candidates[0] if candidates else None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    async def _create_match(
        self, user_id: int, partner_id: int, session: AsyncSession
    ):
        """ایجاد جلسه‌ی گفتگو و به‌روزرسانی وضعیت کاربران.

        نشست باید توسط فراخواننده (``start_search``) تأمین شود تا
        عملیات در یک تراکنش اتمیک انجام شود.
        """
        chat_repo = self._container.chat_repo_with(session)
        user_repo = self._container.user_repo_with(session)

        sess = await chat_repo.create_session(
            user_id=user_id, partner_id=partner_id
        )
        await user_repo.set_chat_state(user_id, True)
        await user_repo.set_chat_state(partner_id, True)
        await user_repo.increment_stats(user_id, chats=1)
        await user_repo.increment_stats(partner_id, chats=1)
        await session.commit()
        self._log.info(
            "matchmaking.matched",
            user=user_id,
            partner=partner_id,
            session=sess.id,
        )
        return sess

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
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is not None:
                await user_repo.set_searching(user.id, False)
                await session.commit()
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
