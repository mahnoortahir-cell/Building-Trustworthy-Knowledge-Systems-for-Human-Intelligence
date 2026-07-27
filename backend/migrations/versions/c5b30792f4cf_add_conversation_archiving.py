"""add conversation archiving

Revision ID: c5b30792f4cf
Revises: ac959336af40
Create Date: 2026-07-28 01:51:01.531906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5b30792f4cf'
down_revision: Union[str, Sequence[str], None] = 'ac959336af40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_conversations",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "document_conversations",
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_document_conversations_is_archived"),
        "document_conversations",
        ["is_archived"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_document_conversations_is_archived"),
        table_name="document_conversations",
    )
    op.drop_column(
        "document_conversations",
        "archived_at",
    )
    op.drop_column(
        "document_conversations",
        "is_archived",
    )
