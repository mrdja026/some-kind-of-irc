from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
import requests
import io
from typing import List
from fpdf import FPDF

from src.core.config import settings

router = APIRouter(prefix="/media", tags=["media"])


class PdfSection(BaseModel):
    heading: str
    content: str


class PdfGenerateRequest(BaseModel):
    title: str
    sections: List[PdfSection]
    links: List[str] = []


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
            raise HTTPException(status_code=response.status_code, detail="Media storage upload failed")
            
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
