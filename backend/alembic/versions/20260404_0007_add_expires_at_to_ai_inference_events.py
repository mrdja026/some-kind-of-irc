"""add expires_at column to ai_inference_events

Retroactive fix: migration 0006 was amended after initial deployment to include
the expires_at column, but Alembic won't re-run an already-applied migration.
This migration adds the column idempotently so it works regardless of whether
the table already has the column.

Revision ID: 20260404_0007
Revises: 20260403_0006
Create Date: 2026-04-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260404_0007"
down_revision: Union[str, None] = "20260403_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check whether a column already exists in the given table."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column"
        ),
        {"table": table, "column": column},
    )
    return result.scalar() is not None


def _index_exists(index_name: str) -> bool:
    """Check whether an index already exists."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.scalar() is not None


def upgrade() -> None:
    if not _column_exists("ai_inference_events", "expires_at"):
        op.add_column(
            "ai_inference_events",
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=True,
                comment="Retention deadline; rows past this timestamp may be purged",
            ),
        )

    if not _index_exists("ix_ai_inference_events_expires_at"):
        op.create_index(
            "ix_ai_inference_events_expires_at",
            "ai_inference_events",
            ["expires_at"],
            postgresql_where=sa.text("expires_at IS NOT NULL"),
        )

    # Backfill rows written before this migration (90-day TTL from creation)
    op.execute(
        sa.text(
            "UPDATE ai_inference_events "
            "SET expires_at = created_at + INTERVAL '90 days' "
            "WHERE expires_at IS NULL"
        )
    )


def downgrade() -> None:
    if _index_exists("ix_ai_inference_events_expires_at"):
        op.drop_index(
            "ix_ai_inference_events_expires_at",
            table_name="ai_inference_events",
        )

    if _column_exists("ai_inference_events", "expires_at"):
        op.drop_column("ai_inference_events", "expires_at")
