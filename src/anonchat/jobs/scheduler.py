"""زمان‌بند کارهای دوره‌ای (Background Jobs).

کارهای زمان‌بندی‌شده:
- پاکسازی بن‌های منقضی (هر ساعت)
- پاکسازی صف انتظار قدیمی (هر ۵ دقیقه)
- بررسی دستاوردهای کاربران آنلاین (هر ۱۵ دقیقه)
- به‌روزرسانی آمار (هر ساعت)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container

_log = get_logger("scheduler")


class JobScheduler:
    """مدیریت کارهای پس‌زمینه."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """شروع زمان‌بند با ثبت همه‌ی کارها."""
        self._register_jobs()
        self._scheduler.start()
        _log.info("scheduler.started")

    async def stop(self) -> None:
        """توقف زمان‌بند."""
        self._scheduler.shutdown(wait=False)
        _log.info("scheduler.stopped")

    def _register_jobs(self) -> None:
        """ثبت کارهای دوره‌ای."""

        # پاکسازی بن‌های منقضی — هر ساعت
        self._scheduler.add_job(
            self._cleanup_expired_bans,
            trigger=IntervalTrigger(hours=1),
            id="cleanup_bans",
            replace_existing=True,
        )

        # پاکسازی صف انتظار قدیمی — هر ۵ دقیقه
        self._scheduler.add_job(
            self._cleanup_stale_queue,
            trigger=IntervalTrigger(minutes=5),
            id="cleanup_queue",
            replace_existing=True,
        )

        # پاکسازی کاربران آفلاین — هر ۱۰ دقیقه
        self._scheduler.add_job(
            self._cleanup_offline_users,
            trigger=IntervalTrigger(minutes=10),
            id="cleanup_offline",
            replace_existing=True,
        )

    async def _cleanup_expired_bans(self) -> None:
        """غیرفعال کردن بن‌های منقضی."""
        try:
            async with self._container.session() as session:
                ban_repo = self._container.ban_repo_with(session)
                count = await ban_repo.cleanup_expired()
                await session.commit()
            if count > 0:
                _log.info("scheduler.bans_cleaned", count=count)
        except Exception as exc:
            _log.error("scheduler.cleanup_bans_failed", error=str(exc))

    async def _cleanup_stale_queue(self) -> None:
        """پاک کردن کاربران قدیمی از صف انتظار."""
        try:
            count = await self._container.matchmaking_service.cleanup_stale_queue()
            if count > 0:
                _log.info("scheduler.queue_cleaned", count=count)
        except Exception as exc:
            _log.error("scheduler.cleanup_queue_failed", error=str(exc))

    async def _cleanup_offline_users(self) -> None:
        """علامت‌گذاری کاربران غیرفعال به‌عنوان آفلاین."""
        try:
            from datetime import UTC, datetime, timedelta

            from sqlalchemy import update

            from anonchat.models.user import User

            cutoff = datetime.now(UTC) - timedelta(minutes=5)
            async with self._container.session() as session:
                await session.execute(
                    update(User)
                    .where(User.is_online.is_(True), User.last_seen < cutoff)
                    .values(is_online=False)
                )
                await session.commit()
        except Exception as exc:
            _log.error("scheduler.cleanup_offline_failed", error=str(exc))
