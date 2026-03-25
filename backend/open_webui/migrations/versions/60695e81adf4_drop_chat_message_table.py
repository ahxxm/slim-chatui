"""drop chat_message table

Revision ID: 60695e81adf4
Revises: cb611f7fb096
Create Date: 2026-03-25 21:16:19.471645

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = "60695e81adf4"
down_revision: Union[str, None] = "cb611f7fb096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("chat_message")


def downgrade() -> None:
    op.create_table(
        "chat_message",
        sa.Column("id", sa.TEXT(), nullable=False),
        sa.Column("chat_id", sa.TEXT(), nullable=False),
        sa.Column("user_id", sa.TEXT(), nullable=True),
        sa.Column("role", sa.TEXT(), nullable=False),
        sa.Column("parent_id", sa.TEXT(), nullable=True),
        sa.Column("content", sqlite.JSON(), nullable=True),
        sa.Column("output", sqlite.JSON(), nullable=True),
        sa.Column("model_id", sa.TEXT(), nullable=True),
        sa.Column("files", sqlite.JSON(), nullable=True),
        sa.Column("sources", sqlite.JSON(), nullable=True),
        sa.Column("done", sa.BOOLEAN(), nullable=True),
        sa.Column("status_history", sqlite.JSON(), nullable=True),
        sa.Column("error", sqlite.JSON(), nullable=True),
        sa.Column("usage", sqlite.JSON(), nullable=True),
        sa.Column("created_at", sa.BIGINT(), nullable=True),
        sa.Column("updated_at", sa.BIGINT(), nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chat.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_message_user_id", "chat_message", ["user_id"])
    op.create_index("ix_chat_message_model_id", "chat_message", ["model_id"])
    op.create_index("ix_chat_message_created_at", "chat_message", ["created_at"])
    op.create_index("ix_chat_message_chat_id", "chat_message", ["chat_id"])
    op.create_index(
        "chat_message_user_created_idx", "chat_message", ["user_id", "created_at"]
    )
    op.create_index(
        "chat_message_model_created_idx", "chat_message", ["model_id", "created_at"]
    )
    op.create_index(
        "chat_message_chat_parent_idx", "chat_message", ["chat_id", "parent_id"]
    )
