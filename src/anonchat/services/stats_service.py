"""سرویس آمار — ارائه‌ی داده‌های تحلیلی.

**نکته‌ی معماری:** تمام عملیات دیتابیس در ``async with container.session()``
انجام می‌شود تا نشست به‌درستی بسته شده و اتصال به pool برگردد.
این الگو از نشت اتصال (connection leak) جلوگیری می‌کند.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.core.container import Container


class StatsService:
    """سرویس آمار و گزارش‌گیری."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.stats")

    async def get_overview(self) -> dict:
        """دریافت خلاصه‌ی آمار."""
        async with self._container.session() as session:
            stats_repo = self._container.stats_repo_with(session)
            return await stats_repo.get_overview()

    async def get_growth(self, days: int = 30) -> list[dict]:
        """رشد کاربران روزانه."""
        async with self._container.session() as session:
            stats_repo = self._container.stats_repo_with(session)
            return await stats_repo.get_growth(days=days)

    async def get_chat_stats(self, days: int = 7) -> dict:
        """آمار گفتگو."""
        async with self._container.session() as session:
            stats_repo = self._container.stats_repo_with(session)
            return await stats_repo.get_chat_stats(days=days)

    async def get_leaderboard(self, metric: str = "xp", limit: int = 10) -> list:
        """جدول رتبه‌بندی."""
        async with self._container.session() as session:
            stats_repo = self._container.stats_repo_with(session)
            return await stats_repo.get_top_users(metric=metric, limit=limit)

    async def get_user_stats(self, telegram_id: int) -> dict:
        """آمار یک کاربر خاص."""
        async with self._container.session() as session:
            user_repo = self._container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                return {}
            return {
                "telegram_id": user.telegram_id,
                "nickname": user.nickname,
                "level": user.level,
                "xp": user.xp,
                "total_chats": user.total_chats,
                "total_messages_sent": user.total_messages_sent,
                "total_messages_received": user.total_messages_received,
                "risk_score": user.risk_score,
                "warnings_count": user.warnings_count,
                "is_online": user.is_online,
                "member_since": user.created_at.isoformat(),
            }
