"""DTOهای کاربر با Pydantic v2."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from anonchat.core.security import (
    sanitize_bio,
    sanitize_nickname,
    validate_age,
    validate_country_code,
    validate_interests,
    validate_language_code,
)

Gender = Literal["male", "female", "other", "unspecified"]


class UserCreateDTO(BaseModel):
    """DTO ایجاد کاربر اولیه."""

    telegram_id: int
    referral_code: str
    language: str = "fa"
    referred_by_code: str | None = None


class RegistrationDTO(BaseModel):
    """DTO تکمیل ثبت‌نام — اعتبارسنجی کامل ورودی."""

    nickname: str = Field(..., min_length=2, max_length=30)
    gender: Gender = "unspecified"
    age: int = Field(..., ge=13, le=120)
    country: str = Field(..., min_length=2, max_length=2)
    language: str = "fa"
    bio: str | None = Field(None, max_length=300)
    interests: list[str] = Field(default_factory=list, max_length=15)

    @field_validator("nickname")
    @classmethod
    def _valid_nickname(cls, v: str) -> str:
        return sanitize_nickname(v)

    @field_validator("bio")
    @classmethod
    def _valid_bio(cls, v: str | None) -> str | None:
        return sanitize_bio(v) if v else None

    @field_validator("country")
    @classmethod
    def _valid_country(cls, v: str) -> str:
        return validate_country_code(v)

    @field_validator("language")
    @classmethod
    def _valid_language(cls, v: str) -> str:
        return validate_language_code(v)

    @field_validator("interests")
    @classmethod
    def _valid_interests(cls, v: list[str]) -> list[str]:
        return validate_interests(v)


class ProfileUpdateDTO(BaseModel):
    """DTO به‌روزرسانی پروفایل — همه‌ی فیلدها اختیاری."""

    nickname: str | None = None
    bio: str | None = None
    gender: Gender | None = None
    age: int | None = None
    country: str | None = None
    language: str | None = None
    interests: list[str] | None = None
    profile_photo_file_id: str | None = None

    @field_validator("nickname")
    @classmethod
    def _valid_nickname(cls, v: str | None) -> str | None:
        return sanitize_nickname(v) if v else None

    @field_validator("bio")
    @classmethod
    def _valid_bio(cls, v: str | None) -> str | None:
        return sanitize_bio(v) if v else None

    @field_validator("age")
    @classmethod
    def _valid_age(cls, v: int | None) -> int | None:
        return validate_age(v) if v is not None else None

    @field_validator("country")
    @classmethod
    def _valid_country(cls, v: str | None) -> str | None:
        return validate_country_code(v) if v else None


class PrivacySettingsDTO(BaseModel):
    """DTO تنظیمات حریم خصوصی."""

    show_age: bool = True
    show_country: bool = True
    show_gender: bool = True
    notifications_enabled: bool = True


class UserPublicDTO(BaseModel):
    """DTO عمومی پروفایل کاربر — فیلدهای حریم خصوصی حذف می‌شوند."""

    model_config = ConfigDict(from_attributes=True)

    nickname: str | None
    gender: str
    age: int | None
    country: str | None
    language: str
    bio: str | None
    interests: list[str] = Field(default_factory=list)
    level: int
    xp: int
    referral_code: str
    total_chats: int
    is_online: bool

    @classmethod
    def from_user(cls, user, *, viewer_is_self: bool = False) -> UserPublicDTO:
        """ساخت DTO از مدل کاربر با احترام به تنظیمات حریم خصوصی."""
        interests = user.interests.split(",") if user.interests else []
        interests = [i.strip() for i in interests if i.strip()]
        return cls(
            nickname=user.nickname,
            gender=user.gender if (user.show_gender or viewer_is_self) else "unspecified",
            age=user.age if (user.show_age or viewer_is_self) else None,
            country=user.country if (user.show_country or viewer_is_self) else None,
            language=user.language,
            bio=user.bio,
            interests=interests,
            level=user.level,
            xp=user.xp,
            referral_code=user.referral_code,
            total_chats=user.total_chats,
            is_online=user.is_online,
        )


class UserResponseDTO(BaseModel):
    """DTO کامل پاسخ کاربر (برای مدیر)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    nickname: str | None
    gender: str
    age: int | None
    country: str | None
    language: str
    bio: str | None
    is_registered: bool
    is_online: bool
    is_blocked: bool
    is_admin: bool
    xp: int
    level: int
    referral_code: str
    risk_score: int
    warnings_count: int
    total_chats: int
    total_messages_sent: int
    total_messages_received: int
    created_at: datetime
    last_seen: datetime
