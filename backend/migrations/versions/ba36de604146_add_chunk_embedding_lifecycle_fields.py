"""add chunk embedding lifecycle fields

Revision ID: ba36de604146
Revises: adc045146b2d
Create Date: 2026-07-25 08:17:22.696746

"""
from sqlalchemy.dialects import postgresql
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba36de604146'
down_revision: Union[str, Sequence[str], None] = 'adc045146b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        embedding_status_type = postgresql.ENUM(
            "pending",
            "processing",
            "completed",
            "failed",
            name="embeddingstatus",
        )

        embedding_status_type.create(
            bind,
            checkfirst=True,
        )

        column_type = postgresql.ENUM(
            "pending",
            "processing",
            "completed",
            "failed",
            name="embeddingstatus",
            create_type=False,
        )
    else:
        column_type = sa.Enum(
            "pending",
            "processing",
            "completed",
            "failed",
            name="embeddingstatus",
        )

    with op.batch_alter_table(
        "document_chunks",
        schema=None,
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "embedding_status",
                column_type,
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column(
                "embedding_model",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "embedding_error",
                sa.Text(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "embedded_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )

    with op.batch_alter_table(
        "document_chunks",
        schema=None,
    ) as batch_op:
        batch_op.alter_column(
            "embedding_status",
            server_default=None,
        )


def downgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table(
        "document_chunks",
        schema=None,
    ) as batch_op:
        batch_op.drop_column("embedded_at")
        batch_op.drop_column("embedding_error")
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("embedding_status")

    if bind.dialect.name == "postgresql":
        embedding_status_type = postgresql.ENUM(
            "pending",
            "processing",
            "completed",
            "failed",
            name="embeddingstatus",
        )

        embedding_status_type.drop(
            bind,
            checkfirst=True,
        )