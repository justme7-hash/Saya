"""بسته‌ی مدل‌ها — ثبت تمام مدل‌ها در یک مکان برای MetaData."""

from __future__ import annotations

from anonchat.models.achievement import Achievement, UserAchievement
from anonchat.models.anonymous_message import AnonymousMessage
from anonchat.models.ban import Ban
from anonchat.models.chat import ChatSession
from anonchat.models.favorite import Favorite
from anonchat.models.message import Message
from anonchat.models.referral import Referral
from anonchat.models.report import Report
from anonchat.models.security_log import AuditLog, SecurityLog
from anonchat.models.settings import DailyMission, Setting
from anonchat.models.user import User

__all_models__ = [
    User,
    ChatSession,
    Message,
    Report,
    Ban,
    Favorite,
    Referral,
    Achievement,
    UserAchievement,
    Setting,
    DailyMission,
    SecurityLog,
    AuditLog,
    AnonymousMessage,
]

__all__ = [
    "Achievement",
    "AnonymousMessage",
    "AuditLog",
    "Ban",
    "ChatSession",
    "DailyMission",
    "Favorite",
    "Message",
    "Referral",
    "Report",
    "SecurityLog",
    "Setting",
    "User",
    "UserAchievement",
    "__all_models__",
]
