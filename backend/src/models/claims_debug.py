import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.core.database import Base


class ClaimsDebugEvent(Base):
    __tablename__ = "claims_debug_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("claims_visible_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_kind = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    payload = Column(JSONB, nullable=False)
    request_id = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)
    recorded_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_claims_debug_events_session_id", "session_id"),
        Index("ix_claims_debug_events_event_kind", "event_kind"),
    )
