"""add conversation soft delete

Revision ID: e7b1d9f4a2c8
Revises: c5b30792f4cf
Create Date: 2026-07-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b1d9f4a2c8"
down_revision: Union[str, Sequence[str], None] = (
    "c5b30792f4cf"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_conversations",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "document_conversations",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_document_conversations_is_deleted"),
        "document_conversations",
        ["is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_conversations_is_deleted"),
        table_name="document_conversations",
    )
    op.drop_column(
        "document_conversations",
        "deleted_at",
    )
    op.drop_column(
        "document_conversations",
        "is_deleted",
    )
