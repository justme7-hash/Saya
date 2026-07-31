"""لایه‌ی مخازن."""

from anonchat.db.repositories.ban_repo import BanRepository
from anonchat.db.repositories.base import BaseRepository
from anonchat.db.repositories.chat_repo import ChatRepository
from anonchat.db.repositories.favorite_repo import FavoriteRepository
from anonchat.db.repositories.referral_repo import ReferralRepository
from anonchat.db.repositories.report_repo import ReportRepository
from anonchat.db.repositories.stats_repo import StatsRepository
from anonchat.db.repositories.user_repo import UserRepository

__all__ = [
    "BanRepository",
    "BaseRepository",
    "ChatRepository",
    "FavoriteRepository",
    "ReferralRepository",
    "ReportRepository",
    "StatsRepository",
    "UserRepository",
]
