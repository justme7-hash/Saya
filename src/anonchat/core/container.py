"""کانتینر تزریق وابستگی (Dependency Injection).

این کانتینر چرخه‌ی حیات تمام کامپوننت‌های پروژه را مدیریت می‌کند:
- نشست پایگاه داده (AsyncSession factory)
- مخازن (Repositories)
- سرویس‌ها (Services)
- کش‌های درون‌حافظه‌ای

طراحی به‌گونه‌ای است که جایگزینی SQLite با PostgreSQL تنها با تغییر
``DATABASE_URL`` ممکن است — هیچ وابستگی مستقیمی به SQLite در سرویس‌ها نیست.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from cachetools import TTLCache

from anonchat.core.config import get_settings
from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from anonchat.db.repositories.ban_repo import BanRepository
    from anonchat.db.repositories.chat_repo import ChatRepository
    from anonchat.db.repositories.favorite_repo import FavoriteRepository
    from anonchat.db.repositories.referral_repo import ReferralRepository
    from anonchat.db.repositories.report_repo import ReportRepository
    from anonchat.db.repositories.stats_repo import StatsRepository
    from anonchat.db.repositories.user_repo import UserRepository
    from anonchat.db.session import DatabaseSessionManager
    from anonchat.services.achievement_service import AchievementService
    from anonchat.services.admin_service import AdminService
    from anonchat.services.chat_service import ChatService
    from anonchat.services.matchmaking_service import MatchmakingService
    from anonchat.services.message_service import MessageService
    from anonchat.services.referral_service import ReferralService
    from anonchat.services.security_service import SecurityService
    from anonchat.services.stats_service import StatsService
    from anonchat.services.user_service import UserService


class Container:
    """کانتینر ریشه‌ی وابستگی‌ها.

    تمام کامپوننت‌ها به‌صورت lazy ایجاد می‌شوند تا هزینه‌ی راه‌اندازی
    پایین بماند و فقط آنچه واقعاً استفاده می‌شود ساخته شود.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._log = get_logger("container")
        self._db_manager: DatabaseSessionManager | None = None
        self._user_cache: TTLCache[int, dict] = TTLCache(
            maxsize=10_000, ttl=self._settings.user_cache_ttl
        )
        self._initialized = False

    # ------------------------------------------------------------------ #
    #  چرخه‌ی حیات
    # ------------------------------------------------------------------ #

    async def init(self) -> None:
        """راه‌اندازی منابع ناهمگام (async)."""
        if self._initialized:
            return
        from anonchat.db.session import DatabaseSessionManager

        self._db_manager = DatabaseSessionManager(self._settings.database_url)
        await self._db_manager.init()
        self._initialized = True
        self._log.info("container.initialized", db=self._settings.database_url[:40])

    async def close(self) -> None:
        """آزادسازی منابع."""
        if self._db_manager is not None:
            await self._db_manager.close()
        self._initialized = False
        self._log.info("container.closed")

    @property
    def settings(self):
        return self._settings

    @property
    def db_manager(self) -> DatabaseSessionManager:
        if self._db_manager is None:
            raise RuntimeError("کانتینر هنوز init() نشده است.")
        return self._db_manager

    @property
    def user_cache(self) -> TTLCache[int, dict]:
        return self._user_cache

    @property
    def session_factory(self):
        """دریافت factory نشست پایگاه داده (async_sessionmaker).

        برای دریافت یک نشست واقعی، آن را صدا بزنید:
        ``session = container.session_factory()`` یا
        ``async with container.session_factory() as session:``.
        """
        return self.db_manager.session_factory

    @asynccontextmanager
    async def session(self):
        """Context manager امن برای نشست پایگاه داده.

        نشست را باز می‌کند، در پایان (چه موفق چه خطا) آن را می‌بندد
        و به pool برمی‌گرداند. این روش توصیه‌شده برای جلوگیری از
        نشت اتصال (connection leak) است.

        مثال::

            async with container.session() as session:
                repo = UserRepository(session)
                user = await repo.get_by_telegram_id(123)
                await session.commit()

        Yields:
            نشست AsyncSession آماده‌ی استفاده.
        """
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # ------------------------------------------------------------------ #
    #  Repositories — دو حالت:
    #   1. repo_with(session): برای استفاده‌ی امن در context manager
    #   2. *_repo(): قدیمی (deprecated) — برای سازگاری
    # ------------------------------------------------------------------ #

    def user_repo_with(self, session) -> "UserRepository":
        """ساخت مخزن با نشست داده‌شده (توصیه‌شده)."""
        from anonchat.db.repositories.user_repo import UserRepository
        return UserRepository(session)

    def chat_repo_with(self, session) -> "ChatRepository":
        from anonchat.db.repositories.chat_repo import ChatRepository
        return ChatRepository(session)

    def report_repo_with(self, session) -> "ReportRepository":
        from anonchat.db.repositories.report_repo import ReportRepository
        return ReportRepository(session)

    def ban_repo_with(self, session) -> "BanRepository":
        from anonchat.db.repositories.ban_repo import BanRepository
        return BanRepository(session)

    def favorite_repo_with(self, session) -> "FavoriteRepository":
        from anonchat.db.repositories.favorite_repo import FavoriteRepository
        return FavoriteRepository(session)

    def referral_repo_with(self, session) -> "ReferralRepository":
        from anonchat.db.repositories.referral_repo import ReferralRepository
        return ReferralRepository(session)

    def stats_repo_with(self, session) -> "StatsRepository":
        from anonchat.db.repositories.stats_repo import StatsRepository
        return StatsRepository(session)

    def user_repo(self) -> UserRepository:
        """[Deprecated] نمونه‌ی مخزن با نشست تازه.

        ⚠️ هشدار: نشست بازگشتی از این متد باید به‌صورت دستی بسته شود.
        ترجیحاً از ``user_repo_with(session)`` همراه با ``container.session()``
        استفاده کنید.
        """
        from anonchat.db.repositories.user_repo import UserRepository
        return UserRepository(self.session_factory())

    def chat_repo(self) -> ChatRepository:
        from anonchat.db.repositories.chat_repo import ChatRepository
        return ChatRepository(self.session_factory())

    def report_repo(self) -> ReportRepository:
        from anonchat.db.repositories.report_repo import ReportRepository
        return ReportRepository(self.session_factory())

    def ban_repo(self) -> BanRepository:
        from anonchat.db.repositories.ban_repo import BanRepository
        return BanRepository(self.session_factory())

    def favorite_repo(self) -> FavoriteRepository:
        from anonchat.db.repositories.favorite_repo import FavoriteRepository
        return FavoriteRepository(self.session_factory())

    def referral_repo(self) -> ReferralRepository:
        from anonchat.db.repositories.referral_repo import ReferralRepository
        return ReferralRepository(self.session_factory())

    def stats_repo(self) -> StatsRepository:
        from anonchat.db.repositories.stats_repo import StatsRepository
        return StatsRepository(self.session_factory())

    # ------------------------------------------------------------------ #
    #  Services (singleton در طول عمر ربات)
    # ------------------------------------------------------------------ #

    @property
    def user_service(self) -> UserService:
        from anonchat.services.user_service import UserService
        if not hasattr(self, "_user_service"):
            self._user_service = UserService(self)  # type: ignore[attr-defined]
        return self._user_service  # type: ignore[attr-defined]

    @property
    def matchmaking_service(self) -> MatchmakingService:
        from anonchat.services.matchmaking_service import MatchmakingService
        if not hasattr(self, "_matchmaking_service"):
            self._matchmaking_service = MatchmakingService(self)  # type: ignore[attr-defined]
        return self._matchmaking_service  # type: ignore[attr-defined]

    @property
    def chat_service(self) -> ChatService:
        from anonchat.services.chat_service import ChatService
        if not hasattr(self, "_chat_service"):
            self._chat_service = ChatService(self)  # type: ignore[attr-defined]
        return self._chat_service  # type: ignore[attr-defined]

    @property
    def message_service(self) -> MessageService:
        from anonchat.services.message_service import MessageService
        if not hasattr(self, "_message_service"):
            self._message_service = MessageService(self)  # type: ignore[attr-defined]
        return self._message_service  # type: ignore[attr-defined]

    @property
    def security_service(self) -> SecurityService:
        from anonchat.services.security_service import SecurityService
        if not hasattr(self, "_security_service"):
            self._security_service = SecurityService(self)  # type: ignore[attr-defined]
        return self._security_service  # type: ignore[attr-defined]

    @property
    def admin_service(self) -> AdminService:
        from anonchat.services.admin_service import AdminService
        if not hasattr(self, "_admin_service"):
            self._admin_service = AdminService(self)  # type: ignore[attr-defined]
        return self._admin_service  # type: ignore[attr-defined]

    @property
    def stats_service(self) -> StatsService:
        from anonchat.services.stats_service import StatsService
        if not hasattr(self, "_stats_service"):
            self._stats_service = StatsService(self)  # type: ignore[attr-defined]
        return self._stats_service  # type: ignore[attr-defined]

    @property
    def referral_service(self) -> ReferralService:
        from anonchat.services.referral_service import ReferralService
        if not hasattr(self, "_referral_service"):
            self._referral_service = ReferralService(self)  # type: ignore[attr-defined]
        return self._referral_service  # type: ignore[attr-defined]

    @property
    def achievement_service(self) -> AchievementService:
        from anonchat.services.achievement_service import AchievementService
        if not hasattr(self, "_achievement_service"):
            self._achievement_service = AchievementService(self)  # type: ignore[attr-defined]
        return self._achievement_service  # type: ignore[attr-defined]


# نمونه‌ی ماژول‌سطح
_container: Container | None = None


def get_container() -> Container:
    """دسترسی به کانتینر سراسری."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def set_container(container: Container) -> None:
    """تزریق کانتینر (برای تست)."""
    global _container
    _container = container
