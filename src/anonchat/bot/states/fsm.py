"""تعریف وضعیت‌های FSM (Finite State Machine) برای جریان‌های تعاملی."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """وضعیت‌های فرآیند ثبت‌نام."""

    waiting_nickname = State()
    waiting_gender = State()
    waiting_age = State()
    waiting_country = State()
    waiting_bio = State()
    waiting_interests = State()


class SearchStates(StatesGroup):
    """وضعیت‌های جستجوی مخاطب."""

    choosing_criteria = State()
    waiting_gender_pref = State()
    waiting_country_pref = State()
    waiting_language_pref = State()
    waiting_age_range = State()
    in_queue = State()


class ChatStates(StatesGroup):
    """وضعیت‌های گفتگو."""

    chatting = State()
    rating = State()
    reporting = State()


class ProfileEditStates(StatesGroup):
    """وضعیت‌های ویرایش پروفایل."""

    choosing_field = State()
    editing_nickname = State()
    editing_bio = State()
    editing_age = State()
    editing_country = State()
    editing_interests = State()


class AdminStates(StatesGroup):
    """وضعیت‌های پنل مدیریت."""

    waiting_broadcast_text = State()
    waiting_ban_input = State()
    waiting_unban_input = State()


class AnonymousStates(StatesGroup):
    """وضعیت‌های پیام ناشناس."""

    composing_message = State()
    """فرستنده در حال نوشتن پیام ناشناس."""

    replying = State()
    """صاحب لینک در حال پاسخ به پیام ناشناس."""

    waiting_forward_target = State()
    """صاحب لینک در حال انتخاب مقصد فوروارد."""

    viewing_inbox = State()
    """صاحب لینک در حال مشاهده‌ی صندوق پیام‌های ناشناس."""
