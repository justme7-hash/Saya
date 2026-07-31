"""محیط Alembic با پشتیبانی async.

این فایل از SQLAlchemy async engine استفاده می‌کند تا مهاجرت‌ها
به‌صورت ناهمگام اجرا شوند (هماهنگ با runtime اصلی).
"""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# اضافه کردن مسیر src به sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anonchat.core.config import get_settings  # noqa: E402
from anonchat.db.base import Base  # noqa: E402
from anonchat.models import __all_models__  # noqa: F401, E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# override URL با تنظیمات محیطی
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """اجرای مهاجرت در حالت offline (تولید SQL بدون اتصال)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """اجرای مهاجرت با اتصال داده‌شده."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """اجرای مهاجرت در حالت online با async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
