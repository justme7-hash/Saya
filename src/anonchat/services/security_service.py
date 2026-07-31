"""سرویس امنیت — ضد اسپم، Rate Limiting، تشخیص Flood، مدیریت گزارش‌ها.

این سرویس از ترکیب کش درون‌حافظه‌ای (برای سرعت) و دیتابیس
(برای ماندگاری) استفاده می‌کند.

الگوریتم‌ها:
- Rate Limiting: Token Bucket / Sliding Window
- Flood Detection: تشخیص پیام‌های تکراری پشت سر هم
- Risk Scoring: ترکیب فاکتورهای متعدد

**نکته‌ی معماری:** تمام عملیات دیتابیس در ``async with container.session()``
انجام می‌شود تا نشست به‌درستی بسته شده و اتصال به pool برگردد.
این الگو از نشت اتصال (connection leak) جلوگیری می‌کند.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from anonchat.core.config import get_settings
from anonchat.core.exceptions import (
    FloodDetectedError,
    RateLimitExceededError,
    SuspiciousActivityError,
    UserBannedError,
)
from anonchat.core.logging import get_logger
from anonchat.core.security import compute_risk_score
from anonchat.models.security_log import SecurityLog

if TYPE_CHECKING:
    from anonchat.core.container import Container


class SecurityService:
    """سرویس امنیت و ضد-سوءاستفاده."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.security")
        self._settings = get_settings()
        # پنجره‌ی کش‌شده: telegram_id -> deque(timestamps)
        self._message_times: dict[int, deque[float]] = defaultdict(deque)
        # تشخیص تکرار: telegram_id -> deque(content_hash)
        self._recent_hashes: dict[int, deque[tuple[float, str]]] = defaultdict(deque)
        # شمارنده‌ی نقض‌ها
        self._violations: dict[int, int] = defaultdict(int)

    async def check_rate_limit(self, telegram_id: int) -> None:
        """بررسی محدودیت نرخ پیام.

        از الگوریتم Sliding Window استفاده می‌کند.
        در صورت نقض، استثنا پرتاب می‌کند و رویداد ثبت می‌شود.

        نکته: ``_message_times`` یک ``defaultdict(deque)`` است، بنابراین برای
        کاربر جدید به‌صورت خودکار یک deque خالی ساخته می‌شود و کاربر می‌تواند
        اولین پیام خود را بفرستد (``len(times) == 0 < limit``).
        """
        now = time.monotonic()
        window = self._settings.rate_limit_window
        limit = self._settings.rate_limit_messages

        times = self._message_times[telegram_id]
        # حذف timestamps قدیمی
        while times and times[0] < now - window:
            times.popleft()

        if len(times) >= limit:
            self._violations[telegram_id] += 1
            await self._log_security_event(
                telegram_id,
                event_type="rate_limit",
                severity="warning",
                description=f"نقض Rate Limit: {len(times)} پیام در {window} ثانیه",
            )
            raise RateLimitExceededError(telegram_id, limit, window)

        times.append(now)

    async def detect_flood(self, telegram_id: int, content_hash: str | None) -> None:
        """تشخیص Flood — پیام تکراری پشت سر هم.

        اگر ۵ پیام یکسان در ۱۰ ثانیه ارسال شود، Flood تشخیص داده می‌شود.
        """
        if not content_hash:
            return
        now = time.monotonic()
        recent = self._recent_hashes[telegram_id]
        # پاک کردن قدیمی‌ها (بازده ۳۰ ثانیه)
        while recent and recent[0][0] < now - 30:
            recent.popleft()

        # شمارش تکرار در ۱۰ ثانیه اخیر
        count = sum(1 for t, h in recent if t > now - 10 and h == content_hash)
        recent.append((now, content_hash))

        if count >= 4:
            self._violations[telegram_id] += 1
            await self._log_security_event(
                telegram_id,
                event_type="flood",
                severity="warning",
                description=f"Flood تشخیص داده شد: {count + 1} پیام تکراری",
            )
            raise FloodDetectedError(telegram_id)

    async def evaluate_risk(self, telegram_id: int) -> int:
        """محاسبه و ذخیره‌ی امتیاز ریسک کاربر."""
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            report_repo = self._container.report_repo_with(session)
            ban_repo = self._container.ban_repo_with(session)

            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return 0

            reports = await report_repo.count_active_for_user(user.id)
            bans = await ban_repo.get_user_bans(user.id)
            account_age = (datetime.now(UTC) - user.created_at.replace(
                tzinfo=UTC if user.created_at.tzinfo is None else user.created_at.tzinfo
            )).days

            score = compute_risk_score(
                reports_count=reports,
                bans_count=len(bans),
                rate_limit_hits=self._violations.get(telegram_id, 0),
                account_age_days=account_age,
            )

            await user_repo.update_risk_score(user.id, score)
            await session.commit()

        if score >= self._settings.risk_score_threshold:
            await self._log_security_event(
                telegram_id,
                event_type="suspicious",
                severity="error",
                description=f"امتیاز ریسک بحرانی: {score}",
            )
            # محدودسازی خودکار: بن موقت
            await self._auto_restrict(telegram_id, score)
            raise SuspiciousActivityError(telegram_id, "risk_score_critical", score)

        return score

    async def _auto_restrict(self, telegram_id: int, score: int) -> None:
        """محدودسازی خودکار کاربر پرخطر."""
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            ban_repo = self._container.ban_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return
            await ban_repo.ban_user(
                user_id=user.id,
                reason=f"بن خودکار — امتیاز ریسک {score}",
                duration_hours=self._settings.auto_ban_duration_hours,
            )
            await session.commit()
        self._log.warning(
            "security.auto_ban",
            telegram_id=telegram_id,
            score=score,
        )

    async def report_user(
        self,
        reporter_telegram_id: int,
        reported_telegram_id: int,
        reason: str,
        description: str | None = None,
        chat_session_id: int | None = None,
    ) -> None:
        """ثبت گزارش علیه یک کاربر و بررسی بن خودکار."""
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            report_repo = self._container.report_repo_with(session)

            reporter = await user_repo.get_by_telegram_id(reporter_telegram_id)
            reported = await user_repo.get_by_telegram_id(reported_telegram_id)
            if reporter is None or reported is None:
                return

            await report_repo.create_report(
                reporter_id=reporter.id,
                reported_id=reported.id,
                reason=reason,
                description=description,
                chat_session_id=chat_session_id,
            )

            # بررسی آستانه‌ی بن خودکار (همان نشست)
            active_reports = await report_repo.count_active_for_user(reported.id)
            await session.commit()

            # مقادیر لازم برای فراخوانی پس از commit را ذخیره می‌کنیم
            should_auto_restrict = (
                active_reports >= self._settings.auto_ban_report_threshold
            )

        # محدودسازی خودکار در نشست جداگانه
        if should_auto_restrict:
            await self._auto_restrict(reported_telegram_id, active_reports)

        self._log.info(
            "security.report_filed",
            reporter=reporter_telegram_id,
            reported=reported_telegram_id,
            reason=reason,
        )

    async def _log_security_event(
        self,
        telegram_id: int | None,
        *,
        event_type: str,
        severity: str,
        description: str,
        metadata: dict | None = None,
    ) -> None:
        """ثبت رویداد امنیتی در دیتابیس."""
        import json

        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = None
            if telegram_id is not None:
                user = await user_repo.get_by_telegram_id(telegram_id)

            log_entry = SecurityLog(
                user_id=user.id if user else None,
                event_type=event_type,
                severity=severity,
                description=description,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(log_entry)
            await session.commit()

    async def check_access(self, telegram_id: int) -> None:
        """بررسی جامع دسترسی — بن، Rate Limit، ریسک.

        این متد در Middleware قبل از هر هندلر فراخوانی می‌شود.
        """
        # 1. بررسی بن
        async with self._container.session() as session:
            ban_repo = self._container.ban_repo_with(session)
            ban = await ban_repo.get_active_ban_by_telegram(telegram_id)
            if ban is not None:
                raise UserBannedError(
                    telegram_id,
                    until=ban.banned_until,
                    reason=ban.reason,
                )

        # 2. بررسی Rate Limit
        await self.check_rate_limit(telegram_id)

    def reset_user_state(self, telegram_id: int) -> None:
        """پاک کردن کش کاربر (هنگام پایان گفتگو یا خروج)."""
        self._message_times.pop(telegram_id, None)
        self._recent_hashes.pop(telegram_id, None)
