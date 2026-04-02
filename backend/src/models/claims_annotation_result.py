import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from src.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimsAnnotationResult(Base):
    """Business table linking a claim to its annotation export.

    Each row represents one export action: who exported, which document,
    what damage labels were annotated, and the full findings JSON.
    """

    __tablename__ = "claims_annotation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("claims_visible_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_id = Column(String, nullable=False)
    document_id = Column(String, nullable=False)
    filename = Column(String, nullable=True)
    damage_labels = Column(ARRAY(String), nullable=False, server_default="{}")
    findings = Column(JSONB, nullable=False)
    exported_by = Column(String, nullable=False)
    exported_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_claims_annotation_results_claim_id", "claim_id"),
        Index("ix_claims_annotation_results_session_id", "session_id"),
        Index("ix_claims_annotation_results_exported_by", "exported_by"),
    )
