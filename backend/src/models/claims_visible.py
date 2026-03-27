import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.core.database import Base


class ClaimsVisibleSession(Base):
    __tablename__ = "claims_visible_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    flags = Column(JSONB, nullable=True)
    turn_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_claims_visible_sessions_created_at", "created_at"),
    )


class ClaimsVisibleTurn(Base):
    __tablename__ = "claims_visible_turns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("claims_visible_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_number = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=True)
    tool_calls = Column(JSONB, nullable=True)
    done = Column(Boolean, nullable=False, default=False)
    next_question = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("session_id", "turn_number", name="uq_session_turn"),
        Index("ix_claims_visible_turns_session_id", "session_id"),
    )
