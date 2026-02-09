"""
OCR pipeline with Tesseract integration.

Provides text extraction from preprocessed images with:
- Full document OCR
- Region-specific extraction
- Confidence scoring
- Automatic region detection for common document elements
- Coordinate mapping between annotations and extracted text
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import re

import cv2
import numpy as np
import pytesseract
from pytesseract import Output
from django.conf import settings

from .preprocessor import (
    PreprocessingConfig,
    preprocess_image,
    load_image_from_bytes,
    convert_to_grayscale,
)
from storage.in_memory import BoundingBox, Annotation, LabelType

logger = logging.getLogger(__name__)


@dataclass
class OcrConfig:
    """Configuration for OCR processing."""
    lang: str = "eng"
    psm: int = 3  # Page segmentation mode (3 = fully automatic)
    oem: int = 3  # OCR engine mode (3 = default, based on what's available)
    custom_config: str = ""
    min_confidence: float = 0.0  # Minimum confidence threshold
    
    @classmethod
    def from_settings(cls) -> "OcrConfig":
        """Create config from Django settings."""
        return cls(
            lang=getattr(settings, "OCR_LANG", "eng"),
        )
    
    def to_tesseract_config(self) -> str:
        """Build Tesseract config string."""
        config_parts = [
            f"--psm {self.psm}",
            f"--oem {self.oem}",
        ]
        if self.custom_config:
            config_parts.append(self.custom_config)
        return " ".join(config_parts)


@dataclass
class OcrWord:
    """Represents a single word extracted by OCR."""
    text: str
    confidence: float
    x: int
    y: int
    width: int
    height: int
    block_num: int = 0
    par_num: int = 0
    line_num: int = 0
    word_num: int = 0


@dataclass
class OcrLine:
    """Represents a line of text."""
    text: str
    words: List[OcrWord]
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class OcrBlock:
    """Represents a text block (paragraph)."""
    text: str
    lines: List[OcrLine]
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class OcrResult:
    """Complete OCR result for a document."""
    full_text: str
    words: List[OcrWord]
    lines: List[OcrLine]
    blocks: List[OcrBlock]
    average_confidence: float
    word_count: int
    detected_regions: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "full_text": self.full_text,
            "word_count": self.word_count,
            "average_confidence": self.average_confidence,
            "blocks": [
                {
                    "text": block.text,
                    "confidence": block.confidence,
                    "bounding_box": {
                        "x": block.x,
                        "y": block.y,
                        "width": block.width,
                        "height": block.height,
                    },
                    "lines": [
                        {
                            "text": line.text,
                            "confidence": line.confidence,
                            "bounding_box": {
                                "x": line.x,
                                "y": line.y,
                                "width": line.width,
                                "height": line.height,
                            },
                        }
                        for line in block.lines
                    ],
                }
                for block in self.blocks
            ],
            "detected_regions": self.detected_regions,
        }


def extract_text_simple(
    image: np.ndarray,
    config: Optional[OcrConfig] = None
) -> str:
    """
    Simple text extraction from image.
    
    Args:
        image: OpenCV image (grayscale or color)
        config: OCR configuration
        
    Returns:
        Extracted text string
    """
    if config is None:
        config = OcrConfig.from_settings()
    
    # Ensure grayscale for better OCR
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    text = pytesseract.image_to_string(
        gray,
        lang=config.lang,
        config=config.to_tesseract_config()
    )
    
    return text.strip()


def extract_text_with_data(
    image: np.ndarray,
    config: Optional[OcrConfig] = None
) -> OcrResult:
    """
    Full text extraction with word-level bounding boxes and confidence.
    
    Args:
        image: OpenCV image (grayscale or color)
        config: OCR configuration
        
    Returns:
        OcrResult with structured text data
    """
    if config is None:
        config = OcrConfig.from_settings()
    
    # Ensure grayscale for better OCR
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Get detailed OCR data
    data = pytesseract.image_to_data(
        gray,
        lang=config.lang,
        config=config.to_tesseract_config(),
        output_type=Output.DICT
    )
    
    # Parse words
    words: List[OcrWord] = []
    valid_confidences = []
    
    n_boxes = len(data["text"])
    for i in range(n_boxes):
        text = str(data["text"][i]).strip()
        conf = float(data["conf"][i])
        
        if text and conf >= config.min_confidence:
            word = OcrWord(
                text=text,
                confidence=conf,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                width=int(data["width"][i]),
                height=int(data["height"][i]),
                block_num=int(data["block_num"][i]),
                par_num=int(data["par_num"][i]),
                line_num=int(data["line_num"][i]),
                word_num=int(data["word_num"][i]),
            )
            words.append(word)
            if conf > 0:
                valid_confidences.append(conf)
    
    # Group words into lines
    lines = _group_words_into_lines(words)
    
    # Group lines into blocks
    blocks = _group_lines_into_blocks(lines)
    
    # Calculate full text
    full_text = " ".join([w.text for w in words])
    
    # Calculate average confidence
    avg_conf = sum(valid_confidences) / len(valid_confidences) if valid_confidences else 0.0
    
    logger.info(f"OCR extracted {len(words)} words with avg confidence {avg_conf:.1f}%")
    
    return OcrResult(
        full_text=full_text,
        words=words,
        lines=lines,
        blocks=blocks,
        average_confidence=avg_conf,
        word_count=len(words),
    )


def _group_words_into_lines(words: List[OcrWord]) -> List[OcrLine]:
    """Group words into lines based on their line numbers."""
    lines_dict: Dict[Tuple[int, int, int], List[OcrWord]] = {}
    
    for word in words:
        key = (word.block_num, word.par_num, word.line_num)
        if key not in lines_dict:
            lines_dict[key] = []
        lines_dict[key].append(word)
    
    lines: List[OcrLine] = []
    for key, line_words in sorted(lines_dict.items()):
        if not line_words:
            continue
        
        # Sort words by x position
        line_words.sort(key=lambda w: w.x)
        
        # Calculate line bounds
        x = min(w.x for w in line_words)
        y = min(w.y for w in line_words)
        x2 = max(w.x + w.width for w in line_words)
        y2 = max(w.y + w.height for w in line_words)
        
        # Calculate line text and confidence
        text = " ".join(w.text for w in line_words)
        confidences = [w.confidence for w in line_words if w.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        lines.append(OcrLine(
            text=text,
            words=line_words,
            x=x,
            y=y,
            width=x2 - x,
            height=y2 - y,
            confidence=avg_conf,
        ))
    
    return lines


def _group_lines_into_blocks(lines: List[OcrLine]) -> List[OcrBlock]:
    """Group lines into blocks based on their block numbers."""
    blocks_dict: Dict[int, List[OcrLine]] = {}
    
    for line in lines:
        if line.words:
            block_num = line.words[0].block_num
            if block_num not in blocks_dict:
                blocks_dict[block_num] = []
            blocks_dict[block_num].append(line)
    
    blocks: List[OcrBlock] = []
    for block_num, block_lines in sorted(blocks_dict.items()):
        if not block_lines:
            continue
        
        # Sort lines by y position
        block_lines.sort(key=lambda l: l.y)
        
        # Calculate block bounds
        x = min(l.x for l in block_lines)
        y = min(l.y for l in block_lines)
        x2 = max(l.x + l.width for l in block_lines)
        y2 = max(l.y + l.height for l in block_lines)
        
        # Calculate block text and confidence
        text = "\n".join(l.text for l in block_lines)
        confidences = [l.confidence for l in block_lines if l.confidence > 0]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        blocks.append(OcrBlock(
            text=text,
            lines=block_lines,
            x=x,
            y=y,
            width=x2 - x,
            height=y2 - y,
            confidence=avg_conf,
        ))
    
    return blocks


def extract_text_from_region(
    image: np.ndarray,
    bbox: BoundingBox,
    config: Optional[OcrConfig] = None
) -> Tuple[str, float]:
    """
    Extract text from a specific region of an image.
    
    Args:
        image: Full document image
        bbox: Bounding box defining the region
        config: OCR configuration
        
    Returns:
        Tuple of (extracted_text, confidence)
    """
    if config is None:
        config = OcrConfig.from_settings()
    
    # Extract region
    x = int(bbox.x)
    y = int(bbox.y)
    w = int(bbox.width)
    h = int(bbox.height)
    
    # Ensure bounds are within image
    height, width = image.shape[:2]
    x = max(0, min(x, width - 1))
    y = max(0, min(y, height - 1))
    w = min(w, width - x)
    h = min(h, height - y)
    
    if w <= 0 or h <= 0:
        logger.warning(f"Invalid region bounds: x={x}, y={y}, w={w}, h={h}")
        return "", 0.0
    
    region = image[y:y+h, x:x+w]
    
    # Handle rotation if specified
    if bbox.rotation != 0:
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, -bbox.rotation, 1.0)
        region = cv2.warpAffine(region, rotation_matrix, (w, h))
    
    # Extract text with data for confidence
    result = extract_text_with_data(region, config)
    
    return result.full_text, result.average_confidence


def detect_document_regions(
    image: np.ndarray,
    min_area: int = 500
) -> List[Dict[str, Any]]:
    """
    Automatically detect document regions using contour analysis.
    
    Detects:
    - Text blocks
    - Tables (grid patterns)
    - Potential signature areas (irregular shapes at bottom)
    
    Args:
        image: Document image
        min_area: Minimum contour area to consider
        
    Returns:
        List of detected regions with type hints
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    height, width = image.shape[:2]
    regions: List[Dict[str, Any]] = []
    
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0
        
        # Classify region type
        region_type = "text"
        
        # Wide, thin regions near edges might be headers
        if y < height * 0.15 and w > width * 0.4:
            region_type = "header"
        # Bottom regions might be signatures
        elif y > height * 0.8:
            region_type = "signature"
        # Very wide regions might be tables
        elif aspect_ratio > 3 and h > 20:
            region_type = "table"
        
        regions.append({
            "type": region_type,
            "bounding_box": {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
            },
            "area": area,
            "aspect_ratio": aspect_ratio,
        })
    
    # Sort by y position (top to bottom)
    regions.sort(key=lambda r: r["bounding_box"]["y"])
    
    logger.info(f"Detected {len(regions)} document regions")
    return regions


def detect_tables(image: np.ndarray) -> List[Dict[str, Any]]:
    """
    Detect table structures using line detection.
    
    Args:
        image: Document image
        
    Returns:
        List of detected table regions
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Detect horizontal lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    
    # Detect vertical lines
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    
    # Combine
    table_mask = cv2.add(horizontal, vertical)
    
    # Find table contours
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    tables: List[Dict[str, Any]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 5000:  # Minimum table size
            continue
        
        x, y, w, h = cv2.boundingRect(contour)
        
        tables.append({
            "type": "table",
            "bounding_box": {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
            },
            "area": area,
        })
    
    logger.info(f"Detected {len(tables)} table regions")
    return tables


def map_coordinates(
    source_box: BoundingBox,
    original_size: Tuple[int, int],
    processed_size: Tuple[int, int]
) -> BoundingBox:
    """
    Map coordinates from processed image back to original image dimensions.
    
    Args:
        source_box: Bounding box in processed image coordinates
        original_size: (width, height) of original image
        processed_size: (width, height) of processed image
        
    Returns:
        BoundingBox in original image coordinates
    """
    if original_size == processed_size:
        return source_box
    
    scale_x = original_size[0] / processed_size[0]
    scale_y = original_size[1] / processed_size[1]
    
    return BoundingBox(
        x=source_box.x * scale_x,
        y=source_box.y * scale_y,
        width=source_box.width * scale_x,
        height=source_box.height * scale_y,
        rotation=source_box.rotation,
    )


def process_document(
    image_data: bytes,
    preprocessing_options: Optional[dict] = None,
    ocr_config: Optional[OcrConfig] = None
) -> Tuple[OcrResult, Dict[str, Any]]:
    """
    Full document processing pipeline.
    
    1. Preprocess image (resize, denoise, deskew, binarize)
    2. Extract text with OCR
    3. Detect document regions
    
    Args:
        image_data: Raw image bytes
        preprocessing_options: Optional preprocessing configuration
        ocr_config: Optional OCR configuration
        
    Returns:
        Tuple of (OcrResult, metadata_dict)
    """
    from .preprocessor import PreprocessingConfig
    
    # Preprocess
    preprocess_config = PreprocessingConfig.from_dict(preprocessing_options or {})
    preprocess_result = preprocess_image(image_data, preprocess_config)
    
    # Extract text
    if ocr_config is None:
        ocr_config = OcrConfig.from_settings()
    
    ocr_result = extract_text_with_data(preprocess_result.image, ocr_config)
    
    # Detect regions
    # Load original image for region detection (before binarization)
    original_image = load_image_from_bytes(image_data)
    detected_regions = detect_document_regions(original_image)
    tables = detect_tables(original_image)
    
    # Add detected regions to result
    ocr_result.detected_regions = detected_regions + tables
    
    # Build metadata
    metadata = {
        "original_size": preprocess_result.original_size,
        "processed_size": preprocess_result.processed_size,
        "preprocessing_applied": preprocess_result.steps_applied,
        "deskew_angle": preprocess_result.deskew_angle,
        "word_count": ocr_result.word_count,
        "average_confidence": ocr_result.average_confidence,
        "regions_detected": len(ocr_result.detected_regions),
    }
    
    logger.info(f"Document processed: {ocr_result.word_count} words, {len(detected_regions)} regions")
    
    return ocr_result, metadata


def extract_text_for_annotations(
    image: np.ndarray,
    annotations: List[Annotation],
    ocr_config: Optional[OcrConfig] = None
) -> List[Annotation]:
    """
    Extract text for each annotation region and update annotations.
    
    Args:
        image: Document image
        annotations: List of annotations with bounding boxes
        ocr_config: OCR configuration
        
    Returns:
        Updated annotations with extracted_text and confidence
    """
    for annotation in annotations:
        if annotation.bounding_box:
            text, confidence = extract_text_from_region(
                image,
                annotation.bounding_box,
                ocr_config
            )
            annotation.extracted_text = text
            annotation.confidence = confidence / 100.0  # Normalize to 0-1
    
    return annotations
