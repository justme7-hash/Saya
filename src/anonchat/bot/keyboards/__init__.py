"""کیبوردهای اینلاین و ریپلای ربات.

تمام دکمه‌ها از این لایه ساخته می‌شوند تا:
- یکپارچگی ظاهری حفظ شود
- تغییر متن دکمه در یک مکان امکان‌پذیر باشد
- پشتیبانی از i18n
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from anonchat.i18n import t

# ---------------------------------------------------------------------------
#  کیبوردهای ریپلای (منوی اصلی)
# ---------------------------------------------------------------------------

def main_menu(locale: str = "fa") -> ReplyKeyboardMarkup:
    """منوی اصلی ربات."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("start_chat_button", locale)),
                KeyboardButton(text=t("settings_button", locale)),
            ],
            [
                KeyboardButton(text=t("profile_button", locale)),
                KeyboardButton(text=t("stats_button", locale)),
            ],
            [
                KeyboardButton(text="🔗 لینک ناشناس من"),
                KeyboardButton(text=t("referral_button", locale)),
            ],
            [
                KeyboardButton(text=t("help_button", locale)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard(locale: str = "fa") -> ReplyKeyboardMarkup:
    """کیبورد لغو."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("cancel_button", locale))]],
        resize_keyboard=True,
    )


def chat_keyboard(locale: str = "fa") -> ReplyKeyboardMarkup:
    """کیبورد فعال در حین گفتگو."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("chat_end", locale)),
                KeyboardButton(text=t("chat_find_new", locale)),
            ],
            [
                KeyboardButton(text=t("chat_report", locale)),
                KeyboardButton(text=t("chat_favorite", locale)),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ---------------------------------------------------------------------------
#  کیبوردهای اینلاین
# ---------------------------------------------------------------------------

def start_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """کیبورد شروع (ثبت‌نام یا شروع گفتگو)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("register_button", locale), callback_data="register")],
        ]
    )


def search_criteria_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """انتخاب معیار جستجو."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("search_random", locale), callback_data="search_random")],
            [InlineKeyboardButton(text=t("search_by_gender", locale), callback_data="search_gender")],
            [InlineKeyboardButton(text=t("search_by_country", locale), callback_data="search_country")],
            [InlineKeyboardButton(text=t("search_by_language", locale), callback_data="search_language")],
            [InlineKeyboardButton(text=t("search_by_age", locale), callback_data="search_age")],
        ]
    )


def gender_keyboard(locale: str = "fa", prefix: str = "gender") -> InlineKeyboardMarkup:
    """انتخاب جنسیت."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("reg_gender_male", locale), callback_data=f"{prefix}_male"),
                InlineKeyboardButton(text=t("reg_gender_female", locale), callback_data=f"{prefix}_female"),
            ],
            [
                InlineKeyboardButton(text=t("reg_gender_other", locale), callback_data=f"{prefix}_other"),
                InlineKeyboardButton(text=t("reg_gender_unspecified", locale), callback_data=f"{prefix}_unspecified"),
            ],
        ]
    )


def report_reason_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """انتخاب دلیل گزارش."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("report_spam", locale), callback_data="report_spam")],
            [InlineKeyboardButton(text=t("report_harassment", locale), callback_data="report_harassment")],
            [InlineKeyboardButton(text=t("report_nsfw", locale), callback_data="report_nsfw")],
            [InlineKeyboardButton(text=t("report_scam", locale), callback_data="report_scam")],
            [InlineKeyboardButton(text=t("report_violence", locale), callback_data="report_violence")],
            [InlineKeyboardButton(text=t("report_other", locale), callback_data="report_other")],
        ]
    )


def rating_keyboard(locale: str = "fa", session_id: int = 0) -> InlineKeyboardMarkup:
    """امتیاز دادن به گفتگو.

    ``session_id`` در ``callback_data`` دکمه‌ها قرار می‌گیرد تا هندلر امتیازدهی
    بدون نیاز به state بتواند آن را بخواند. این الگو قابل‌اعتمادتر از state
    است چون ``end_chat`` در پایان state را پاک می‌کند.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐", callback_data=f"rate_1_{session_id}"),
                InlineKeyboardButton(text="⭐⭐", callback_data=f"rate_2_{session_id}"),
                InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"rate_3_{session_id}"),
            ],
            [
                InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"rate_4_{session_id}"),
                InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"rate_5_{session_id}"),
            ],
        ]
    )


def language_keyboard() -> InlineKeyboardMarkup:
    """انتخاب زبان."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang_fa"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
            ]
        ]
    )


def privacy_keyboard(locale: str = "fa", settings: dict | None = None) -> InlineKeyboardMarkup:
    """کیبورد تنظیمات حریم خصوصی.

    برای hide_from_search، منطق برعکس است: ✅ یعنی «نمایش در جستجو» (یعنی hide=False)،
    ❌ یعنی «مخفی از جستجو» (یعنی hide=True).
    """
    s = settings or {}
    def toggle(field: str, label_key: str) -> InlineKeyboardButton:
        on = s.get(field, True)
        marker = "✅" if on else "❌"
        return InlineKeyboardButton(
            text=f"{marker} {t(label_key, locale)}",
            callback_data=f"privacy_{field}",
        )

    # دکمه‌ی مخفی کردن از جستجو (منطق برعکس)
    hide = s.get("hide_from_search", False)
    # اگر hide_from_search=False → ✅ نمایش در جستجو
    # اگر hide_from_search=True → ❌ مخفی از جستجو
    hide_marker = "❌" if hide else "✅"
    hide_button = InlineKeyboardButton(
        text=f"{hide_marker} {t('settings_show_in_search', locale)}",
        callback_data="privacy_hide_from_search",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle("show_age", "settings_show_age")],
            [toggle("show_country", "settings_show_country")],
            [toggle("show_gender", "settings_show_gender")],
            [toggle("notifications_enabled", "settings_notifications")],
            [hide_button],
        ]
    )


def settings_menu_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """منوی تنظیمات."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("settings_language", locale), callback_data="set_language")],
            [InlineKeyboardButton(text=t("settings_privacy", locale), callback_data="set_privacy")],
        ]
    )


def profile_edit_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """انتخاب فیلد ویرایش پروفایل."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("profile_nickname", locale), callback_data="edit_nickname"),
                InlineKeyboardButton(text=t("profile_age", locale), callback_data="edit_age"),
            ],
            [
                InlineKeyboardButton(text=t("profile_country", locale), callback_data="edit_country"),
                InlineKeyboardButton(text=t("profile_bio", locale), callback_data="edit_bio"),
            ],
            [InlineKeyboardButton(text=t("profile_interests", locale), callback_data="edit_interests")],
            [InlineKeyboardButton(text=t("reg_gender", locale), callback_data="edit_gender")],
            [InlineKeyboardButton(text=t("profile_back_button", locale), callback_data="profile_back")],
        ]
    )


def admin_panel_keyboard(locale: str = "fa") -> InlineKeyboardMarkup:
    """پنل مدیریت."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("admin_stats", locale), callback_data="admin_stats")],
            [InlineKeyboardButton(text=t("admin_users", locale), callback_data="admin_users")],
            [InlineKeyboardButton(text=t("admin_reports", locale), callback_data="admin_reports")],
            [
                InlineKeyboardButton(text=t("admin_ban", locale), callback_data="admin_ban"),
                InlineKeyboardButton(text=t("admin_broadcast", locale), callback_data="admin_broadcast"),
            ],
            [InlineKeyboardButton(text=t("admin_maintenance", locale), callback_data="admin_maintenance")],
        ]
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    """حذف کیبورد."""
    return ReplyKeyboardRemove()


# ---------------------------------------------------------------------------
#  کیبوردهای پیام ناشناس
# ---------------------------------------------------------------------------

def anon_message_keyboard(locale: str = "fa", msg_id: int = 0) -> InlineKeyboardMarkup:
    """کیبورد زیر پیام ناشناس دریافتی — برای صاحب لینک."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 پاسخ", callback_data=f"anon_reply_{msg_id}"),
                InlineKeyboardButton(text="📤 فوروارد", callback_data=f"anon_fwd_{msg_id}"),
            ],
            [InlineKeyboardButton(text="✅ خوانده‌شده", callback_data=f"anon_read_{msg_id}")],
        ]
    )


def anon_link_keyboard(locale: str = "fa", link: str = "") -> InlineKeyboardMarkup:
    """کیبورد نمایش لینک ناشناس با دکمه‌ی اشتراک‌گذاری.

    از switch_inline_query استفاده می‌کنیم تا کاربر بتواند لینک را در چت‌های
    دیگر اشتراک بگذارد (به‌جای باز کردن لینک خود ربات).
    دکمه‌ی کپی لینک هم callback می‌فرستد تا هندلر آن را به‌صورت پیام نمایش دهد.
    """
    buttons = []
    if link:
        # دکمه‌ی اشتراک‌گذاری: با switch_inline_query، تلگرام لیست چت‌ها را باز می‌کند
        # و لینک را به‌عنوان پیام آماده ارسال می‌گذارد
        buttons.append([
            InlineKeyboardButton(
                text="📤 اشتراک‌گذاری لینک",
                switch_inline_query=link,
            ),
        ])
        # دکمه‌ی کپی لینک: callback می‌فرستد، هندلر پیام با لینک می‌فرستد تا کاربر کپی کند
        buttons.append([
            InlineKeyboardButton(text="📋 نمایش لینک برای کپی", callback_data="anon_copy_link"),
        ])
    buttons.append([InlineKeyboardButton(text="📬 صندوق پیام‌ها", callback_data="anon_inbox")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def anon_forward_target_keyboard(locale: str = "fa", msg_id: int = 0) -> InlineKeyboardMarkup:
    """کیبورد انتخاب مقصد فوروارد."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📢 کانال من", callback_data=f"anon_fwd_channel_{msg_id}"),
                InlineKeyboardButton(text="👥 گروه من", callback_data=f"anon_fwd_group_{msg_id}"),
            ],
            [InlineKeyboardButton(text=t("cancel_button", locale), callback_data="anon_cancel")],
        ]
    )
