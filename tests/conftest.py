"""تنظیمات مشترک pytest."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# اضافه کردن مسیر src
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# متغیرهای محیطی تست
os.environ.setdefault("BOT_TOKEN", "123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("ADMIN_IDS", "123456789")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "console")


@pytest.fixture(scope="session")
def event_loop():
    """Event loop مشترک برای کل session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_manager():
    """ایجاد دیتابیس in-memory برای هر تست."""
    from anonchat.core.container import set_container, Container
    from anonchat.db.base import Base
    from anonchat.models import __all_models__  # noqa: F401

    container = Container()
    await container.init()
    # ساخت جداول
    async with container.db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    set_container(container)
    yield container

    await container.db_manager.engine.dispose()
    # پاک کردن کش کانتینر سراسری
    from anonchat.core.container import _container
    if _container is not None:
        await _container.close()


@pytest_asyncio.fixture
async def sample_user(db_manager):
    """ایجاد کاربر نمونه."""
    from anonchat.core.security import generate_referral_code
    from anonchat.db.repositories.user_repo import UserRepository

    repo = db_manager.user_repo()
    user = await repo.create_user(
        telegram_id=111111111,
        referral_code=generate_referral_code(111111111),
        language="fa",
    )
    await repo.commit()
    return user
