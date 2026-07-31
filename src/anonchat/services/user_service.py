"""سرویس کاربر — منطق کسب‌وکار کاربران.

این لایه بین Handler و Repository قرار دارد و تمام قوانین کسب‌وکار
کاربر (ثبت‌نام، پروفایل، تنظیمات، آمار) را کپسوله می‌کند.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anonchat.core.exceptions import (
    UserAlreadyRegisteredError,
    UserBannedError,
    UserNotFoundError,
)
from anonchat.core.logging import get_logger
from anonchat.core.security import generate_referral_code
from anonchat.schemas.user import (
    PrivacySettingsDTO,
    ProfileUpdateDTO,
    RegistrationDTO,
    UserPublicDTO,
)

if TYPE_CHECKING:
    from anonchat.core.container import Container


class UserService:
    """سرویس مدیریت کاربران."""

    def __init__(self, container: Container) -> None:
        self._container = container
        self._log = get_logger("service.user")
        self._cache = container.user_cache

    async def get_or_create(
        self, telegram_id: int, *, language: str = "fa", referral_code: str | None = None
    ) -> tuple[object, bool]:
        """دریافت کاربر یا ایجاد در صورت عدم وجود.

        Returns:
            تاپل (کاربر, ایجاد‌شده؟).
        """
        # بررسی کش
        cached = self._cache.get(telegram_id)
        if cached and cached.get("is_registered"):
            async with self._container.session_factory()() as session:
                repo = self._container.user_repo()
                repo.session = session
                user = await repo.get_by_telegram_id(telegram_id)
                if user is not None:
                    return user, False

        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is not None:
            return user, False

        # بررسی بن قبل از ایجاد
        ban_repo = self._container.ban_repo()
        existing_ban = await ban_repo.get_active_ban_by_telegram(telegram_id)
        if existing_ban is not None:
            raise UserBannedError(
                telegram_id,
                until=existing_ban.banned_until,
                reason=existing_ban.reason,
            )

        # یافتن معرف
        referred_by_id = None
        if referral_code:
            referrer = await repo.get_by_referral_code(referral_code)
            if referrer is not None:
                referred_by_id = referrer.id

        # ایجاد کاربر جدید با کد رفرال یکتا
        code = generate_referral_code(telegram_id)
        # اطمینان از یکتایی کد
        for _ in range(5):
            existing = await repo.get_by_referral_code(code)
            if existing is None:
                break
            code = generate_referral_code(telegram_id + telegram_id)

        user = await repo.create_user(
            telegram_id=telegram_id,
            referral_code=code,
            language=language,
            referred_by_id=referred_by_id,
        )
        await repo.commit()
        self._log.info(
            "user.created",
            telegram_id=telegram_id,
            referral_code=code,
            referred_by=referred_by_id,
        )
        return user, True

    async def complete_registration(
        self, telegram_id: int, dto: RegistrationDTO
    ) -> object:
        """تکمیل ثبت‌نام کاربر با اعتبارسنجی کامل."""
        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        if user.is_registered:
            raise UserAlreadyRegisteredError(telegram_id)

        interests_str = ",".join(dto.interests) if dto.interests else None
        updated = await repo.complete_registration(
            user.id,
            nickname=dto.nickname,
            gender=dto.gender,
            age=dto.age,
            country=dto.country,
            language=dto.language,
            bio=dto.bio,
            interests=interests_str,
            profile_photo_file_id=None,
        )
        await repo.commit()
        # ثبت رفرال و پاداش
        if user.referred_by_id is not None:
            await self._container.referral_service.process_referral_reward(
                referrer_id=user.referred_by_id, referred_id=user.id
            )
        # پاک کردن کش
        self._cache.pop(telegram_id, None)
        self._log.info("user.registered", telegram_id=telegram_id, nickname=dto.nickname)
        return updated

    async def update_profile(
        self, telegram_id: int, dto: ProfileUpdateDTO
    ) -> object:
        """به‌روزرسانی پروفایل کاربر."""
        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)

        fields = dto.model_dump(exclude_none=True)
        if "interests" in fields:
            fields["interests"] = ",".join(fields["interests"]) if fields["interests"] else None

        if fields:
            user = await repo.update(user, **fields)
            await repo.commit()
            self._cache.pop(telegram_id, None)
            self._log.info("user.profile_updated", telegram_id=telegram_id, fields=list(fields.keys()))
        return user

    async def update_privacy(
        self, telegram_id: int, dto: PrivacySettingsDTO
    ) -> object:
        """به‌روزرسانی تنظیمات حریم خصوصی."""
        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)

        user = await repo.update(
            user,
            show_age=dto.show_age,
            show_country=dto.show_country,
            show_gender=dto.show_gender,
            notifications_enabled=dto.notifications_enabled,
        )
        await repo.commit()
        self._cache.pop(telegram_id, None)
        return user

    async def get_profile(self, telegram_id: int) -> UserPublicDTO:
        """دریافت پروفایل عمومی کاربر."""
        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        return UserPublicDTO.from_user(user, viewer_is_self=True)

    async def get_public_profile(self, user_id: int) -> UserPublicDTO:
        """دریافت پروفایل عمومی یک کاربر (با احترام به حریم خصوصی)."""
        repo = self._container.user_repo()
        user = await repo.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return UserPublicDTO.from_user(user, viewer_is_self=False)

    async def set_online(self, telegram_id: int, online: bool) -> None:
        """تنظیم وضعیت آنلاین."""
        repo = self._container.user_repo()
        await repo.set_online_by_telegram(telegram_id, online)
        await repo.commit()

    async def check_ban_status(self, telegram_id: int) -> None:
        """بررسی وضعیت بن — در صورت بن بودن استثنا پرتاب می‌کند."""
        ban_repo = self._container.ban_repo()
        ban = await ban_repo.get_active_ban_by_telegram(telegram_id)
        if ban is not None:
            raise UserBannedError(
                telegram_id,
                until=ban.banned_until,
                reason=ban.reason,
            )

    async def add_xp(self, telegram_id: int, amount: int) -> int:
        """افزودن XP و بازگرداندن سطح جدید."""
        repo = self._container.user_repo()
        user = await repo.add_xp_by_telegram(telegram_id, amount)
        if user is None:
            raise UserNotFoundError(telegram_id)
        await repo.commit()
        return user.level

    async def get_by_telegram_id(self, telegram_id: int) -> object:
        """دریافت کاربر بر اساس شناسه تلگرام."""
        repo = self._container.user_repo()
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            raise UserNotFoundError(telegram_id)
        return user
