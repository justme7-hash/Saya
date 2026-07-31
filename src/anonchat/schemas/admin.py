"""DTOهای مدیریتی."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from anonchat.schemas.user import UserResponseDTO


class StatsOverviewDTO(BaseModel):
    """خلاصه‌ی آمار داشبورد."""

    total_users: int
    online_users: int
    active_today: int
    active_chats: int
    pending_reports: int
    active_bans: int
    avg_chat_duration_min: float


class BroadcastDTO(BaseModel):
    """DTO ارسال پیام همگانی."""

    message: str = Field(..., min_length=1, max_length=4000)
    target: Literal["all", "online", "registered"] = "all"
    parse_mode: str | None = None


class BanActionDTO(BaseModel):
    """DTO عملیات بن."""

    user_telegram_id: int
    reason: str = Field(..., min_length=3, max_length=255)
    duration_hours: int | None = Field(None, ge=1, le=8760)
    permanent: bool = False


class AdminUserListDTO(BaseModel):
    """DTO لیست کاربران برای پنل مدیر."""

    users: list[UserResponseDTO]
    total: int
    page: int
    pages: int


class SystemHealthDTO(BaseModel):
    """DTO سلامت سیستم."""

    status: Literal["healthy", "degraded", "down"]
    database: bool
    bot_running: bool
    maintenance_mode: bool
    uptime_seconds: float
    version: str
    checked_at: datetime
