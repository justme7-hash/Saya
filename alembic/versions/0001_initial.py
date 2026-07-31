"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.Integer(), nullable=False, unique=True, index=True),
        sa.Column("nickname", sa.String(30), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("gender", sa.String(16), nullable=False, server_default="unspecified"),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="fa"),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("profile_photo_file_id", sa.String(255), nullable=True),
        sa.Column("show_age", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("show_country", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("show_gender", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_searching", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_in_chat", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("referral_code", sa.String(16), nullable=False, unique=True, index=True),
        sa.Column("referred_by_id", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_chats", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_messages_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_messages_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.id"], ondelete="SET NULL"),
    )

    # chat_sessions
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("partner_id", sa.Integer(), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active", index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(32), nullable=True),
        sa.Column("ended_by", sa.Integer(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ended_by"], ["users.id"], ondelete="SET NULL"),
    )

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_session_id", sa.Integer(), nullable=False, index=True),
        sa.Column("sender_id", sa.Integer(), nullable=False, index=True),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("text_length", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("content_preview", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(255), nullable=True),
        sa.Column("file_unique_id", sa.String(255), nullable=True),
        sa.Column("is_forwarded", sa.String(5), nullable=False, server_default="false"),
        sa.Column("is_reply", sa.String(5), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
    )

    # reports
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.Integer(), nullable=False, index=True),
        sa.Column("reported_id", sa.Integer(), nullable=False, index=True),
        sa.Column("chat_session_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reported_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )

    # bans
    op.create_table(
        "bans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("is_permanent", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("banned_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("banned_by", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("unbanned_by", sa.Integer(), nullable=True),
        sa.Column("unbanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["banned_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["unbanned_by"], ["users.id"], ondelete="SET NULL"),
    )

    # favorites
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("favorite_user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["favorite_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "favorite_user_id", name="uq_favorites_pair"),
    )

    # referrals
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("referrer_id", sa.Integer(), nullable=False, index=True),
        sa.Column("referred_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("reward_given", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reward_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["referred_id"], ["users.id"], ondelete="CASCADE"),
    )

    # achievements
    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(16), nullable=False, server_default="🏆"),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("category", sa.String(32), nullable=False, server_default="general"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # user_achievements
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )

    # settings
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("value_type", sa.String(16), nullable=False, server_default="string"),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # daily_missions
    op.create_table(
        "daily_missions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("xp_reward", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # security_logs
    op.create_table(
        "security_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True, index=True),
        sa.Column("event_type", sa.String(32), nullable=False, index=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.Integer(), nullable=True, index=True),
        sa.Column("action", sa.String(32), nullable=False, index=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("security_logs")
    op.drop_table("daily_missions")
    op.drop_table("settings")
    op.drop_table("user_achievements")
    op.drop_table("achievements")
    op.drop_table("referrals")
    op.drop_table("favorites")
    op.drop_table("bans")
    op.drop_table("reports")
    op.drop_table("messages")
    op.drop_table("chat_sessions")
    op.drop_table("users")
