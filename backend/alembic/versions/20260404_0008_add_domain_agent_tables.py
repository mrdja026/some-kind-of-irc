"""add gmail, calendar, and caddy domain tables

Adds domain-specific tables for routing AI inference events by kind.
The redis-log-sink consumer fans out events from Redis streams into
these tables alongside the generic ai_inference_events audit log.

Tables:
  - gmail_agent_events: gmail_* event kinds with extracted email fields
  - calendar_agent_events: calendar_* event kinds with event fields
  - caddy_log_events: HTTP warn/error logs from caddy:warn_error_logs

Revision ID: 20260404_0008
Revises: 20260404_0007
Create Date: 2026-04-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "20260404_0008"
down_revision: Union[str, None] = "20260404_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── gmail_agent_events ──────────────────────────────────────────
    op.create_table(
        "gmail_agent_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_msg_id",
            sa.String(),
            nullable=False,
            unique=True,
            comment="Redis XADD message ID for dedup",
        ),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column(
            "kind",
            sa.String(),
            nullable=False,
            comment="gmail_questions, gmail_summary, gmail_step_*, etc.",
        ),
        sa.Column(
            "step",
            sa.String(),
            nullable=True,
            comment="Pipeline step: questions, triage, action_summary, insight_summary, judge",
        ),
        sa.Column("interest", sa.Text(), nullable=True, comment="User interest string"),
        sa.Column("email_count", sa.Integer(), nullable=True),
        sa.Column(
            "questions",
            JSONB(),
            nullable=True,
            comment="Generated follow-up questions array",
        ),
        sa.Column(
            "top_email_ids",
            JSONB(),
            nullable=True,
            comment="Selected email message IDs array",
        ),
        sa.Column("final_summary", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("caller", JSONB(), nullable=True, comment="Agent attribution"),
        sa.Column("payload", JSONB(), nullable=False, comment="Full event payload"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_gmail_agent_events_username", "gmail_agent_events", ["username"])
    op.create_index("ix_gmail_agent_events_kind", "gmail_agent_events", ["kind"])
    op.create_index("ix_gmail_agent_events_session_id", "gmail_agent_events", ["session_id"])
    op.create_index("ix_gmail_agent_events_recorded_at", "gmail_agent_events", ["recorded_at"])

    # ── calendar_agent_events ───────────────────────────────────────
    op.create_table(
        "calendar_agent_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_msg_id",
            sa.String(),
            nullable=False,
            unique=True,
            comment="Redis XADD message ID for dedup",
        ),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column(
            "kind",
            sa.String(),
            nullable=False,
            comment="calendar_question, calendar_create",
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=True,
            comment="Clarification status: clarify, confirm",
        ),
        sa.Column("event_title", sa.String(), nullable=True),
        sa.Column("start_datetime", sa.String(), nullable=True),
        sa.Column("end_datetime", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("attendees", JSONB(), nullable=True, comment="Email addresses array"),
        sa.Column("google_event_id", sa.String(), nullable=True),
        sa.Column("google_html_link", sa.String(), nullable=True),
        sa.Column("caller", JSONB(), nullable=True, comment="Agent attribution"),
        sa.Column("payload", JSONB(), nullable=False, comment="Full event payload"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_calendar_agent_events_username", "calendar_agent_events", ["username"])
    op.create_index("ix_calendar_agent_events_kind", "calendar_agent_events", ["kind"])
    op.create_index("ix_calendar_agent_events_session_id", "calendar_agent_events", ["session_id"])
    op.create_index("ix_calendar_agent_events_recorded_at", "calendar_agent_events", ["recorded_at"])

    # ── caddy_log_events ────────────────────────────────────────────
    op.create_table(
        "caddy_log_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "stream_msg_id",
            sa.String(),
            nullable=False,
            unique=True,
            comment="Redis XADD message ID for dedup",
        ),
        sa.Column(
            "level",
            sa.String(),
            nullable=False,
            comment="Log level: warn, error",
        ),
        sa.Column("logger", sa.String(), nullable=True, comment="Source logger name"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=False, comment="Full log entry"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_caddy_log_events_level", "caddy_log_events", ["level"])
    op.create_index("ix_caddy_log_events_recorded_at", "caddy_log_events", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("caddy_log_events")
    op.drop_table("calendar_agent_events")
    op.drop_table("gmail_agent_events")
