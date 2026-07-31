"""مدیریت نشست ناهمگام پایگاه داده.

این ماژول لایه‌ی نازکی روی ``async_sessionmaker`` است که:
- engine را بر اساس ``DATABASE_URL`` می‌سازد.
- برای SQLite، ``check_same_thread`` را غیرفعال می‌کند.
- متد ``run_migrations`` برای اجرای مهاجرت‌ها در زمان راه‌اندازی فراهم می‌کند.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from anonchat.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseSessionManager:
    """مدیریت چرخه‌ی حیات engine و session."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._log = get_logger("db")
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None

    async def init(self) -> None:
        """ساخت engine و session maker."""
        engine_kwargs: dict[str, Any] = {
            "echo": False,
            "pool_pre_ping": True,
        }
        if self._url.startswith("sqlite"):
            # برای SQLite باید check_same_thread غیرفعال باشد
            engine_kwargs["connect_args"] = {"check_same_thread": False}

        self._engine = create_async_engine(self._url, **engine_kwargs)
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        self._log.info("db.engine_created", url=self._url.split("://")[0])

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager هنوز init نشده است.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_maker is None:
            raise RuntimeError("DatabaseSessionManager هنوز init نشده است.")
        return self._session_maker

    async def close(self) -> None:
        """بستن engine."""
        if self._engine is not None:
            await self._engine.dispose()
            self._log.info("db.engine_closed")

    async def create_tables(self) -> None:
        """ساخت تمام جداول (فقط برای محیط توسعه/تست).

        در پروداکشن از Alembic استفاده می‌شود.
        """
        from anonchat.db.base import Base

        # ایمپورت تمام مدل‌ها برای ثبت در MetaData
        from anonchat.models import __all_models__  # noqa: F401

        async with self._engine.begin() as conn:  # type: ignore[union-attr]
            await conn.run_sync(Base.metadata.create_all)
        self._log.info("db.tables_created")
