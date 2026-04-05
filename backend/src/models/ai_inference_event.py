"""
AiInferenceEvent model: Stores all AI inference events from Redis stream.

This table persists every AI inference event emitted to `ai:session_events`,
providing a durable audit log of all AI agent activity including claims Q&A,
Gmail summarization, calendar operations, and local Q&A.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiInferenceEvent(Base):
    """
    Persisted AI inference event from the Redis `ai:session_events` stream.

    Deduplicated by `stream_msg_id` (the Redis XADD message ID).
    Includes full event metadata plus JSONB columns for caller, tool_calls,
    and the raw payload.
    """

    __tablename__ = "ai_inference_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Redis XADD message ID (e.g. "1711528800000-0") — globally unique per message.
    # Used as the dedup key so ON CONFLICT is reliable.
    stream_msg_id = Column(String, nullable=False)

    # Core event metadata
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(
        String,
        nullable=False,
        comment="Service that emitted the event: caddy, ai_service, ai_service_adk, backend",
    )
    kind = Column(
        String,
        nullable=False,
        comment="Event type: claims_candidate, gmail_step_judge, tool_invoked, etc.",
    )
    backend = Column(
        String,
        nullable=False,
        comment="AI backend: crewai, google_adk, local_vllm, n/a",
    )

    # Session and request correlation
    session_id = Column(String, nullable=True)
    request_id = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)

    # User attribution
    username = Column(String, nullable=True)

    # Agent caller attribution (JSONB): {agent, role, stage, attempt, model}
    caller = Column(
        JSONB,
        nullable=True,
        comment="Agent attribution: agent, role, stage, attempt, model",
    )

    # Tool calls (JSONB array): [{tool_name, args, result, error, elapsed_ms, reason, reason_detail, caller}]
    tool_calls = Column(
        JSONB,
        nullable=True,
        comment="List of tool invocations with args, results, reason taxonomy",
    )

    # Optional question(s), reasoning, and plan fields
    question = Column(Text, nullable=True)
    questions = Column(JSONB, nullable=True, comment="Array of question strings")
    reasoning = Column(Text, nullable=True)
    plan = Column(JSONB, nullable=True, comment="Agent plan or step list")

    # Full event payload (JSONB) — raw or structured request/response data
    payload = Column(JSONB, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Retention: rows past expires_at may be purged by a scheduled job.
    # Default: 90 days from creation. NULL means indefinite retention.
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Retention deadline; rows past this timestamp may be purged",
    )

    __table_args__ = (
        # Ensure stream_msg_id is unique for dedup
        UniqueConstraint("stream_msg_id", name="uq_ai_inference_event_stream_msg_id"),
        # Index for session-based queries
        Index("ix_ai_inference_events_session_id", "session_id"),
        # Index for kind-based filtering
        Index("ix_ai_inference_events_kind", "kind"),
        # Index for time-range queries
        Index("ix_ai_inference_events_recorded_at", "recorded_at"),
        # Partial index for retention purge queries
        Index("ix_ai_inference_events_expires_at", "expires_at", postgresql_where="expires_at IS NOT NULL"),
    )
