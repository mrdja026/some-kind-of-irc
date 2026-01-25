"""
Template matching service using ORB features and RANSAC homography.

Provides intelligent template application to documents by detecting visual
similarities and transforming annotation bounding boxes accordingly.

Algorithm:
1. Extract ORB keypoints from template and target images
2. Match descriptors using BFMatcher with Hamming distance
3. Apply ratio test (Lowe's ratio = 0.75) to filter ambiguous matches
4. Compute homography matrix using RANSAC
5. Transform template bounding boxes to target coordinates
6. Validate transformed boxes (area ratio, aspect ratio checks)

Fallback Strategy:
- If feature matching confidence < 60%, prompt user for manual anchor points
"""

import logging
import pickle
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

import cv2
import numpy as np

from storage.in_memory import BoundingBox, Template, TemplateLabel

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatchConfig:
    """Configuration for template matching algorithm."""
    
    # ORB parameters
    orb_nfeatures: int = 500
    orb_scale_factor: float = 1.2
    orb_nlevels: int = 8
    orb_edge_threshold: int = 31
    orb_first_level: int = 0
    orb_wta_k: int = 2
    orb_patch_size: int = 31
    orb_fast_threshold: int = 20
    
    # Matching parameters
    ratio_threshold: float = 0.75  # Lowe's ratio test threshold
    min_match_count: int = 10  # Minimum good matches required
    
    # RANSAC parameters
    ransac_reproj_threshold: float = 5.0
    ransac_max_iters: int = 2000
    ransac_confidence: float = 0.995
    
    # Confidence thresholds
    min_confidence: float = 0.6  # Below this, require manual anchors
    
    # Validation parameters
    max_area_ratio: float = 2.0  # Max change in bounding box area
    max_aspect_change: float = 0.5  # Max change in aspect ratio
    min_box_area: float = 100.0  # Minimum valid box area in pixels
    
    @classmethod
    def from_dict(cls, data: dict) -> "TemplateMatchConfig":
        """Create config from dictionary."""
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config


@dataclass
class TransformedBox:
    """A transformed bounding box with validation status."""
    original_label: TemplateLabel
    bounding_box: BoundingBox
    is_valid: bool = True
    validation_error: Optional[str] = None


@dataclass
class MatchResult:
    """Result of template matching operation."""
    success: bool
    confidence: float
    transformed_boxes: List[TransformedBox] = field(default_factory=list)
    homography_matrix: Optional[np.ndarray] = None
    inlier_count: int = 0
    total_matches: int = 0
    error_message: Optional[str] = None
    requires_manual_anchors: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "confidence": self.confidence,
            "transformed_boxes": [
                {
                    "label_name": tb.original_label.label_name,
                    "label_type": tb.original_label.label_type.value,
                    "bounding_box": tb.bounding_box.to_dict(),
                    "is_valid": tb.is_valid,
                    "validation_error": tb.validation_error,
                }
                for tb in self.transformed_boxes
            ],
            "inlier_count": self.inlier_count,
            "total_matches": self.total_matches,
            "error_message": self.error_message,
            "requires_manual_anchors": self.requires_manual_anchors,
        }


def extract_orb_features(
    image: np.ndarray,
    config: Optional[TemplateMatchConfig] = None
) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
    """
    Extract ORB keypoints and descriptors from an image.
    
    Args:
        image: OpenCV image (BGR or grayscale)
        config: ORB configuration parameters
        
    Returns:
        Tuple of (keypoints, descriptors). Descriptors may be None if no keypoints found.
    """
    if config is None:
        config = TemplateMatchConfig()
    
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Create ORB detector
    orb = cv2.ORB_create(
        nfeatures=config.orb_nfeatures,
        scaleFactor=config.orb_scale_factor,
        nlevels=config.orb_nlevels,
        edgeThreshold=config.orb_edge_threshold,
        firstLevel=config.orb_first_level,
        WTA_K=config.orb_wta_k,
        patchSize=config.orb_patch_size,
        fastThreshold=config.orb_fast_threshold,
    )
    
    # Detect keypoints and compute descriptors
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    
    logger.debug(f"Extracted {len(keypoints)} ORB keypoints")
    return keypoints, descriptors


def serialize_keypoints(
    keypoints: List[cv2.KeyPoint],
    descriptors: np.ndarray
) -> bytes:
    """
    Serialize keypoints and descriptors for storage.
    
    OpenCV KeyPoints are not directly picklable, so we convert to tuples.
    
    Args:
        keypoints: List of cv2.KeyPoint objects
        descriptors: Numpy array of descriptors
        
    Returns:
        Pickled bytes containing keypoint data and descriptors
    """
    # Convert keypoints to serializable format
    kp_data = []
    for kp in keypoints:
        kp_data.append({
            "pt": kp.pt,
            "size": kp.size,
            "angle": kp.angle,
            "response": kp.response,
            "octave": kp.octave,
            "class_id": kp.class_id,
        })
    
    data = {
        "keypoints": kp_data,
        "descriptors": descriptors,
        "version": 1,
    }
    
    return pickle.dumps(data)


def deserialize_keypoints(data: bytes) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
    """
    Deserialize keypoints and descriptors from stored bytes.
    
    Args:
        data: Pickled bytes from serialize_keypoints()
        
    Returns:
        Tuple of (keypoints, descriptors)
    """
    unpacked = pickle.loads(data)
    
    # Reconstruct KeyPoints
    keypoints = []
    for kp_data in unpacked["keypoints"]:
        kp = cv2.KeyPoint(
            x=kp_data["pt"][0],
            y=kp_data["pt"][1],
            size=kp_data["size"],
            angle=kp_data["angle"],
            response=kp_data["response"],
            octave=kp_data["octave"],
            class_id=kp_data["class_id"],
        )
        keypoints.append(kp)
    
    descriptors = unpacked["descriptors"]
    
    return keypoints, descriptors


def match_features(
    descriptors1: np.ndarray,
    descriptors2: np.ndarray,
    config: Optional[TemplateMatchConfig] = None
) -> List[cv2.DMatch]:
    """
    Match descriptors using BFMatcher with Hamming distance and Lowe's ratio test.
    
    Args:
        descriptors1: Descriptors from template image
        descriptors2: Descriptors from target image
        config: Matching configuration
        
    Returns:
        List of good matches after ratio test
    """
    if config is None:
        config = TemplateMatchConfig()
    
    if descriptors1 is None or descriptors2 is None:
        logger.warning("One or both descriptor sets are None")
        return []
    
    if len(descriptors1) < 2 or len(descriptors2) < 2:
        logger.warning("Not enough descriptors for matching")
        return []
    
    # Create BFMatcher with Hamming distance (for binary descriptors like ORB)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    
    # Find k=2 nearest neighbors for ratio test
    try:
        matches = bf.knnMatch(descriptors1, descriptors2, k=2)
    except cv2.error as e:
        logger.error(f"BFMatcher failed: {e}")
        return []
    
    # Apply Lowe's ratio test
    good_matches = []
    for match_pair in matches:
        if len(match_pair) < 2:
            continue
        m, n = match_pair
        if m.distance < config.ratio_threshold * n.distance:
            good_matches.append(m)
    
    logger.debug(f"Found {len(good_matches)}/{len(matches)} good matches after ratio test")
    return good_matches


def compute_homography(
    keypoints1: List[cv2.KeyPoint],
    keypoints2: List[cv2.KeyPoint],
    matches: List[cv2.DMatch],
    config: Optional[TemplateMatchConfig] = None
) -> Tuple[Optional[np.ndarray], int]:
    """
    Compute homography matrix using RANSAC.
    
    Args:
        keypoints1: Keypoints from template image
        keypoints2: Keypoints from target image
        matches: Good matches from match_features()
        config: RANSAC configuration
        
    Returns:
        Tuple of (homography_matrix, inlier_count). Matrix is None if computation fails.
    """
    if config is None:
        config = TemplateMatchConfig()
    
    if len(matches) < config.min_match_count:
        logger.warning(f"Not enough matches ({len(matches)} < {config.min_match_count})")
        return None, 0
    
    # Extract matched point coordinates
    src_pts = np.float32([keypoints1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([keypoints2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    
    # Find homography using RANSAC
    try:
        homography, mask = cv2.findHomography(
            src_pts,
            dst_pts,
            cv2.RANSAC,
            config.ransac_reproj_threshold,
            maxIters=config.ransac_max_iters,
            confidence=config.ransac_confidence,
        )
    except cv2.error as e:
        logger.error(f"Homography computation failed: {e}")
        return None, 0
    
    if homography is None:
        logger.warning("Homography matrix is None")
        return None, 0
    
    # Count inliers
    inlier_count = int(mask.ravel().sum()) if mask is not None else 0
    
    logger.debug(f"Computed homography with {inlier_count}/{len(matches)} inliers")
    return homography, inlier_count


def transform_point(point: Tuple[float, float], homography: np.ndarray) -> Tuple[float, float]:
    """
    Transform a single point using homography matrix.
    
    Args:
        point: (x, y) coordinates
        homography: 3x3 homography matrix
        
    Returns:
        Transformed (x, y) coordinates
    """
    pt = np.array([[point[0], point[1], 1.0]], dtype=np.float32).T
    transformed = homography @ pt
    w = transformed[2, 0]
    if abs(w) < 1e-10:
        w = 1e-10  # Prevent division by zero
    return float(transformed[0, 0] / w), float(transformed[1, 0] / w)


def transform_bounding_box(
    bbox: BoundingBox,
    homography: np.ndarray,
    image_dimensions: Optional[Tuple[int, int]] = None
) -> BoundingBox:
    """
    Transform a bounding box using homography matrix.
    
    The four corners are transformed, then a new axis-aligned bounding box
    is computed from the transformed corners.
    
    Args:
        bbox: Original bounding box
        homography: 3x3 homography matrix
        image_dimensions: Optional (width, height) to clamp coordinates
        
    Returns:
        Transformed bounding box (axis-aligned)
    """
    # Get four corners of the bounding box
    corners = [
        (bbox.x, bbox.y),  # Top-left
        (bbox.x + bbox.width, bbox.y),  # Top-right
        (bbox.x + bbox.width, bbox.y + bbox.height),  # Bottom-right
        (bbox.x, bbox.y + bbox.height),  # Bottom-left
    ]
    
    # Transform all corners
    transformed_corners = [transform_point(pt, homography) for pt in corners]
    
    # Compute axis-aligned bounding box from transformed corners
    xs = [pt[0] for pt in transformed_corners]
    ys = [pt[1] for pt in transformed_corners]
    
    new_x = min(xs)
    new_y = min(ys)
    new_width = max(xs) - new_x
    new_height = max(ys) - new_y
    
    # Clamp to image dimensions if provided
    if image_dimensions:
        img_width, img_height = image_dimensions
        new_x = max(0, min(new_x, img_width - 1))
        new_y = max(0, min(new_y, img_height - 1))
        new_width = min(new_width, img_width - new_x)
        new_height = min(new_height, img_height - new_y)
    
    return BoundingBox(
        x=new_x,
        y=new_y,
        width=new_width,
        height=new_height,
        rotation=0.0,  # Axis-aligned after transformation
    )


def validate_transformed_box(
    original_bbox: BoundingBox,
    transformed_bbox: BoundingBox,
    config: Optional[TemplateMatchConfig] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate a transformed bounding box against sanity checks.
    
    Checks:
    - Minimum area
    - Area ratio (not too different from original)
    - Aspect ratio change (not too distorted)
    - Positive dimensions
    
    Args:
        original_bbox: Original bounding box from template
        transformed_bbox: Transformed bounding box
        config: Validation parameters
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if config is None:
        config = TemplateMatchConfig()
    
    # Check positive dimensions
    if transformed_bbox.width <= 0 or transformed_bbox.height <= 0:
        return False, "Invalid dimensions (non-positive width or height)"
    
    # Check minimum area
    area = transformed_bbox.width * transformed_bbox.height
    if area < config.min_box_area:
        return False, f"Area too small ({area:.1f} < {config.min_box_area})"
    
    # Check area ratio
    original_area = original_bbox.width * original_bbox.height
    if original_area > 0:
        area_ratio = area / original_area
        if area_ratio > config.max_area_ratio or area_ratio < (1.0 / config.max_area_ratio):
            return False, f"Area ratio out of bounds ({area_ratio:.2f})"
    
    # Check aspect ratio change
    original_aspect = original_bbox.width / original_bbox.height if original_bbox.height > 0 else 1.0
    new_aspect = transformed_bbox.width / transformed_bbox.height if transformed_bbox.height > 0 else 1.0
    aspect_change = abs(new_aspect - original_aspect) / original_aspect if original_aspect > 0 else 0
    
    if aspect_change > config.max_aspect_change:
        return False, f"Aspect ratio changed too much ({aspect_change:.2f} > {config.max_aspect_change})"
    
    return True, None


def calculate_match_confidence(
    total_matches: int,
    inlier_count: int,
    valid_boxes: int,
    total_boxes: int,
    config: Optional[TemplateMatchConfig] = None
) -> float:
    """
    Calculate overall matching confidence score.
    
    Factors:
    - Inlier ratio (inliers / total matches)
    - Valid box ratio (valid boxes / total boxes)
    - Absolute match count
    
    Args:
        total_matches: Number of good matches
        inlier_count: Number of RANSAC inliers
        valid_boxes: Number of valid transformed boxes
        total_boxes: Total boxes to transform
        config: Configuration with thresholds
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if config is None:
        config = TemplateMatchConfig()
    
    # Inlier ratio component (0.0 - 0.4 weight)
    inlier_ratio = inlier_count / total_matches if total_matches > 0 else 0.0
    inlier_score = min(inlier_ratio, 1.0) * 0.4
    
    # Valid boxes component (0.0 - 0.3 weight)
    box_ratio = valid_boxes / total_boxes if total_boxes > 0 else 1.0
    box_score = box_ratio * 0.3
    
    # Absolute match count component (0.0 - 0.3 weight)
    # Saturates at 50 matches = full score
    match_score = min(total_matches / 50.0, 1.0) * 0.3
    
    confidence = inlier_score + box_score + match_score
    
    return min(max(confidence, 0.0), 1.0)


def match_template_to_document(
    template: Template,
    document_image: np.ndarray,
    document_dimensions: Optional[Tuple[int, int]] = None,
    config: Optional[TemplateMatchConfig] = None
) -> MatchResult:
    """
    Match a template to a document image and transform annotations.
    
    Full pipeline:
    1. Load/extract template keypoints
    2. Extract document keypoints
    3. Match features using BFMatcher
    4. Compute homography if enough matches
    5. Transform template labels to document coordinates
    6. Validate transformed boxes
    7. Calculate confidence score
    
    Args:
        template: Template with labels and optional stored keypoints
        document_image: Target document image (BGR or grayscale)
        document_dimensions: (width, height) for coordinate clamping
        config: Matching configuration
        
    Returns:
        MatchResult with transformed boxes and confidence score
    """
    if config is None:
        config = TemplateMatchConfig()
    
    # Determine document dimensions
    if document_dimensions is None:
        if len(document_image.shape) == 3:
            document_dimensions = (document_image.shape[1], document_image.shape[0])
        else:
            document_dimensions = (document_image.shape[1], document_image.shape[0])
    
    # Check if template has stored keypoints
    if template.feature_keypoints is not None:
        try:
            template_keypoints, template_descriptors = deserialize_keypoints(template.feature_keypoints)
            logger.info(f"Using {len(template_keypoints)} stored keypoints from template")
        except Exception as e:
            logger.warning(f"Failed to deserialize template keypoints: {e}")
            return MatchResult(
                success=False,
                confidence=0.0,
                error_message=f"Failed to load template keypoints: {e}",
                requires_manual_anchors=True,
            )
    else:
        # No keypoints stored - require manual anchors or use relative positioning
        logger.info("Template has no stored keypoints, requires manual anchors")
        return MatchResult(
            success=False,
            confidence=0.0,
            error_message="Template has no stored feature keypoints",
            requires_manual_anchors=True,
        )
    
    # Extract keypoints from document image
    document_keypoints, document_descriptors = extract_orb_features(document_image, config)
    
    if document_descriptors is None or len(document_keypoints) < config.min_match_count:
        logger.warning(f"Insufficient keypoints in document ({len(document_keypoints)})")
        return MatchResult(
            success=False,
            confidence=0.0,
            error_message=f"Insufficient keypoints in document ({len(document_keypoints)})",
            requires_manual_anchors=True,
        )
    
    # Match features
    good_matches = match_features(template_descriptors, document_descriptors, config)
    total_matches = len(good_matches)
    
    if total_matches < config.min_match_count:
        logger.warning(f"Insufficient matches ({total_matches} < {config.min_match_count})")
        return MatchResult(
            success=False,
            confidence=0.0,
            total_matches=total_matches,
            error_message=f"Insufficient feature matches ({total_matches})",
            requires_manual_anchors=True,
        )
    
    # Compute homography
    homography, inlier_count = compute_homography(
        template_keypoints, document_keypoints, good_matches, config
    )
    
    if homography is None:
        logger.warning("Failed to compute homography matrix")
        return MatchResult(
            success=False,
            confidence=0.0,
            total_matches=total_matches,
            inlier_count=0,
            error_message="Failed to compute homography matrix",
            requires_manual_anchors=True,
        )
    
    # Transform template labels
    transformed_boxes: List[TransformedBox] = []
    valid_count = 0
    
    for label in template.labels:
        # Convert relative coordinates to absolute using document dimensions
        original_bbox = BoundingBox(
            x=label.relative_x * document_dimensions[0],
            y=label.relative_y * document_dimensions[1],
            width=label.relative_width * document_dimensions[0],
            height=label.relative_height * document_dimensions[1],
        )
        
        # Transform bounding box
        transformed_bbox = transform_bounding_box(
            original_bbox, homography, document_dimensions
        )
        
        # Validate
        is_valid, validation_error = validate_transformed_box(
            original_bbox, transformed_bbox, config
        )
        
        if is_valid:
            valid_count += 1
        
        transformed_boxes.append(TransformedBox(
            original_label=label,
            bounding_box=transformed_bbox,
            is_valid=is_valid,
            validation_error=validation_error,
        ))
    
    # Calculate confidence
    confidence = calculate_match_confidence(
        total_matches, inlier_count, valid_count, len(template.labels), config
    )
    
    # Check confidence threshold
    requires_manual_anchors = confidence < config.min_confidence
    
    logger.info(
        f"Template matching complete: confidence={confidence:.2f}, "
        f"matches={total_matches}, inliers={inlier_count}, "
        f"valid_boxes={valid_count}/{len(template.labels)}"
    )
    
    return MatchResult(
        success=not requires_manual_anchors,
        confidence=confidence,
        transformed_boxes=transformed_boxes,
        homography_matrix=homography,
        inlier_count=inlier_count,
        total_matches=total_matches,
        requires_manual_anchors=requires_manual_anchors,
        error_message="Low confidence - manual anchors recommended" if requires_manual_anchors else None,
    )


class TemplateMatcher:
    """
    Class wrapper for template matching operations.
    
    Provides a convenient interface for template matching and keypoint management.
    """
    
    def __init__(self, config: Optional[TemplateMatchConfig] = None):
        """Initialize with optional configuration."""
        self.config = config or TemplateMatchConfig()
    
    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """Extract ORB features from an image."""
        return extract_orb_features(image, self.config)
    
    def serialize_features(
        self, 
        keypoints: List[cv2.KeyPoint], 
        descriptors: np.ndarray
    ) -> bytes:
        """Serialize features for storage."""
        return serialize_keypoints(keypoints, descriptors)
    
    def deserialize_features(self, data: bytes) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """Deserialize features from storage."""
        return deserialize_keypoints(data)
    
    def match(
        self,
        template: Template,
        document_image: np.ndarray,
        document_dimensions: Optional[Tuple[int, int]] = None
    ) -> MatchResult:
        """Match template to document."""
        return match_template_to_document(
            template, document_image, document_dimensions, self.config
        )
    
    def prepare_template_keypoints(
        self,
        template_image: np.ndarray
    ) -> Optional[bytes]:
        """
        Extract and serialize keypoints from a template image.
        
        Use this when creating a template from a document.
        
        Args:
            template_image: Source image for the template
            
        Returns:
            Serialized keypoints bytes, or None if extraction fails
        """
        keypoints, descriptors = self.extract_features(template_image)
        
        if descriptors is None or len(keypoints) < self.config.min_match_count:
            logger.warning(f"Insufficient keypoints extracted ({len(keypoints)})")
            return None
        
        return self.serialize_features(keypoints, descriptors)
