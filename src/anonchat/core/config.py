"""لایه پیکربندی متمرکز پروژه سایه.

این ماژول تمام متغیرهای محیطی را با اعتبارسنجی Pydantic Settings
بارگذاری و تایپ-سیف می‌کند. هیچ بخش دیگری از کد نباید مستقیماً
``os.environ`` را بخواند — همیشه از ``get_settings`` استفاده شود.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """تنظیمات جهانی ربات، بارگذاری‌شده از متغیرهای محیطی و ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram -----------------------------------------------------------
    bot_token: SecretStr = Field(..., description="توکن ربات از BotFather")
    admin_ids: list[int] = Field(
        default_factory=list,
        description="شناسه عددی مدیران، با کاما جدا می‌شود",
    )

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/saya.db",
        description="آدرس اتصال به پایگاه داده",
    )

    # --- Webhook ------------------------------------------------------------
    use_webhook: bool = False
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path: str = "/webhook"

    # --- Chat behaviour -----------------------------------------------------
    max_text_length: int = 4000
    chat_idle_timeout_minutes: int = 15
    auto_ban_report_threshold: int = 5
    auto_ban_duration_hours: int = 24

    # --- Security / rate limiting ------------------------------------------
    rate_limit_messages: int = 20
    rate_limit_window: int = 60
    risk_score_threshold: int = 80

    # --- Matchmaking --------------------------------------------------------
    match_queue_timeout: int = 60
    recent_partner_history: int = 10

    # --- Social / referral --------------------------------------------------
    referral_reward_xp: int = 50
    daily_login_xp: int = 10

    # --- Maintenance --------------------------------------------------------
    maintenance_mode: bool = False

    # --- Logging ------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    # --- i18n ---------------------------------------------------------------
    default_locale: Literal["fa", "en"] = "fa"

    # --- Runtime ------------------------------------------------------------
    health_port: int = 8080
    user_cache_ttl: int = 300

    # ------------------------------------------------------------------ #
    #  اعتبارسنجی‌های سفارشی
    # ------------------------------------------------------------------ #

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: str | list[int] | None) -> list[int]:
        """تبدیل رشته‌ی «1,2,3» به لیست عددی."""
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value if str(v).strip()]
        parts = [p.strip() for p in str(value).split(",") if p.strip()]
        return [int(p) for p in parts]

    @field_validator("bot_token")
    @classmethod
    def _validate_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if ":" not in token or not token.split(":")[0].isdigit():
            raise ValueError(
                "BOT_TOKEN معتبر نیست — باید در قالب «123456:ABC-DEF» باشد."
            )
        return value

    @model_validator(mode="after")
    def _validate_admins_required(self) -> Settings:
        if not self.admin_ids:
            raise ValueError("حداقل یک ADMIN_IDS باید مشخص شود.")
        return self

    # ------------------------------------------------------------------ #
    #  پراپرتی‌های کمکی
    # ------------------------------------------------------------------ #

    @property
    def is_sqlite(self) -> bool:
        """آیا پایگاه داده فعلی SQLite است؟"""
        return self.database_url.startswith("sqlite")

    @property
    def token(self) -> str:
        """مقدار رشته‌ای توکن."""
        return self.bot_token.get_secret_value()

    @property
    def is_admin_configured(self) -> bool:
        return len(self.admin_ids) > 0

    def is_admin(self, user_id: int) -> bool:
        """بررسی اینکه آیا کاربر مدیر است."""
        return user_id in self.admin_ids


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton تنظیمات — یک‌بار محاسبه و کش می‌شود.

    برای تست‌ها می‌توان با ``get_settings.cache_clear()`` کش را پاک کرد.
    """
    return Settings()  # type: ignore[call-arg]


# نمونه‌ی ماژول‌سطح برای ایمپورت مستقیم (در صورت نیاز)
settings = get_settings()
