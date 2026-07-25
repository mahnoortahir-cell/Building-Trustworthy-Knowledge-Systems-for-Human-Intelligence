"""enable vector extension

Revision ID: c33224c7fae2
Revises: ba36de604146
Create Date: 2026-07-25 09:30:44.339233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c33224c7fae2'
down_revision: Union[str, Sequence[str], None] = 'ba36de604146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )


def downgrade() -> None:
    op.execute(
        "DROP EXTENSION IF EXISTS vector"
    )