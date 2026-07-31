"""سرویس مدیریت — عملیات مدیران."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from anonchat.core.exceptions import AdminPermissionError, UserNotFoundError
from anonchat.core.logging import get_logger
from anonchat.models.security_log import AuditLog
from anonchat.schemas.admin import BanActionDTO, BroadcastDTO, SystemHealthDTO
from anonchat.schemas.user import UserResponseDTO

if TYPE_CHECKING:
    from aiogram import Bot

    from anonchat.core.container import Container


class AdminService:
    """سرویس عملیات مدیریتی."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.admin")
        self._started_at = datetime.now(UTC)
        self._bot_running = False

    def set_bot_running(self, running: bool) -> None:
        self._bot_running = running

    def assert_admin(self, telegram_id: int) -> None:
        """بررسی دسترسی مدیر."""
        if not self._container.settings.is_admin(telegram_id):
            raise AdminPermissionError(telegram_id)

    async def get_stats_overview(self):
        """دریافت خلاصه‌ی آمار سیستم."""
        stats_repo = self._container.stats_repo()
        return await stats_repo.get_overview()

    async def get_user_list(
        self, *, page: int = 1, per_page: int = 20, search: str | None = None
    ) -> dict:
        """دریافت لیست کاربران با صفحه‌بندی و جستجو."""
        user_repo = self._container.user_repo()
        from sqlalchemy import or_, select

        from anonchat.models.user import User

        stmt = select(User).where(User.is_registered.is_(True))
        if search:
            stmt = stmt.where(
                or_(
                    User.nickname.ilike(f"%{search}%"),
                    User.telegram_id == int(search) if search.isdigit() else False,
                )
            )
        count_stmt = select(User).where(User.is_registered.is_(True))
        if search:
            count_stmt = count_stmt.where(
                or_(
                    User.nickname.ilike(f"%{search}%"),
                    User.telegram_id == int(search) if search.isdigit() else False,
                )
            )

        total = len(list(await user_repo.get_many(filters={})))
        stmt = stmt.order_by(User.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page)

        async with self._container.session_factory()() as session:
            result = await session.execute(stmt)
            users = result.scalars().all()

        user_dtos = [UserResponseDTO.model_validate(u) for u in users]
        pages = max(1, math.ceil(total / per_page))
        return {
            "users": user_dtos,
            "total": total,
            "page": page,
            "pages": pages,
        }

    async def ban_user(self, dto: BanActionDTO, admin_telegram_id: int) -> None:
        """بن کردن کاربر توسط مدیر."""
        self.assert_admin(admin_telegram_id)
        user_repo = self._container.user_repo()
        ban_repo = self._container.ban_repo()

        user = await user_repo.get_by_telegram_id(dto.user_telegram_id)
        if user is None:
            raise UserNotFoundError(dto.user_telegram_id)

        admin = await user_repo.get_by_telegram_id(admin_telegram_id)
        await ban_repo.ban_user(
            user_id=user.id,
            reason=dto.reason,
            banned_by=admin.id if admin else None,
            duration_hours=dto.duration_hours,
            permanent=dto.permanent,
        )
        await ban_repo.commit()
        await self._log_audit(
            admin_telegram_id,
            action="ban",
            target_user_id=user.id,
            details=f"permanent={dto.permanent}, reason={dto.reason}",
        )
        self._log.info(
            "admin.ban",
            admin=admin_telegram_id,
            target=dto.user_telegram_id,
            permanent=dto.permanent,
        )

    async def unban_user(self, telegram_id: int, admin_telegram_id: int) -> bool:
        """لغو بن کاربر."""
        self.assert_admin(admin_telegram_id)
        user_repo = self._container.user_repo()
        ban_repo = self._container.ban_repo()

        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        admin = await user_repo.get_by_telegram_id(admin_telegram_id)

        result = await ban_repo.unban_user(
            user.id, unbanned_by=admin.id if admin else 0
        )
        await ban_repo.commit()
        if result:
            await self._log_audit(
                admin_telegram_id,
                action="unban",
                target_user_id=user.id,
            )
        return result

    async def block_user(self, telegram_id: int, admin_telegram_id: int) -> None:
        """بلاک کردن کاربر (قطع دسترسی بدون بن)."""
        self.assert_admin(admin_telegram_id)
        user_repo = self._container.user_repo()
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        await user_repo.update(user, is_blocked=True)
        await user_repo.commit()
        await self._log_audit(
            admin_telegram_id, action="block", target_user_id=user.id
        )

    async def broadcast(
        self, bot: Bot, dto: BroadcastDTO, admin_telegram_id: int
    ) -> int:
        """ارسال پیام همگانی.

        Returns:
            تعداد پیام‌های موفق.
        """
        self.assert_admin(admin_telegram_id)
        user_repo = self._container.user_repo()
        from sqlalchemy import select

        from anonchat.models.user import User

        stmt = select(User).where(User.is_registered.is_(True))
        if dto.target == "online":
            stmt = stmt.where(User.is_online.is_(True))

        sent = 0
        failed = 0
        async with self._container.session_factory()() as session:
            result = await session.execute(stmt)
            users = result.scalars().all()

        for user in users:
            try:
                await bot.send_message(
                    user.telegram_id, dto.message, parse_mode=dto.parse_mode
                )
                sent += 1
            except Exception as exc:
                failed += 1
                self._log.debug(
                    "broadcast.failed",
                    telegram_id=user.telegram_id,
                    error=str(exc),
                )

        await self._log_audit(
            admin_telegram_id,
            action="broadcast",
            details=f"sent={sent}, failed={failed}, target={dto.target}",
        )
        self._log.info(
            "admin.broadcast",
            admin=admin_telegram_id,
            sent=sent,
            failed=failed,
        )
        return sent

    async def set_maintenance(self, enabled: bool, admin_telegram_id: int) -> None:
        """فعال/غیرفعال کردن حالت نگهداری."""
        self.assert_admin(admin_telegram_id)
        # ذخیره در جدول settings
        async with self._container.session_factory()() as session:
            from sqlalchemy import select

            from anonchat.models.settings import Setting

            stmt = select(Setting).where(Setting.key == "maintenance_mode")
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()
            if setting is None:
                setting = Setting(
                    key="maintenance_mode",
                    value=str(enabled).lower(),
                    value_type="bool",
                    description="حالت نگهداری",
                    is_public=True,
                )
                session.add(setting)
            else:
                setting.value = str(enabled).lower()
            await session.commit()

        await self._log_audit(
            admin_telegram_id,
            action="maintenance",
            details=f"enabled={enabled}",
        )
        self._log.warning("admin.maintenance_toggled", enabled=enabled)

    async def get_system_health(self) -> SystemHealthDTO:
        """دریافت سلامت سیستم."""
        db_ok = True
        try:
            stats = await self.get_stats_overview()
            _ = stats
        except Exception:
            db_ok = False

        return SystemHealthDTO(
            status="healthy" if db_ok and self._bot_running else "degraded",
            database=db_ok,
            bot_running=self._bot_running,
            maintenance_mode=self._container.settings.maintenance_mode,
            uptime_seconds=(datetime.now(UTC) - self._started_at).total_seconds(),
            version="1.0.0",
            checked_at=datetime.now(UTC),
        )

    async def get_pending_reports(self, limit: int = 20) -> list:
        """دریافت گزارش‌های در انتظار بررسی."""
        report_repo = self._container.report_repo()
        return await report_repo.get_pending(limit=limit)

    async def resolve_report(
        self,
        report_id: int,
        status: str,
        admin_telegram_id: int,
        note: str | None = None,
    ) -> None:
        """تعیین تکلیف یک گزارش."""
        self.assert_admin(admin_telegram_id)
        user_repo = self._container.user_repo()
        report_repo = self._container.report_repo()
        admin = await user_repo.get_by_telegram_id(admin_telegram_id)
        await report_repo.resolve_report(
            report_id,
            status=status,
            reviewed_by=admin.id if admin else 0,
            admin_note=note,
        )
        await report_repo.commit()
        await self._log_audit(
            admin_telegram_id,
            action="report_resolved",
            details=f"report={report_id}, status={status}",
        )

    async def _log_audit(
        self,
        admin_telegram_id: int,
        *,
        action: str,
        target_user_id: int | None = None,
        details: str | None = None,
    ) -> None:
        """ثبت رخداد حسابرسی."""
        user_repo = self._container.user_repo()
        admin = await user_repo.get_by_telegram_id(admin_telegram_id)
        entry = AuditLog(
            admin_id=admin.id if admin else None,
            action=action,
            target_user_id=target_user_id,
            details=details,
        )
        async with self._container.session_factory()() as session:
            session.add(entry)
            await session.commit()
