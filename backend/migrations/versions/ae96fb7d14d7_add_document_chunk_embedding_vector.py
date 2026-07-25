"""add document chunk embedding vector

Revision ID: ae96fb7d14d7
Revises: c33224c7fae2
Create Date: 2026-07-25 09:42:07.610036

"""
from typing import Sequence, Union
import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op



# revision identifiers, used by Alembic.
revision: str = 'ae96fb7d14d7'
down_revision: Union[str, Sequence[str], None] = 'c33224c7fae2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.VECTOR(8),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "document_chunks",
        "embedding",
    )