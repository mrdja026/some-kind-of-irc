"""
Image preprocessing pipeline for OCR optimization.

Implements noise reduction, binarization, and deskew correction
to improve OCR accuracy on scanned documents.
"""

import logging
from dataclasses import dataclass
from typing import Tuple, Optional, List
import io

import cv2
import numpy as np
from PIL import Image
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    """Configuration for image preprocessing."""
    noise_reduction: bool = True
    gaussian_sigma: float = 1.0
    gaussian_kernel_size: int = 5
    bilateral_d: int = 9
    bilateral_sigma_color: int = 75
    bilateral_sigma_space: int = 75
    deskew_enabled: bool = True
    deskew_max_angle: float = 15.0
    binarize: bool = True
    adaptive_block_size: int = 11
    adaptive_c: int = 2
    max_width: int = 1024
    max_height: int = 1024
    
    @classmethod
    def from_settings(cls) -> "PreprocessingConfig":
        """Create config from Django settings."""
        return cls(
            noise_reduction=getattr(settings, "PREPROCESSING_NOISE_REDUCTION", True),
            gaussian_sigma=getattr(settings, "PREPROCESSING_GAUSSIAN_SIGMA", 1.0),
            bilateral_d=getattr(settings, "PREPROCESSING_BILATERAL_D", 9),
            deskew_enabled=getattr(settings, "PREPROCESSING_DESKEW_ENABLED", True),
            deskew_max_angle=getattr(settings, "PREPROCESSING_DESKEW_MAX_ANGLE", 15.0),
            max_width=getattr(settings, "MAX_IMAGE_WIDTH", 1024),
            max_height=getattr(settings, "MAX_IMAGE_HEIGHT", 1024),
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "PreprocessingConfig":
        """Create config from dictionary."""
        config = cls.from_settings()
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


@dataclass 
class PreprocessingResult:
    """Result of image preprocessing."""
    image: np.ndarray
    original_size: Tuple[int, int]
    processed_size: Tuple[int, int]
    deskew_angle: Optional[float] = None
    steps_applied: List[str] = None
    
    def __post_init__(self):
        if self.steps_applied is None:
            self.steps_applied = []


def load_image_from_bytes(image_data: bytes) -> np.ndarray:
    """
    Load an image from bytes into OpenCV format.
    
    Args:
        image_data: Raw image bytes (PNG, JPG, etc.)
        
    Returns:
        OpenCV image array (BGR format)
    """
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_data, np.uint8)
    # Decode image
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("Failed to decode image from bytes")
    
    return image


def image_to_bytes(image: np.ndarray, format: str = "PNG") -> bytes:
    """
    Convert OpenCV image to bytes.
    
    Args:
        image: OpenCV image array
        format: Output format (PNG, JPEG)
        
    Returns:
        Image bytes
    """
    if format.upper() == "PNG":
        _, buffer = cv2.imencode(".png", image)
    elif format.upper() in ("JPG", "JPEG"):
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    return buffer.tobytes()


def resize_image(
    image: np.ndarray,
    max_width: int = 1024,
    max_height: int = 1024
) -> Tuple[np.ndarray, Tuple[int, int], Tuple[int, int]]:
    """
    Resize image to fit within max dimensions while preserving aspect ratio.
    
    Args:
        image: Input image
        max_width: Maximum allowed width
        max_height: Maximum allowed height
        
    Returns:
        Tuple of (resized_image, original_size, new_size)
    """
    original_height, original_width = image.shape[:2]
    original_size = (original_width, original_height)
    
    # Check if resizing is needed
    if original_width <= max_width and original_height <= max_height:
        return image, original_size, original_size
    
    # Calculate scaling factor
    scale_w = max_width / original_width
    scale_h = max_height / original_height
    scale = min(scale_w, scale_h)
    
    new_width = int(original_width * scale)
    new_height = int(original_height * scale)
    new_size = (new_width, new_height)
    
    # Resize with high-quality interpolation
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    logger.info(f"Image resized from {original_size} to {new_size}")
    return resized, original_size, new_size


def reduce_noise(
    image: np.ndarray,
    config: PreprocessingConfig
) -> np.ndarray:
    """
    Apply noise reduction using Gaussian blur and bilateral filtering.
    
    The pipeline:
    1. Gaussian blur to remove high-frequency noise
    2. Bilateral filter to preserve edges while smoothing
    
    Args:
        image: Input image (BGR or grayscale)
        config: Preprocessing configuration
        
    Returns:
        Denoised image
    """
    # Ensure we're working with a copy
    result = image.copy()
    
    # Apply Gaussian blur
    kernel_size = config.gaussian_kernel_size
    if kernel_size % 2 == 0:
        kernel_size += 1  # Must be odd
    
    result = cv2.GaussianBlur(
        result,
        (kernel_size, kernel_size),
        config.gaussian_sigma
    )
    
    # Apply bilateral filter for edge-preserving smoothing
    result = cv2.bilateralFilter(
        result,
        d=config.bilateral_d,
        sigmaColor=config.bilateral_sigma_color,
        sigmaSpace=config.bilateral_sigma_space
    )
    
    logger.debug("Noise reduction applied (Gaussian + bilateral)")
    return result


def binarize_image(
    image: np.ndarray,
    config: PreprocessingConfig
) -> np.ndarray:
    """
    Convert image to binary using adaptive thresholding with Otsu's fallback.
    
    Args:
        image: Input image (BGR or grayscale)
        config: Preprocessing configuration
        
    Returns:
        Binary image (0 or 255 values)
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Try adaptive thresholding first
    try:
        block_size = config.adaptive_block_size
        if block_size % 2 == 0:
            block_size += 1  # Must be odd
        
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            config.adaptive_c
        )
        logger.debug("Binarization applied (adaptive threshold)")
    except Exception as e:
        # Fallback to Otsu's method
        logger.warning(f"Adaptive threshold failed, using Otsu's: {e}")
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        logger.debug("Binarization applied (Otsu's method)")
    
    return binary


def estimate_skew_angle(image: np.ndarray, max_angle: float = 15.0) -> float:
    """
    Estimate document skew angle using Hough transform line detection.
    
    Args:
        image: Input image (grayscale or binary preferred)
        max_angle: Maximum allowed angle in degrees
        
    Returns:
        Estimated skew angle in degrees
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=100,
        minLineLength=100,
        maxLineGap=10
    )
    
    if lines is None or len(lines) == 0:
        logger.debug("No lines detected for skew estimation")
        return 0.0
    
    # Calculate angles of all detected lines
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Only consider nearly horizontal lines
            if abs(angle) < max_angle:
                angles.append(angle)
    
    if not angles:
        logger.debug("No suitable lines for skew estimation")
        return 0.0
    
    # Use median angle for robustness
    median_angle = np.median(angles)
    
    logger.debug(f"Estimated skew angle: {median_angle:.2f} degrees")
    return float(median_angle)


def deskew_image(
    image: np.ndarray,
    angle: Optional[float] = None,
    max_angle: float = 15.0
) -> Tuple[np.ndarray, float]:
    """
    Correct document skew using affine transformation.
    
    Args:
        image: Input image
        angle: Skew angle (if None, will be estimated)
        max_angle: Maximum allowed angle for estimation
        
    Returns:
        Tuple of (deskewed_image, applied_angle)
    """
    if angle is None:
        angle = estimate_skew_angle(image, max_angle)
    
    if abs(angle) < 0.5:
        # Skip if angle is negligible
        logger.debug("Skew angle negligible, skipping deskew")
        return image, 0.0
    
    if abs(angle) > max_angle:
        logger.warning(f"Skew angle {angle:.2f} exceeds max {max_angle}, clamping")
        angle = max_angle if angle > 0 else -max_angle
    
    # Get image dimensions
    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    
    # Create rotation matrix
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    
    # Calculate new bounding box size
    cos = np.abs(rotation_matrix[0, 0])
    sin = np.abs(rotation_matrix[0, 1])
    new_width = int(height * sin + width * cos)
    new_height = int(height * cos + width * sin)
    
    # Adjust rotation matrix for translation
    rotation_matrix[0, 2] += (new_width - width) / 2
    rotation_matrix[1, 2] += (new_height - height) / 2
    
    # Apply rotation
    deskewed = cv2.warpAffine(
        image,
        rotation_matrix,
        (new_width, new_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE
    )
    
    logger.info(f"Image deskewed by {angle:.2f} degrees")
    return deskewed, angle


def convert_to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert image to grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def enhance_contrast(image: np.ndarray) -> np.ndarray:
    """
    Enhance image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    logger.debug("Contrast enhancement applied (CLAHE)")
    return enhanced


def preprocess_image(
    image_data: bytes,
    config: Optional[PreprocessingConfig] = None
) -> PreprocessingResult:
    """
    Full preprocessing pipeline for OCR optimization.
    
    Pipeline stages:
    1. Load image from bytes
    2. Resize to max dimensions
    3. Noise reduction (Gaussian + bilateral)
    4. Deskew correction
    5. Binarization (adaptive threshold)
    
    Args:
        image_data: Raw image bytes
        config: Preprocessing configuration (uses defaults if None)
        
    Returns:
        PreprocessingResult with processed image and metadata
    """
    if config is None:
        config = PreprocessingConfig.from_settings()
    
    steps_applied = []
    deskew_angle = None
    
    # Load image
    image = load_image_from_bytes(image_data)
    original_size = (image.shape[1], image.shape[0])
    
    # Resize if needed
    image, _, processed_size = resize_image(
        image,
        max_width=config.max_width,
        max_height=config.max_height
    )
    if processed_size != original_size:
        steps_applied.append("resize")
    
    # Noise reduction
    if config.noise_reduction:
        image = reduce_noise(image, config)
        steps_applied.append("noise_reduction")
    
    # Deskew
    if config.deskew_enabled:
        image, deskew_angle = deskew_image(image, max_angle=config.deskew_max_angle)
        if deskew_angle != 0.0:
            steps_applied.append("deskew")
    
    # Binarization
    if config.binarize:
        image = binarize_image(image, config)
        steps_applied.append("binarize")
    
    logger.info(f"Preprocessing complete: {steps_applied}")
    
    return PreprocessingResult(
        image=image,
        original_size=original_size,
        processed_size=processed_size,
        deskew_angle=deskew_angle,
        steps_applied=steps_applied,
    )


def preprocess_for_ocr(
    image_data: bytes,
    options: Optional[dict] = None
) -> Tuple[np.ndarray, dict]:
    """
    Convenience function that returns preprocessed image and metadata.
    
    Args:
        image_data: Raw image bytes
        options: Optional preprocessing options dict
        
    Returns:
        Tuple of (processed_image, metadata_dict)
    """
    config = PreprocessingConfig.from_dict(options or {})
    result = preprocess_image(image_data, config)
    
    metadata = {
        "original_size": result.original_size,
        "processed_size": result.processed_size,
        "deskew_angle": result.deskew_angle,
        "steps_applied": result.steps_applied,
    }
    
    return result.image, metadata
