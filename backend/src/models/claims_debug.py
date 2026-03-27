import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimsDebugEvent(Base):
    __tablename__ = "claims_debug_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("claims_visible_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Redis XADD message ID (e.g. "1711528800000-0") — always unique per message.
    # Used as the dedup key so ON CONFLICT is reliable even when request_id is NULL.
    stream_msg_id = Column(String, nullable=False, server_default="")
    event_kind = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    payload = Column(JSONB, nullable=False)
    request_id = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("session_id", "stream_msg_id", name="uq_debug_event_stream_msg"),
        Index("ix_claims_debug_events_session_id", "session_id"),
        Index("ix_claims_debug_events_event_kind", "event_kind"),
    )
