"""dedup constraint superseded by stream_msg_id in migration 0004

The original intent of this migration was to add a unique constraint on
(session_id, event_kind, recorded_at, request_id) for debug event dedup.
That approach is unsafe because PostgreSQL does not treat NULL values as equal
in unique constraints, so rows with request_id=NULL would not be deduplicated.

Migration 20260327_0004 was updated to instead use a (session_id, stream_msg_id)
constraint (uq_debug_event_stream_msg) where stream_msg_id is the Redis XADD
message ID — always non-null and unique per message.  This migration is retained
as a no-op to preserve the revision chain.

Revision ID: 20260327_0005
Revises: 20260327_0004
Create Date: 2026-03-27

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "20260327_0005"
down_revision: Union[str, None] = "20260327_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: the dedup constraint is now uq_debug_event_stream_msg, created in
    # migration 20260327_0004 alongside the table itself.
    pass


def downgrade() -> None:
    pass
