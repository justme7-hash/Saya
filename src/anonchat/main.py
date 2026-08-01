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

    اگر مهاجرت شکست بخورد (مثلاً چون جدول‌ها از قبل وجود دارند)،
    ``alembic stamp head`` را اجرا می‌کند تا alembic بداند که دیتابیس
    در نسخه‌ی نهایی است. سپس ``ensure_tables_exist`` (که بعداً صدا زده
    می‌شود) ستون‌های مفقود را اضافه می‌کند.
    """
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

    try:
        command.upgrade(config, "head")
        _log.info("main.migrations_applied")
    except Exception as exc:
        _log.error("main.migration_failed", error=str(exc))
        # اگر مهاجرت شکست خورد، stamp کن تا دفعات بعدی از نو شروع نشود
        # ensure_tables_exist ستون‌های مفقود را اضافه می‌کند
        try:
            command.stamp(config, "head")
            _log.info("main.migration_stamped_after_failure")
        except Exception as stamp_exc:
            _log.error("main.migration_stamp_failed", error=str(stamp_exc))


async def ensure_tables_exist() -> None:
    """اطمینان از وجود تمام جداول و ستون‌ها — fallback اگر مهاجرت شکست خورد.

    این تابع دو کار انجام می‌دهد:
    ۱. اگر جدولی وجود ندارد، آن را می‌سازد (با ``create_all``).
    ۲. اگر جدولی وجود دارد ولی ستون‌های جدیدی (که در مدل هست ولی در دیتابیس نیست)
       اضافه نشده، آن‌ها را با ``ALTER TABLE ADD COLUMN`` اضافه می‌کند.

    این تابع برای مواردی که دیتابیس قدیمی است و مهاجرت‌ها شکست خورده‌اند
    (مثلاً «table users already exists») ضروری است.
    """
    try:
        container = get_container()
        from sqlalchemy import inspect, text

        from anonchat.db.base import Base
        from anonchat.models import __all_models__  # noqa: F401

        async with container.db_manager.engine.begin() as conn:
            def _check_and_create(sync_conn) -> dict:
                """بررسی جداول و ستون‌ها — در sync context اجرا می‌شود."""
                insp = inspect(sync_conn)
                existing_tables = set(insp.get_table_names())
                expected_tables = Base.metadata.tables

                missing_tables = set(expected_tables.keys()) - existing_tables
                missing_columns: dict[str, list] = {}

                # بررسی ستون‌های مفقود در جداول موجود
                for table_name in expected_tables:
                    if table_name not in existing_tables:
                        continue
                    table_obj = expected_tables[table_name]
                    existing_cols = {col["name"] for col in insp.get_columns(table_name)}
                    expected_cols = set(table_obj.columns.keys())
                    missing = expected_cols - existing_cols
                    if missing:
                        missing_columns[table_name] = list(missing)

                return {
                    "missing_tables": missing_tables,
                    "missing_columns": missing_columns,
                }

            result = await conn.run_sync(_check_and_create)
            missing_tables = result["missing_tables"]
            missing_columns = result["missing_columns"]

        # ساخت جداول مفقود
        if missing_tables:
            _log.info("main.creating_missing_tables", missing=list(missing_tables))
            await container.db_manager.create_tables()

        # اضافه کردن ستون‌های مفقود با ALTER TABLE
        if missing_columns:
            _log.info("main.adding_missing_columns", columns=missing_columns)
            async with container.db_manager.engine.begin() as conn:
                for table_name, cols in missing_columns.items():
                    table_obj = Base.metadata.tables[table_name]
                    for col_name in cols:
                        col_obj = table_obj.columns[col_name]
                        # ساخت عبارت ALTER TABLE ADD COLUMN
                        col_type = col_obj.type.compile(
                            dialect=container.db_manager.engine.dialect
                        )
                        nullable = "" if col_obj.nullable else " NOT NULL"
                        default = ""
                        if col_obj.server_default is not None:
                            default = f" DEFAULT {col_obj.server_default.arg}"
                        elif col_obj.default is not None and col_obj.default.arg is not None:
                            default = f" DEFAULT {col_obj.default.arg}"
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{nullable}{default}"
                        _log.info("main.adding_column", table=table_name, column=col_name)
                        await conn.execute(text(sql))

        # لاگ نهایی
        async with container.db_manager.engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
        _log.info("main.tables_exist", count=len(table_names))

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
