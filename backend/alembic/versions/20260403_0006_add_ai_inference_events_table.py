"""add ai_inference_events table

Persist all AI inference events from Redis to Postgres for audit and analysis.
Includes JSONB columns for caller attribution, tool_calls, and full payload.

Revision ID: 20260403_0006
Revises: 20260327_0005
Create Date: 2026-04-03

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision: str = "20260403_0006"
down_revision: Union[str, None] = "20260327_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_inference_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_msg_id",
            sa.String(),
            nullable=False,
            unique=True,
            comment="Redis XADD message ID for dedup",
        ),
        # Core event metadata
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            comment="Service: caddy, ai_service, ai_service_adk, backend",
        ),
        sa.Column(
            "kind",
            sa.String(),
            nullable=False,
            comment="Event type: claims_candidate, gmail_step_judge, etc.",
        ),
        sa.Column(
            "backend",
            sa.String(),
            nullable=False,
            comment="AI backend: crewai, google_adk, local_vllm, n/a",
        ),
        # Session and request correlation
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        # User attribution
        sa.Column("username", sa.String(), nullable=True),
        # Agent caller attribution (JSONB)
        sa.Column(
            "caller",
            JSONB(),
            nullable=True,
            comment="Agent attribution: agent, role, stage, attempt, model",
        ),
        # Tool calls (JSONB array)
        sa.Column(
            "tool_calls",
            JSONB(),
            nullable=True,
            comment="List of tool invocations with args, results, reason taxonomy",
        ),
        # Optional question(s), reasoning, plan fields
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column(
            "questions",
            JSONB(),
            nullable=True,
            comment="Array of question strings",
        ),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "plan",
            JSONB(),
            nullable=True,
            comment="Agent plan or step list",
        ),
        # Full event payload
        sa.Column("payload", JSONB(), nullable=False),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "ix_ai_inference_events_session_id",
        "ai_inference_events",
        ["session_id"],
    )
    op.create_index(
        "ix_ai_inference_events_kind",
        "ai_inference_events",
        ["kind"],
    )
    op.create_index(
        "ix_ai_inference_events_recorded_at",
        "ai_inference_events",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_inference_events_recorded_at", table_name="ai_inference_events"
    )
    op.drop_index("ix_ai_inference_events_kind", table_name="ai_inference_events")
    op.drop_index("ix_ai_inference_events_session_id", table_name="ai_inference_events")
    op.drop_table("ai_inference_events")
