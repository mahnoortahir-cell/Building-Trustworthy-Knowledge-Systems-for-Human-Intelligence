"""add conversation pinning

Revision ID: ac959336af40
Revises: ff0479611628
Create Date: 2026-07-27

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "ac959336af40"
down_revision: str | None = "ff0479611628"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_conversations",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.add_column(
        "document_conversations",
        sa.Column(
            "pinned_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_document_conversations_is_pinned",
        "document_conversations",
        ["is_pinned"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_conversations_is_pinned",
        table_name="document_conversations",
    )

    op.drop_column(
        "document_conversations",
        "pinned_at",
    )

    op.drop_column(
        "document_conversations",
        "is_pinned",
    )
