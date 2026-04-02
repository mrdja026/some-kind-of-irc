from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from secrets import randbelow
import re
import requests
import io
from typing import Any, List, Optional
from fpdf import FPDF

import redis as _redis

from src.core.config import settings
from src.core.database import get_db
from src.api.endpoints.auth import get_current_user
from src.models.user import User
from src.models.claims_visible import ClaimsVisibleSession
from src.models.claims_debug import ClaimsDebugEvent
from src.models.claims_annotation_result import ClaimsAnnotationResult
from src.models.channel import Channel
from src.models.message import Message
from src.services.websocket_manager import manager

from sqlalchemy.orm import Session as DbSession
from sqlalchemy import desc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["media"])


class PdfSection(BaseModel):
    heading: str
    content: str


class PdfGenerateRequest(BaseModel):
    title: str
    sections: List[PdfSection]
    links: List[str] = []


class ClaimResponse(BaseModel):
    filename: str
    claim: Any


@router.post("/pdf/generate")
def generate_pdf(request: Request, body: PdfGenerateRequest):
    try:
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, body.title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)

        # Sections
        pdf.set_font("helvetica", "", 12)
        for section in body.sections:
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 10, section.heading, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

            pdf.set_font("helvetica", "", 12)
            pdf.multi_cell(0, 6, section.content)
            pdf.ln(5)

        # Links
        if body.links:
            pdf.add_page()
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(0, 10, "Relevant Links", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)

            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 255)
            for link in body.links:
                pdf.cell(0, 6, link, link=link, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        # Output to buffer
        pdf_bytes = pdf.output()
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)

        # Upload to Media Storage
        storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")
        response = requests.post(
            f"{storage_url}/upload",
            files={
                "file": (
                    f"{body.title.replace(' ', '_').lower()}.pdf",
                    buffer,
                    "application/pdf",
                )
            },
            cookies=request.cookies,
            timeout=15,
        )

        if not response.ok:
            raise HTTPException(
                status_code=response.status_code, detail="Media storage upload failed"
            )

        return response.json()

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.post("/upload")
def upload_media(request: Request, file: UploadFile = File(...)):
    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")
    if not file:
        raise HTTPException(status_code=400, detail="Missing file")

    try:
        file.file.seek(0)
        response = requests.post(
            f"{storage_url}/upload",
            files={
                "file": (
                    file.filename or "upload",
                    file.file,
                    file.content_type or "application/octet-stream",
                )
            },
            cookies=request.cookies,
            timeout=15,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "Upload failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            if response.text:
                detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid storage response")


@router.get("/claims/random", response_model=ClaimResponse)
def get_random_claim(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    claim_index = randbelow(100) + 1
    filename = f"CLM-2026-{claim_index:04d}.json"
    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")

    try:
        response = requests.get(
            f"{storage_url}/claims/{filename}",
            cookies=request.cookies,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "Claim retrieval failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            if response.text:
                detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid storage response")

    if not isinstance(payload, dict) or "claim" not in payload:
        raise HTTPException(status_code=502, detail="Invalid claim payload")

    return payload


@router.get("/claims/deep-review/random", response_model=ClaimResponse)
def get_deep_review_claim(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return a random incomplete claim (0001-0010) that has companion data."""
    claim_index = randbelow(10) + 1
    filename = f"CLM-2026-{claim_index:04d}.json"
    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")

    try:
        response = requests.get(
            f"{storage_url}/claims/{filename}",
            cookies=request.cookies,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "Claim retrieval failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            if response.text:
                detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid storage response")

    if not isinstance(payload, dict) or "claim" not in payload:
        raise HTTPException(status_code=502, detail="Invalid claim payload")

    return payload


_claim_id_pattern = r"^CLM-2026-\d{4}$"


@router.get("/claims/{claim_id}/files")
def list_claim_files(
    request: Request,
    claim_id: str,
    current_user: User = Depends(get_current_user),
):
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")
    try:
        response = requests.get(
            f"{storage_url}/claims/{claim_id}/files",
            cookies=request.cookies,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "File listing failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid storage response")


@router.get("/claims/{claim_id}/files/{filename:path}")
def get_claim_file(
    request: Request,
    claim_id: str,
    filename: str,
    current_user: User = Depends(get_current_user),
):
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    storage_url = settings.MEDIA_STORAGE_URL.rstrip("/")
    try:
        response = requests.get(
            f"{storage_url}/claims/{claim_id}/files/{filename}",
            cookies=request.cookies,
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Media storage unavailable")

    if not response.ok:
        detail = "File retrieval failed"
        try:
            payload = response.json()
            detail = payload.get("detail", detail)
        except ValueError:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)

    content_type = response.headers.get("content-type", "application/octet-stream")
    return Response(content=response.content, media_type=content_type)


# ---------------------------------------------------------------------------
# Data-processor proxy helpers
# ---------------------------------------------------------------------------

def _dp_headers() -> dict:
    """Build auth headers for data-processor service calls."""
    secret = settings.DP_SERVICE_AUTH_SECRET
    if secret:
        return {"X-Service-Auth": secret, "Content-Type": "application/json"}
    return {"Content-Type": "application/json"}


def _dp_url(path: str) -> str:
    return f"{settings.DATA_PROCESSOR_URL.rstrip('/')}/api/{path.lstrip('/')}"


# ---------------------------------------------------------------------------
# Claim damage-annotation proxy endpoints
# ---------------------------------------------------------------------------


class CreateDocFromMinioRequest(BaseModel):
    image_url: str
    source_key: str
    source_parent_key: str | None = None
    original_filename: str | None = None


@router.post("/claims/{claim_id}/documents/from-minio")
def create_claim_document(
    claim_id: str,
    body: CreateDocFromMinioRequest,
    current_user: User = Depends(get_current_user),
):
    """Create or retrieve a data-processor document from a MinIO reference."""
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    payload = {
        "source_bucket": "synt-data",
        "source_key": body.source_key,
        "source_parent_key": body.source_parent_key or f"{claim_id}-data",
        "image_url": body.image_url,
        "channel_id": f"claims-{claim_id}",
        "uploaded_by": current_user.username,
        "original_filename": body.original_filename or body.source_key.rsplit("/", 1)[-1],
    }
    try:
        resp = requests.post(
            _dp_url("documents/from-minio/"),
            json=payload,
            headers=_dp_headers(),
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Data processor unavailable")

    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


class CreateDamageAnnotationRequest(BaseModel):
    document_id: str
    label_type: str = "fire_damage"
    label_name: str = ""
    color: str = "#EF5350"
    bounding_box: dict
    verification_status: str = "human_verified"
    certainty: float = 1.0
    review_value: str | None = None


@router.post("/claims/{claim_id}/damage-annotations")
def create_damage_annotation(
    claim_id: str,
    body: CreateDamageAnnotationRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a damage annotation on a claim document via data-processor."""
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    payload = {
        "label_type": body.label_type,
        "label_name": body.label_name or body.label_type.replace("_", " ").title(),
        "color": body.color,
        "bounding_box": body.bounding_box,
        "verification_status": body.verification_status,
        "certainty": body.certainty,
        "review_value": body.review_value,
    }
    try:
        resp = requests.post(
            _dp_url(f"documents/{body.document_id}/annotations/"),
            json=payload,
            headers=_dp_headers(),
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Data processor unavailable")

    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


@router.get("/claims/{claim_id}/damage-annotations")
def list_damage_annotations(
    claim_id: str,
    current_user: User = Depends(get_current_user),
):
    """List all damage annotations for a claim's documents."""
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    channel_id = f"claims-{claim_id}"
    try:
        resp = requests.get(
            _dp_url("documents/"),
            params={"channel_id": channel_id},
            headers=_dp_headers(),
            timeout=10,
        )
    except requests.RequestException:
        raise HTTPException(status_code=503, detail="Data processor unavailable")

    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()
    documents = data.get("documents", [])
    annotations = []
    for doc in documents:
        for ann in doc.get("annotations", []):
            ann["document_id"] = doc.get("id")
            ann["original_filename"] = doc.get("original_filename")
            ann["image_url"] = doc.get("image_url")
            annotations.append(ann)

    return {"claim_id": claim_id, "annotations": annotations, "count": len(annotations)}


# ---------------------------------------------------------------------------
# Annotation session & export persistence
# ---------------------------------------------------------------------------

_redis_log_client: _redis.Redis | None = None


def _get_redis_log() -> _redis.Redis:
    global _redis_log_client
    if _redis_log_client is None:
        url = settings.REDIS_LOG_URL.strip()
        if not url:
            raise HTTPException(status_code=503, detail="Redis log URL not configured")
        _redis_log_client = _redis.from_url(url, decode_responses=True)
    return _redis_log_client


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/claims/{claim_id}/annotation-session")
def create_annotation_session(
    claim_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """Create or reuse a claims annotation session for a claim and user."""
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    existing = (
        db.query(ClaimsVisibleSession)
        .filter(
            ClaimsVisibleSession.claim_id == claim_id,
            ClaimsVisibleSession.username == current_user.username,
            ClaimsVisibleSession.status == "annotation",
        )
        .first()
    )
    if existing:
        return {"session_id": str(existing.id), "created": False}

    session = ClaimsVisibleSession(
        id=uuid.uuid4(),
        claim_id=claim_id,
        username=current_user.username,
        status="annotation",
        flags={"source": "annotation_export"},
        turn_count=0,
        created_at=_utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": str(session.id), "created": True}


class AnnotationExportRequest(BaseModel):
    session_id: str
    document_id: str
    findings: Any
    source_filename: str | None = None


@router.post("/claims/{claim_id}/annotation-export")
async def persist_annotation_export(
    claim_id: str,
    body: AnnotationExportRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """Persist annotation export to claims_debug_events, emit AI stream event, post #ai message."""
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    try:
        session_uuid = uuid.UUID(body.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    session = (
        db.query(ClaimsVisibleSession)
        .filter(ClaimsVisibleSession.id == session_uuid)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Annotation session not found")

    now = _utcnow()
    payload = {
        "claim_id": claim_id,
        "document_id": body.document_id,
        "source_filename": body.source_filename,
        "findings": body.findings,
        "username": current_user.username,
        "exported_at": now.isoformat().replace("+00:00", "Z"),
    }

    # 1) Emit AI session stream event via Redis XADD
    stream_msg_id = ""
    try:
        client = _get_redis_log()
        fields: dict[str, str] = {
            "recorded_at": now.isoformat().replace("+00:00", "Z"),
            "source": "backend",
            "kind": "claims_annotation_export",
            "backend": "n/a",
            "username": current_user.username,
            "payload": json.dumps(payload, default=str),
            "session_id": str(session_uuid),
        }
        stream_msg_id = client.xadd(
            settings.AI_SESSION_STREAM_KEY,
            fields,
            maxlen=500,
            approximate=True,
        )
        if isinstance(stream_msg_id, bytes):
            stream_msg_id = stream_msg_id.decode()
    except Exception:
        logger.warning("Failed to XADD annotation export event", exc_info=True)
        stream_msg_id = f"fallback-{uuid.uuid4().hex[:12]}"

    # 2) Write claims_debug_events row
    debug_event = ClaimsDebugEvent(
        id=uuid.uuid4(),
        session_id=session_uuid,
        stream_msg_id=str(stream_msg_id),
        event_kind="claims_annotation_export",
        stage="export",
        payload=payload,
        request_id=None,
        correlation_id=None,
        recorded_at=now,
        created_at=now,
    )
    db.add(debug_event)

    # 3) Update session turn_count as a proxy for export count
    session.turn_count = (session.turn_count or 0) + 1

    # 4) Write claims_annotation_results row (business table)
    damage_labels: list[str] = []
    if isinstance(body.findings, dict):
        fields = body.findings.get("fields") or []
        if isinstance(fields, list):
            for f in fields:
                if isinstance(f, dict):
                    name = f.get("name") or f.get("label_name") or ""
                    if name:
                        damage_labels.append(name)
                elif isinstance(f, str):
                    damage_labels.append(f)
    annotation_result = ClaimsAnnotationResult(
        id=uuid.uuid4(),
        session_id=session_uuid,
        claim_id=claim_id,
        document_id=body.document_id,
        filename=body.source_filename,
        damage_labels=damage_labels,
        findings=body.findings if body.findings else {},
        exported_by=current_user.username,
        exported_at=now,
    )
    db.add(annotation_result)

    # 5) Post #ai message with FINDINGS JSON and broadcast via WebSocket
    ai_channel = db.query(Channel).filter(Channel.name == "#ai").first()
    ai_message_id = None
    if ai_channel:
        findings_summary = json.dumps(body.findings, default=str)
        if len(findings_summary) > 2000:
            findings_summary = findings_summary[:1997] + "..."
        content = (
            f"📋 **Annotation Export** — `{claim_id}`\n"
            f"Document: `{body.source_filename or body.document_id}`\n"
            f"```json\n{findings_summary}\n```"
        )
        msg = Message(
            content=content,
            sender_id=int(current_user.id),
            channel_id=int(ai_channel.id),
        )
        db.add(msg)

    db.commit()

    if ai_channel:
        db.refresh(msg)
        ai_message_id = int(msg.id)
        await manager.broadcast(
            {
                "type": "message",
                "id": ai_message_id,
                "content": str(msg.content),
                "image_url": None,
                "sender_id": int(current_user.id),
                "username": str(current_user.username),
                "display_name": getattr(current_user, "display_name", None),
                "channel_id": int(ai_channel.id),
                "timestamp": msg.timestamp.isoformat(),
            },
            int(ai_channel.id),
        )

    return {
        "status": "ok",
        "debug_event_id": str(debug_event.id),
        "annotation_result_id": str(annotation_result.id),
        "damage_labels": damage_labels,
        "stream_msg_id": str(stream_msg_id),
        "ai_message_id": ai_message_id,
    }


# ---------------------------------------------------------------------------
# Annotation results — read + derive primary damage_type
# ---------------------------------------------------------------------------


def _derive_damage_type(result: ClaimsAnnotationResult) -> str:
    """Pick primary damage_type: highest certainty → most frequent → first → unknown."""
    findings = result.findings or {}
    fields = findings.get("fields") if isinstance(findings, dict) else []
    if not isinstance(fields, list) or not fields:
        labels = list(result.damage_labels or [])
        return labels[0] if labels else "unknown"

    # Try highest certainty
    best_label, best_cert = None, -1.0
    freq: dict[str, int] = {}
    for f in fields:
        if not isinstance(f, dict):
            continue
        name = f.get("name") or ""
        if not name:
            continue
        cert = f.get("certainty")
        if cert is not None and cert > best_cert:
            best_cert = cert
            best_label = name
        freq[name] = freq.get(name, 0) + 1

    if best_label and best_cert > 0:
        return best_label

    # Fallback: most frequent
    if freq:
        return max(freq, key=lambda k: freq[k])

    # Fallback: first damage_label
    labels = list(result.damage_labels or [])
    return labels[0] if labels else "unknown"


@router.get("/claims/{claim_id}/annotation-results")
async def get_annotation_results(
    claim_id: str,
    request: Request,
    session_id: Optional[str] = Query(None),
    document_id: Optional[str] = Query(None),
    db: DbSession = Depends(get_db),
):
    """Return latest annotation results for a claim, derive damage_type.

    Auth is optional: when called with a valid cookie (frontend), the endpoint
    also posts an #ai message and emits a stream event.  When called without
    auth (ADK service-to-service), it returns data only.
    """
    if not re.match(_claim_id_pattern, claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim ID")

    # Optional auth — don't fail if missing
    current_user: User | None = None
    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        pass

    query = db.query(ClaimsAnnotationResult).filter(
        ClaimsAnnotationResult.claim_id == claim_id,
    )
    if session_id:
        try:
            sid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid session_id")
        query = query.filter(ClaimsAnnotationResult.session_id == sid)
    if document_id:
        query = query.filter(ClaimsAnnotationResult.document_id == document_id)

    result = query.order_by(desc(ClaimsAnnotationResult.exported_at)).first()

    if not result:
        return {
            "status": "no_results",
            "claim_id": claim_id,
            "damage_type": None,
            "damage_labels": [],
            "findings": {},
        }

    damage_type = _derive_damage_type(result)
    now = _utcnow()
    username = current_user.username if current_user else "system"

    payload = {
        "claim_id": claim_id,
        "document_id": result.document_id,
        "damage_type": damage_type,
        "damage_labels": list(result.damage_labels or []),
        "findings": result.findings,
        "username": username,
        "resolved_at": now.isoformat().replace("+00:00", "Z"),
    }

    # Emit AI session stream event (always — even without auth)
    stream_msg_id = ""
    try:
        client = _get_redis_log()
        fields: dict[str, str] = {
            "recorded_at": now.isoformat().replace("+00:00", "Z"),
            "source": "backend",
            "kind": "claims_annotation_results",
            "backend": "n/a",
            "username": username,
            "payload": json.dumps(payload, default=str),
            "session_id": str(result.session_id),
        }
        stream_msg_id = client.xadd(
            settings.AI_SESSION_STREAM_KEY,
            fields,
            maxlen=500,
            approximate=True,
        )
        if isinstance(stream_msg_id, bytes):
            stream_msg_id = stream_msg_id.decode()
    except Exception:
        logger.warning("Failed to XADD annotation results event", exc_info=True)
        stream_msg_id = f"fallback-{uuid.uuid4().hex[:12]}"

    # Post #ai message (only when authenticated — skip for ADK service-to-service)
    ai_message_id = None
    if current_user:
        ai_channel = db.query(Channel).filter(Channel.name == "#ai").first()
        if ai_channel:
            findings_summary = json.dumps(result.findings, default=str)
            if len(findings_summary) > 2000:
                findings_summary = findings_summary[:1997] + "..."
            content = (
                f"✅ **ok that is {damage_type} damage** — `{claim_id}`\n"
                f"Document: `{result.filename or result.document_id}`\n"
                f"```json\n{findings_summary}\n```"
            )
            msg = Message(
                content=content,
                sender_id=int(current_user.id),
                channel_id=int(ai_channel.id),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            ai_message_id = int(msg.id)

            await manager.broadcast(
                {
                    "type": "message",
                    "id": ai_message_id,
                    "content": str(msg.content),
                    "image_url": None,
                    "sender_id": int(current_user.id),
                    "username": str(current_user.username),
                    "display_name": getattr(current_user, "display_name", None),
                    "channel_id": int(ai_channel.id),
                    "timestamp": msg.timestamp.isoformat(),
                },
                int(ai_channel.id),
            )

    return {
        "status": "ok",
        "claim_id": claim_id,
        "damage_type": damage_type,
        "damage_labels": list(result.damage_labels or []),
        "findings": result.findings,
        "document_id": result.document_id,
        "filename": result.filename,
        "stream_msg_id": str(stream_msg_id),
        "ai_message_id": ai_message_id,
    }
