"""نقطه‌ی ورود اصلی ربات سایه.

این ماژول ربات را راه‌اندازی می‌کند:
1. پیکربندی لاگ
2. راه‌اندازی کانتینر DI و پایگاه داده
3. اجرای مهاجرت‌ها (در صورت نیاز)
4. کاشت داده‌ی اولیه (دستاوردها)
5. شروع زمان‌بند کارهای پس‌زمینه
6. شروع سرور سلامت‌سنج
7. شروع Long Polling (یا Webhook)

روی پلن رایگان Railway از Long Polling استفاده می‌کنیم چون
نیاز به دامنه و SSL ندارد.
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


async def run_migrations() -> None:
    """اجرای مهاجرت‌های Alembic در زمان راه‌اندازی.

    روی Railway، اجرای خودکار مهاجرت تضمین می‌کند که اسکیمای
    دیتابیس همیشه به‌روز است.
    """
    try:
        import os

        from alembic import command
        from alembic.config import Config

        # مسیر alembic.ini
        ini_path = os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini")
        config = Config(ini_path)
        # override URL با تنظیمات محیطی
        config.set_main_option("sqlalchemy.url", get_settings().database_url)
        command.upgrade(config, "head")
        _log.info("main.migrations_applied")
    except Exception as exc:
        _log.error("main.migration_failed", error=str(exc))
        # در صورت شکست، جداول را به‌صورت مستقیم بساز (فقط SQLite)
        container = get_container()
        await container.db_manager.create_tables()


async def seed_data() -> None:
    """کاشت داده‌ی اولیه."""
    try:
        container = get_container()
        await container.achievement_service.seed_default_achievements()
    except Exception as exc:
        _log.error("main.seed_failed", error=str(exc))


async def main() -> None:
    """اجرای اصلی ربات."""
    # 1. پیکربندی لاگ
    configure_logging()
    settings = get_settings()
    _log.info("main.starting", version="1.0.0")

    # 2. راه‌اندازی کانتینر
    container = get_container()
    await container.init()

    # 3. مهاجرت‌ها
    await run_migrations()

    # 4. کاشت داده
    await seed_data()

    # 5. زمان‌بند
    scheduler = JobScheduler(container)
    scheduler.start()

    # 6. سرور سلامت
    health = HealthServer(container, settings.health_port)
    await health.start()

    # 7. بات
    bot = create_bot()
    dp = create_dispatcher()
    container.admin_service.set_bot_running(True)

    # ثبت هندلر خاموشی
    stop_event = asyncio.Event()

    def _signal_handler(*_: object) -> None:
        _log.info("main.shutdown_signal")
        stop_event.set()

    # فقط در محیط‌های یونیکس
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_event_loop().add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, _signal_handler)  # type: ignore[arg-type]

    # 8. اجرای Long Polling
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
    """نقطه ورود اسکریپت Poetry."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main_entry()
