"""
Data Processor Proxy Endpoints

This module provides proxy endpoints that forward requests to the
data-processor microservice. It handles authentication, request forwarding,
and error handling.

The data-processor service runs as a separate Django REST Framework
microservice that handles document processing, OCR, and template matching.

Additionally, this module provides webhook endpoints that the data-processor
service calls to broadcast real-time updates via WebSocket to connected clients.
"""

import httpx
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.admin import require_admin
from src.api.endpoints.auth import create_access_token
from src.models.user import User
from src.services.websocket_manager import manager
from src.services.rate_limiter import enforce_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-processor", tags=["data-processor"])

# HTTP client for forwarding requests to data-processor service
_http_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    """Get or create HTTP client for data-processor service."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=settings.DATA_PROCESSOR_URL,
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
    return _http_client


def _auth_cookies(user: User) -> Dict[str, str]:
    token = create_access_token({"sub": user.username})
    return {"access_token": f"Bearer {token}"}


def check_feature_enabled():
    """Check if data processor feature is enabled."""
    if not settings.data_processor_enabled:
        raise HTTPException(
            status_code=503,
            detail="Data processor feature is not enabled"
        )


async def admin_with_rate_limit(current_user: User = Depends(require_admin)) -> User:
    """Admin guard + shared rate limit for data-processor APIs."""
    await enforce_rate_limit(
        user_id=current_user.id,
        max_requests=settings.AI_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    return current_user


# Pydantic models for request/response
class DocumentUploadResponse(BaseModel):
    id: str
    channel_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    original_filename: Optional[str] = None
    filename: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ocr_status: Optional[str] = None
    ocr_result: Optional[Dict[str, Any]] = None
    raw_ocr_text: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None
    template_id: Optional[str] = None
    preprocessing_applied: Optional[List[str]] = None
    deskew_angle: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AnnotationCreate(BaseModel):
    label_type: str
    label_name: str
    color: str = "#FF0000"
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0


class AnnotationUpdate(BaseModel):
    label_type: Optional[str] = None
    label_name: Optional[str] = None
    color: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    rotation: Optional[float] = None


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    channel_id: str
    source_document_id: Optional[str] = None


class TemplateApply(BaseModel):
    template_id: str
    use_feature_matching: bool = True
    force_apply: bool = False
    confidence_threshold: float = 0.6


class ExportRequest(BaseModel):
    format: str  # "json", "csv", or "sql"


class BatchCreate(BaseModel):
    template_id: Optional[str] = None
    document_ids: list[str]


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


# Health check endpoint
@router.get("/health")
async def data_processor_health():
    """Check data-processor service health."""
    check_feature_enabled()
    
    client = await get_http_client()
    try:
        response = await client.get("/healthz")
        if response.status_code == 200:
            return {"status": "healthy", "service": "data-processor"}
        else:
            raise HTTPException(
                status_code=503,
                detail="Data processor service is not healthy"
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to data-processor service: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# Document endpoints
@router.post("/documents/", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    channel_id: str = Form(...),
    current_user: User = Depends(admin_with_rate_limit)
):
    """
    Upload a document for processing.
    
    Forwards the file to the data-processor service with user context.
    """
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        # Read file content
        content = await file.read()
        
        # Forward to data-processor
        response = await client.post(
            "/api/documents/",
            files={"image": (file.filename, content, file.content_type)},
            data={
                "channel_id": channel_id,
                "uploaded_by": str(current_user.id),
            },
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 201:
            dp = response.json()
            return {
                **dp,
                "filename": dp.get("original_filename"),
                "status": dp.get("ocr_status"),
                "message": dp.get("message", "Upload successful"),
            }
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Upload failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Get document details and OCR results."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.get(
            f"/api/documents/{document_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Request failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Delete a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.delete(
            f"/api/documents/{document_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 204:
            return {"message": "Document deleted"}
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Delete failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# Annotation endpoints
@router.post("/documents/{document_id}/annotations/")
async def create_annotation(
    document_id: str,
    annotation: AnnotationCreate,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Create an annotation on a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        payload = annotation.model_dump()
        response = await client.post(
            f"/api/documents/{document_id}/annotations/",
            json=payload,
            cookies=_auth_cookies(current_user),
        )

        
        if response.status_code in (200, 201):
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Create annotation failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to create annotation: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.put("/documents/{document_id}/annotations/{annotation_id}/")
async def update_annotation(
    document_id: str,
    annotation_id: str,
    annotation: AnnotationUpdate,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Update an annotation on a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.put(
            f"/api/documents/{document_id}/annotations/{annotation_id}/",
            json=annotation.model_dump(exclude_none=True),
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document or annotation not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Update annotation failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to update annotation: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.delete("/documents/{document_id}/annotations/{annotation_id}/")
async def delete_annotation(
    document_id: str,
    annotation_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Delete an annotation from a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.delete(
            f"/api/documents/{document_id}/annotations/{annotation_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 204:
            return {"message": "Annotation deleted"}
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document or annotation not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Delete annotation failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to delete annotation: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# OCR endpoints
@router.post("/documents/{document_id}/process/")
async def process_document(
    document_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Trigger OCR processing for a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.post(
            f"/api/documents/{document_id}/process/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Process failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to process document: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.post("/documents/{document_id}/extract-text/")
async def extract_text_for_annotations(
    document_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Extract text for all annotations in a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.post(
            f"/api/documents/{document_id}/extract-text/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Extraction failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to extract text: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# Template endpoints
@router.get("/templates/")
async def list_templates(
    channel_id: Optional[str] = None,
    current_user: User = Depends(admin_with_rate_limit)
):
    """List templates, optionally filtered by channel."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        params = {}
        if channel_id:
            params["channel_id"] = channel_id
        
        response = await client.get(
            "/api/templates/",
            params=params,
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Request failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.post("/templates/")
async def create_template(
    template: TemplateCreate,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Create a new template."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        data = template.model_dump()
        data["created_by"] = str(current_user.id)
        
        response = await client.post(
            "/api/templates/",
            json=data,
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Create template failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Get template details."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.get(
            f"/api/templates/{template_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Template not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Request failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to get template: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Delete a template."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.delete(
            f"/api/templates/{template_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 204:
            return {"message": "Template deleted"}
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Template not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Delete failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.post("/documents/{document_id}/apply-template/")
async def apply_template(
    document_id: str,
    request: TemplateApply,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Apply a template to a document."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.post(
            f"/api/documents/{document_id}/apply-template/",
            json=request.model_dump(),
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document or template not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Apply template failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to apply template: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# Export endpoints
@router.post("/documents/{document_id}/export/")
async def export_document(
    document_id: str,
    request: ExportRequest,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Export document data in specified format."""
    check_feature_enabled()
    
    if request.format not in ("json", "csv", "sql"):
        raise HTTPException(
            status_code=400,
            detail="Invalid export format. Supported: json, csv, sql"
        )
    
    client = await get_http_client()
    
    try:
        response = await client.post(
            f"/api/documents/{document_id}/export/",
            json=request.model_dump(),
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Document not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Export failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to export document: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


# Batch processing endpoints
@router.post("/batch/")
async def create_batch_job(
    request: BatchCreate,
    channel_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Create a batch processing job."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        data = request.model_dump()
        data["channel_id"] = channel_id
        data["created_by"] = str(current_user.id)
        
        response = await client.post(
            "/api/batch/",
            json=data,
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Create batch job failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to create batch job: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.get("/batch/{job_id}")
async def get_batch_job(
    job_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Get batch job status."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.get(
            f"/api/batch/{job_id}/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Batch job not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Request failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to get batch job: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


@router.post("/batch/{job_id}/process/")
async def process_batch_job(
    job_id: str,
    current_user: User = Depends(admin_with_rate_limit)
):
    """Start processing a batch job."""
    check_feature_enabled()
    
    client = await get_http_client()
    
    try:
        response = await client.post(
            f"/api/batch/{job_id}/process/",
            cookies=_auth_cookies(current_user),
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Batch job not found")
        else:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json().get("error", "Process failed")
            )
    except httpx.RequestError as e:
        logger.error(f"Failed to process batch job: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to data processor service"
        )


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
    """
    Webhook called by data-processor when a document upload completes.
    
    Broadcasts the document_uploaded event to all channel members via WebSocket.
    This allows the frontend to show immediate feedback when documents are
    uploaded by other users in the same data-processor channel.
    """
    check_feature_enabled()
    
    logger.info(
        f"Received document_uploaded webhook: document_id={payload.document_id}, "
        f"channel_id={payload.channel_id}"
    )
    
    await manager.broadcast_document_uploaded(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        uploaded_by=payload.uploaded_by,
        filename=payload.filename,
        thumbnail_url=payload.thumbnail_url
    )
    
    return {"status": "ok", "message": "Document uploaded event broadcast"}


@router.post("/webhooks/ocr-progress")
async def webhook_ocr_progress(payload: WebhookOcrProgress):
    """
    Webhook called by data-processor during OCR processing stages.
    
    Broadcasts ocr_progress events to all channel members via WebSocket.
    Provides real-time feedback on processing stages:
    - preprocessing: Image preprocessing (noise reduction, deskew correction)
    - detection: Detecting text regions and document elements
    - extraction: Extracting text via Tesseract OCR
    - mapping: Mapping extracted text to annotation regions
    
    The progress value (0-100) indicates completion percentage within the stage.
    """
    check_feature_enabled()
    
    # Validate stage value
    valid_stages = {"preprocessing", "detection", "extraction", "mapping"}
    if payload.stage not in valid_stages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stage. Must be one of: {', '.join(valid_stages)}"
        )
    
    # Validate progress range
    if not 0 <= payload.progress <= 100:
        raise HTTPException(
            status_code=400,
            detail="Progress must be between 0 and 100"
        )
    
    logger.info(
        f"Received ocr_progress webhook: document_id={payload.document_id}, "
        f"stage={payload.stage}, progress={payload.progress}%"
    )
    
    await manager.broadcast_ocr_progress(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        stage=payload.stage,
        progress=payload.progress,
        message=payload.message
    )
    
    return {"status": "ok", "message": "OCR progress event broadcast"}


@router.post("/webhooks/ocr-complete")
async def webhook_ocr_complete(payload: WebhookOcrComplete):
    """
    Webhook called by data-processor when OCR processing completes.
    
    Broadcasts ocr_complete event to all channel members via WebSocket.
    Includes detected regions with bounding boxes and extracted text.
    
    The frontend can use this to:
    - Display detected text regions as annotation suggestions
    - Show the full extracted text in the document viewer
    - Enable text search and selection within the document
    """
    check_feature_enabled()
    
    logger.info(
        f"Received ocr_complete webhook: document_id={payload.document_id}, "
        f"detected_regions={len(payload.detected_regions)}, "
        f"extracted_text_length={len(payload.extracted_text)}"
    )
    
    # Convert Pydantic models to dicts for the WebSocket broadcast
    detected_regions_dicts = [region.model_dump() for region in payload.detected_regions]
    
    await manager.broadcast_ocr_complete(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        detected_regions=detected_regions_dicts,
        extracted_text=payload.extracted_text
    )
    
    return {"status": "ok", "message": "OCR complete event broadcast"}


@router.post("/webhooks/template-applied")
async def webhook_template_applied(payload: WebhookTemplateApplied):
    """
    Webhook called by data-processor when a template is applied to a document.
    
    Broadcasts template_applied event to all channel members via WebSocket.
    Includes matched regions with transformed bounding box positions and
    an overall confidence score for the template match.
    
    The frontend can use this to:
    - Display matched template labels on the document
    - Show extracted text for each matched region
    - Indicate confidence levels with visual feedback
    - Allow users to review and correct low-confidence matches
    """
    check_feature_enabled()
    
    # Validate confidence range
    if not 0.0 <= payload.confidence <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="Confidence must be between 0.0 and 1.0"
        )
    
    logger.info(
        f"Received template_applied webhook: document_id={payload.document_id}, "
        f"template_id={payload.template_id}, matched_regions={len(payload.matched_regions)}, "
        f"confidence={payload.confidence:.2f}"
    )
    
    # Convert Pydantic models to dicts for the WebSocket broadcast
    matched_regions_dicts = [region.model_dump() for region in payload.matched_regions]
    
    await manager.broadcast_template_applied(
        channel_id=payload.channel_id,
        document_id=payload.document_id,
        template_id=payload.template_id,
        matched_regions=matched_regions_dicts,
        confidence=payload.confidence
    )
    
    return {"status": "ok", "message": "Template applied event broadcast"}
