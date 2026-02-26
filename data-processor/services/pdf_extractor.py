"""
PDF extraction utilities for data-processor.

Provides:
- PDF first-page rasterization
- Text layer extraction for page 1
- Page count metadata
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List
import logging

from pdf2image import convert_from_bytes
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)

MAX_DIMENSION = 1024


@dataclass
class PdfExtractionResult:
    """Result of PDF extraction for first page."""

    page_count: int
    image_bytes: bytes
    width: int
    height: int
    text_layer: List[Dict[str, Any]]


def _resize_image(image: Image.Image, max_dimension: int) -> Image.Image:
    """Resize image to fit within max dimensions while preserving aspect ratio."""
    if image.width <= max_dimension and image.height <= max_dimension:
        return image

    resized = image.copy()
    resized.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    logger.info(
        "Resized PDF page from %sx%s to %sx%s",
        image.width,
        image.height,
        resized.width,
        resized.height,
    )
    return resized


def extract_pdf_first_page(pdf_bytes: bytes, max_dimension: int = MAX_DIMENSION) -> PdfExtractionResult:
    """Extract text layer and rasterize the first page of a PDF."""
    if not pdf_bytes:
        raise ValueError("PDF content is empty")

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        if page_count == 0:
            raise ValueError("PDF has no pages")

        first_page = pdf.pages[0]
        extracted_text = first_page.extract_text() or ""
        words = first_page.extract_words() or []

        text_layer: List[Dict[str, Any]] = []
        if extracted_text or words:
            text_layer = [
                {
                    "page": 1,
                    "text": extracted_text,
                    "words": [
                        {
                            "text": word.get("text"),
                            "x0": word.get("x0"),
                            "x1": word.get("x1"),
                            "top": word.get("top"),
                            "bottom": word.get("bottom"),
                        }
                        for word in words
                    ],
                }
            ]

    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, fmt="png")
    if not images:
        raise ValueError("Failed to rasterize PDF")

    image = _resize_image(images[0], max_dimension)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    return PdfExtractionResult(
        page_count=page_count,
        image_bytes=image_bytes,
        width=image.width,
        height=image.height,
        text_layer=text_layer,
    )
