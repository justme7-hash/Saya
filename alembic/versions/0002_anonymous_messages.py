"""add anonymous messages table

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "anonymous_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("recipient_id", sa.Integer(), nullable=False, index=True),
        sa.Column("sender_telegram_id", sa.Integer(), nullable=False, index=True),
        sa.Column("sender_display_name", sa.String(32), nullable=False, server_default="ناشناس"),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("file_id", sa.String(255), nullable=True),
        sa.Column("file_unique_id", sa.String(255), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_reply", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False, server_default="in"),
        sa.Column("forwarded_to_chat_id", sa.Integer(), nullable=True),
        sa.Column("telegram_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reply_to_id"], ["anonymous_messages.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("anonymous_messages")
