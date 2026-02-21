"""Data processor webhooks for WebSocket fan-out.

Keeps only the webhook endpoints that broadcast OCR/template events to connected
clients. Proxy endpoints to the data-processor service are handled by Caddy.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.config import settings
from src.services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-processor", tags=["data-processor"])


def check_feature_enabled():
    """Check if data processor feature is enabled."""
    if not settings.data_processor_enabled:
        raise HTTPException(
            status_code=503,
            detail="Data processor feature is not enabled",
        )


# Webhook Pydantic models (for data-processor service callbacks)
class WebhookDocumentUploaded(BaseModel):
    """Webhook payload for document_uploaded event."""

    document_id: str
    channel_id: int
    uploaded_by: str
    filename: str
    thumbnail_url: Optional[str] = None


class WebhookOcrProgress(BaseModel):
    """Webhook payload for ocr_progress event."""

    document_id: str
    channel_id: int
    stage: str  # "preprocessing", "detection", "extraction", "mapping"
    progress: int  # 0-100
    message: str


class DetectedRegion(BaseModel):
    """A detected text region from OCR processing."""

    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    text: str
    confidence: float


class WebhookOcrComplete(BaseModel):
    """Webhook payload for ocr_complete event."""

    document_id: str
    channel_id: int
    detected_regions: List[DetectedRegion]
    extracted_text: str


class MatchedRegion(BaseModel):
    """A matched region from template application."""

    label_id: str
    label_name: str
    label_type: str
    x: float
    y: float
    width: float
    height: float
    matched_text: Optional[str] = None
    confidence: float


class WebhookTemplateApplied(BaseModel):
    """Webhook payload for template_applied event."""

    document_id: str
    channel_id: int
    template_id: str
    matched_regions: List[MatchedRegion]
    confidence: float


# =============================================================================
# Webhook Endpoints
# =============================================================================
# These endpoints are called by the data-processor service to broadcast
# real-time updates to connected WebSocket clients. They do NOT require
# user authentication since they're called from the trusted data-processor
# service within the internal docker network.
# =============================================================================


@router.post("/webhooks/document-uploaded")
async def webhook_document_uploaded(payload: WebhookDocumentUploaded):
    """Broadcast document_uploaded event to channel members."""
    check_feature_enabled()

    logger.info(
        "Received document_uploaded webhook: document_id=%s, channel_id=%s",
        payload.document_id,
        payload.channel_id,
    )

    await manager.broadcast_document_uploaded(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        uploaded_by=payload.uploaded_by,
        filename=payload.filename,
        thumbnail_url=payload.thumbnail_url,
    )

    return {"status": "ok", "message": "Document uploaded event broadcast"}


@router.post("/webhooks/ocr-progress")
async def webhook_ocr_progress(payload: WebhookOcrProgress):
    """Broadcast ocr_progress events to channel members."""
    check_feature_enabled()

    valid_stages = {"preprocessing", "detection", "extraction", "mapping"}
    if payload.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage. Must be one of: {', '.join(valid_stages)}",
        )

    if not 0 <= payload.progress <= 100:
        raise HTTPException(
            status_code=400,
            detail="Progress must be between 0 and 100",
        )

    logger.info(
        "Received ocr_progress webhook: document_id=%s, stage=%s, progress=%s%%",
        payload.document_id,
        payload.stage,
        payload.progress,
    )

    await manager.broadcast_ocr_progress(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        stage=payload.stage,
        progress=payload.progress,
        message=payload.message,
    )

    return {"status": "ok", "message": "OCR progress event broadcast"}


@router.post("/webhooks/ocr-complete")
async def webhook_ocr_complete(payload: WebhookOcrComplete):
    """Broadcast ocr_complete event to channel members."""
    check_feature_enabled()

    logger.info(
        "Received ocr_complete webhook: document_id=%s, detected_regions=%s, extracted_text_length=%s",
        payload.document_id,
        len(payload.detected_regions),
        len(payload.extracted_text),
    )

    detected_regions_dicts = [region.model_dump() for region in payload.detected_regions]

    await manager.broadcast_ocr_complete(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        detected_regions=detected_regions_dicts,
        extracted_text=payload.extracted_text,
    )

    return {"status": "ok", "message": "OCR complete event broadcast"}


@router.post("/webhooks/template-applied")
async def webhook_template_applied(payload: WebhookTemplateApplied):
    """Broadcast template_applied event to channel members."""
    check_feature_enabled()

    if not 0.0 <= payload.confidence <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="Confidence must be between 0.0 and 1.0",
        )

    logger.info(
        "Received template_applied webhook: document_id=%s, template_id=%s, matched_regions=%s, confidence=%.2f",
        payload.document_id,
        payload.template_id,
        len(payload.matched_regions),
        payload.confidence,
    )

    matched_regions_dicts = [region.model_dump() for region in payload.matched_regions]

    await manager.broadcast_template_applied(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        template_id=payload.template_id,
        matched_regions=matched_regions_dicts,
        confidence=payload.confidence,
    )

    return {"status": "ok", "message": "Template applied event broadcast"}
