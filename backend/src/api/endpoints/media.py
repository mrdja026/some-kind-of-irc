from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from secrets import randbelow
import re
import requests
import io
from typing import Any, List
from fpdf import FPDF

from src.core.config import settings
from src.api.endpoints.auth import get_current_user
from src.models.user import User

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
