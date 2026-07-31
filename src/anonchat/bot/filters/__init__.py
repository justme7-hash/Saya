"""فیلترهای سفارشی aiogram."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message, TelegramObject

from anonchat.core.container import get_container
from anonchat.core.logging import get_logger

_log = get_logger("filters")


class IsRegisteredFilter(BaseFilter):
    """فیلتر: آیا کاربر ثبت‌نام کرده است؟"""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        if not isinstance(event, Message):
            return False
        if event.from_user is None:
            return False
        container = get_container()
        async with container.session() as session:
            user_repo = container.user_repo_with(session)
            user = await user_repo.get_by_telegram_id(event.from_user.id)
            return user is not None and user.is_registered


class IsAdminFilter(BaseFilter):
    """فیلتر: آیا کاربر مدیر است؟"""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        if not isinstance(event, Message):
            return False
        if event.from_user is None:
            return False
        container = get_container()
        return container.settings.is_admin(event.from_user.id)


class IsNotBannedFilter(BaseFilter):
    """فیلتر: آیا کاربر بن نیست؟"""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        if not isinstance(event, Message):
            return False
        if event.from_user is None:
            return False
        container = get_container()
        async with container.session() as session:
            ban_repo = container.ban_repo_with(session)
            ban = await ban_repo.get_active_ban_by_telegram(event.from_user.id)
            return ban is None


class InChatFilter(BaseFilter):
    """فیلتر: آیا کاربر در گفتگوی فعالی است؟"""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        if not isinstance(event, Message):
            return False
        if event.from_user is None:
            return False
        container = get_container()
        chat_service = container.chat_service
        return await chat_service.is_in_chat(event.from_user.id)
