"""add unique constraint on claims_debug_events for dedup

Revision ID: 20260327_0005
Revises: 20260327_0004
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260327_0005"
down_revision: Union[str, None] = "20260327_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_debug_event_dedup",
        "claims_debug_events",
        ["session_id", "event_kind", "recorded_at", "request_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_debug_event_dedup", "claims_debug_events", type_="unique")
