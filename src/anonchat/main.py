"""نقطه‌ی ورود اصلی ربات سایه.

این ماژول ربات را راه‌اندازی می‌کند:
1. پیکربندی لاگ
2. اجرای مهاجرت‌های دیتابیس (قبل از event loop)
3. راه‌اندازی کانتینر DI و پایگاه داده
4. کاشت داده‌ی اولیه (دستاوردها)
5. شروع زمان‌بند کارهای پس‌زمینه
6. شروع سرور سلامت‌سنج
7. شروع Long Polling

روی پلن رایگان Railway از Long Polling استفاده می‌کنیم چون
نیاز به دامنه و SSL ندارد.

**نکته‌ی معماری:** مهاجرت‌ها قبل از شروع event loop اجرا می‌شوند چون
Alembic از ``asyncio.run()`` داخلی استفاده می‌کند که نمی‌تواند داخل
یک event loop در حال اجرا صدا زده شود.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import NoReturn

from anonchat.bot.dispatcher import create_bot, create_dispatcher
from anonchat.core.config import get_settings
from anonchat.core.container import get_container
from anonchat.core.logging import configure_logging, get_logger
from anonchat.jobs.scheduler import JobScheduler
from anonchat.utils.health_server import HealthServer

_log = get_logger("main")


def run_migrations_sync() -> None:
    """اجرای مهاجرت‌های Alembic به‌صورت همزمان.

    **مهم:** این متد باید قبل از شروع event loop صدا زده شود، چون
    ``alembic/env.py`` از ``asyncio.run()`` داخلی استفاده می‌کند که
    نمی‌تواند داخل یک event loop در حال اجرا صدا زده شود.
    """
    try:
        import os

        from alembic import command
        from alembic.config import Config

        ini_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
        )
        if not os.path.exists(ini_path):
            _log.warning("main.alembic_ini_missing", path=ini_path)
            return

        config = Config(ini_path)
        config.set_main_option("sqlalchemy.url", get_settings().database_url)
        command.upgrade(config, "head")
        _log.info("main.migrations_applied")
    except Exception as exc:
        _log.error("main.migration_failed", error=str(exc))


async def ensure_tables_exist() -> None:
    """اطمینان از وجود تمام جداول — fallback اگر مهاجرت شکست خورد.

    ``create_all`` در SQLAlchemy فقط جداولی که وجود ندارند را می‌سازد
    و جداول موجود را تغییر نمی‌دهد. بنابراین همیشه امن است که صدا زده شود.
    این تابع تضمین می‌کند که حتی اگر مهاجرت شکست بخورد یا دیتابیس قدیمی
    باشد، تمام جداول (از جمله anonymous_messages) وجود داشته باشند.
    """
    try:
        container = get_container()
        from sqlalchemy import inspect

        # بررسی جداول موجود
        async with container.db_manager.engine.connect() as conn:
            existing_tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        # دریافت تمام جداول مورد انتظار از مدل‌ها
        from anonchat.db.base import Base
        from anonchat.models import __all_models__  # noqa: F401

        expected_tables = set(Base.metadata.tables.keys())
        missing_tables = expected_tables - set(existing_tables)

        if missing_tables or not existing_tables:
            _log.info(
                "main.creating_missing_tables",
                missing=list(missing_tables) or "all",
            )
            await container.db_manager.create_tables()
        else:
            _log.info("main.tables_exist", count=len(existing_tables))
    except Exception as exc:
        _log.error("main.ensure_tables_failed", error=str(exc))


async def seed_data() -> None:
    """کاشت داده‌ی اولیه."""
    try:
        container = get_container()
        await container.achievement_service.seed_default_achievements()
    except Exception as exc:
        _log.error("main.seed_failed", error=str(exc))


async def main() -> None:
    """اجرای اصلی ربات."""
    configure_logging()
    settings = get_settings()
    _log.info("main.starting", version="1.0.0")

    container = get_container()
    await container.init()

    # اطمینان از وجود جداول (fallback مهاجرت)
    await ensure_tables_exist()

    # کاشت داده
    await seed_data()

    # زمان‌بند
    scheduler = JobScheduler(container)
    scheduler.start()

    # سرور سلامت
    health = HealthServer(container, settings.health_port)
    await health.start()

    # بات
    bot = create_bot()
    dp = create_dispatcher()
    container.admin_service.set_bot_running(True)

    # هندلر خاموشی
    stop_event = asyncio.Event()

    def _signal_handler(*_: object) -> None:
        _log.info("main.shutdown_signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, _signal_handler)  # type: ignore[arg-type]

    _log.info("main.polling_started")
    polling_task = asyncio.create_task(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )

    try:
        await stop_event.wait()
    finally:
        _log.info("main.stopping")
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        await dp.stop_polling()
        await bot.session.close()
        await health.stop()
        await scheduler.stop()
        await container.close()
        _log.info("main.stopped")


def main_entry() -> NoReturn:
    """نقطه‌ی ورود اسکریپت Poetry.

    مهاجرت‌ها را قبل از شروع event loop اجرا می‌کند تا از تداخل
    ``asyncio.run()`` داخلی Alembic جلوگیری شود.
    """
    configure_logging()

    _log.info("main.running_migrations")
    run_migrations_sync()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main_entry()
