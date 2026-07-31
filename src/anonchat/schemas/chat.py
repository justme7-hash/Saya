"""DTOهای گفتگو و جستجوی مخاطب."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Gender = Literal["male", "female", "other", "unspecified", "any"]


class SearchCriteriaDTO(BaseModel):
    """معیارهای جستجوی مخاطب."""

    gender: Gender = "any"
    country: str | None = None
    language: str | None = None
    age_min: int | None = Field(None, ge=13, le=120)
    age_max: int | None = Field(None, ge=13, le=120)
    interests: list[str] = Field(default_factory=list, max_length=10)


class MatchResultDTO(BaseModel):
    """نتیجه‌ی مچ‌سازی."""

    matched: bool
    partner_telegram_id: int | None = None
    chat_session_id: int | None = None
    reason: str | None = None


class ChatSessionDTO(BaseModel):
    """DTO جلسه‌ی گفتگو."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    partner_id: int
    status: str
    started_at: datetime
    ended_at: datetime | None
    end_reason: str | None
    message_count: int
    rating: int | None


class RateChatDTO(BaseModel):
    """DTO امتیاز دادن به گفتگو."""

    rating: int = Field(..., ge=1, le=5)
    favorite: bool = False


class ReportDTO(BaseModel):
    """DTO ثبت گزارش."""

    reason: Literal["spam", "harassment", "nsfw", "scam", "violence", "other"]
    description: str | None = Field(None, max_length=500)
