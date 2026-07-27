"""add conversation message sequence

Revision ID: ff0479611628
Revises: bc578604bcb4
Create Date: 2026-07-26 05:27:44.718859

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.

revision: str = "ff0479611628"
down_revision: str | None = "bc578604bcb4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_conversation_messages",
        sa.Column(
            "sequence_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Existing records did not have a reliable sequence. The best possible
    # backfill is the previous created_at/id ordering.
    op.execute(
        """
        WITH ranked_messages AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY conversation_id
                    ORDER BY created_at ASC, id ASC
                ) AS calculated_sequence
            FROM document_conversation_messages
        )
        UPDATE document_conversation_messages AS message
        SET sequence_number = ranked.calculated_sequence
        FROM ranked_messages AS ranked
        WHERE message.id = ranked.id
        """
    )

    op.alter_column(
        "document_conversation_messages",
        "sequence_number",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        (
            "uq_document_conversation_messages_"
            "conversation_sequence"
        ),
        "document_conversation_messages",
        [
            "conversation_id",
            "sequence_number",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        (
            "uq_document_conversation_messages_"
            "conversation_sequence"
        ),
        "document_conversation_messages",
        type_="unique",
    )

    op.drop_column(
        "document_conversation_messages",
        "sequence_number",
    )