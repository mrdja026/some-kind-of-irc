"""add claims_visible and claims_debug tables

Revision ID: 20260327_0004
Revises: 20260321_0003
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "20260327_0004"
down_revision: Union[str, None] = "20260321_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claims_visible_sessions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("claim_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("flags", JSONB(), nullable=True),
        sa.Column("turn_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_claims_visible_sessions_claim_id",
        "claims_visible_sessions",
        ["claim_id"],
    )
    op.create_index(
        "ix_claims_visible_sessions_username",
        "claims_visible_sessions",
        ["username"],
    )
    op.create_index(
        "ix_claims_visible_sessions_created_at",
        "claims_visible_sessions",
        ["created_at"],
    )

    op.create_table(
        "claims_visible_turns",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("tool_calls", JSONB(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("next_question", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["claims_visible_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "turn_number", name="uq_session_turn"),
    )
    op.create_index(
        "ix_claims_visible_turns_session_id",
        "claims_visible_turns",
        ["session_id"],
    )

    op.create_table(
        "claims_debug_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_kind", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["claims_visible_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_claims_debug_events_session_id",
        "claims_debug_events",
        ["session_id"],
    )
    op.create_index(
        "ix_claims_debug_events_event_kind",
        "claims_debug_events",
        ["event_kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_claims_debug_events_event_kind", table_name="claims_debug_events")
    op.drop_index("ix_claims_debug_events_session_id", table_name="claims_debug_events")
    op.drop_table("claims_debug_events")

    op.drop_index("ix_claims_visible_turns_session_id", table_name="claims_visible_turns")
    op.drop_table("claims_visible_turns")

    op.drop_index("ix_claims_visible_sessions_created_at", table_name="claims_visible_sessions")
    op.drop_index("ix_claims_visible_sessions_username", table_name="claims_visible_sessions")
    op.drop_index("ix_claims_visible_sessions_claim_id", table_name="claims_visible_sessions")
    op.drop_table("claims_visible_sessions")
