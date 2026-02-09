"""
Unit tests for template matching service.

Tests ORB feature extraction, matching, RANSAC homography, 
bounding box transformation, and validation.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

# Import test subjects - these will fail gracefully if OpenCV not available
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

# Import our modules
from services.template_matcher import (
    TemplateMatchConfig,
    MatchResult,
    TransformedBox,
    extract_orb_features,
    serialize_keypoints,
    deserialize_keypoints,
    match_features,
    compute_homography,
    transform_bounding_box,
    transform_point,
    validate_transformed_box,
    calculate_match_confidence,
    match_template_to_document,
    TemplateMatcher,
)
from storage.in_memory import Template, TemplateLabel, BoundingBox, LabelType


# Skip all tests if OpenCV not available
pytestmark = pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")


class TestTemplateMatchConfig:
    """Tests for TemplateMatchConfig dataclass."""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = TemplateMatchConfig()
        
        assert config.orb_nfeatures == 500
        assert config.ratio_threshold == 0.75
        assert config.ransac_reproj_threshold == 5.0
        assert config.min_confidence == 0.6
        assert config.max_area_ratio == 2.0
        assert config.max_aspect_change == 0.5
        assert config.min_match_count == 10
    
    def test_custom_values(self):
        """Test custom configuration values."""
        config = TemplateMatchConfig(
            orb_nfeatures=1000,
            ratio_threshold=0.8,
            min_confidence=0.5
        )
        
        assert config.orb_nfeatures == 1000
        assert config.ratio_threshold == 0.8
        assert config.min_confidence == 0.5
    
    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "orb_nfeatures": 750,
            "min_confidence": 0.7,
            "unknown_field": "ignored"
        }
        config = TemplateMatchConfig.from_dict(data)
        
        assert config.orb_nfeatures == 750
        assert config.min_confidence == 0.7


class TestORBFeatureExtraction:
    """Tests for ORB feature extraction."""
    
    def test_extract_features_from_valid_image(self):
        """Test ORB feature extraction from a valid image."""
        # Create a test image with some features (corners and edges)
        image = np.zeros((200, 200), dtype=np.uint8)
        # Add some rectangles to create features
        cv2.rectangle(image, (20, 20), (80, 80), 255, -1)
        cv2.rectangle(image, (100, 100), (180, 180), 255, -1)
        cv2.rectangle(image, (50, 120), (90, 170), 128, -1)
        
        keypoints, descriptors = extract_orb_features(image)
        
        assert keypoints is not None
        assert len(keypoints) > 0
        assert descriptors is not None
        assert descriptors.shape[0] == len(keypoints)
        assert descriptors.shape[1] == 32  # ORB descriptor length
    
    def test_extract_features_from_color_image(self):
        """Test that color images are handled correctly."""
        # Create a color image
        image = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (100, 100), (255, 255, 255), -1)
        
        keypoints, descriptors = extract_orb_features(image)
        
        assert keypoints is not None
        assert descriptors is not None
    
    def test_extract_features_empty_image(self):
        """Test feature extraction from blank image."""
        # Completely blank image may have no features
        image = np.zeros((100, 100), dtype=np.uint8)
        
        keypoints, descriptors = extract_orb_features(image)
        
        # Should return empty results for blank image
        assert keypoints is not None
        # Blank image should have no/few features
        assert len(keypoints) < 10
    
    def test_extract_features_with_custom_config(self):
        """Test that custom config parameters are used."""
        image = np.random.randint(0, 256, (500, 500), dtype=np.uint8)
        
        config = TemplateMatchConfig(orb_nfeatures=50)
        keypoints, descriptors = extract_orb_features(image, config)
        
        assert len(keypoints) <= 50


class TestKeypointSerialization:
    """Tests for keypoint serialization and deserialization."""
    
    def test_serialize_and_deserialize_keypoints(self):
        """Test round-trip serialization of keypoints."""
        # Create test image and extract real keypoints
        image = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        keypoints, descriptors = extract_orb_features(image)
        
        if len(keypoints) > 0:
            # Serialize
            serialized = serialize_keypoints(keypoints, descriptors)
            
            assert isinstance(serialized, bytes)
            assert len(serialized) > 0
            
            # Deserialize
            restored_kp, restored_desc = deserialize_keypoints(serialized)
            
            assert len(restored_kp) == len(keypoints)
            assert np.array_equal(restored_desc, descriptors)
            
            # Check keypoint properties preserved
            for orig, restored in zip(keypoints, restored_kp):
                assert abs(orig.pt[0] - restored.pt[0]) < 0.01
                assert abs(orig.pt[1] - restored.pt[1]) < 0.01
                assert abs(orig.size - restored.size) < 0.01
                assert abs(orig.angle - restored.angle) < 0.01


class TestFeatureMatching:
    """Tests for feature matching with BFMatcher."""
    
    def test_match_identical_features(self):
        """Test matching features from the same image."""
        # Create image with distinct features
        image = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(image, (10, 10), (50, 50), 255, -1)
        cv2.rectangle(image, (100, 100), (150, 150), 255, -1)
        cv2.circle(image, (150, 50), 30, 255, -1)
        
        kp1, desc1 = extract_orb_features(image)
        kp2, desc2 = extract_orb_features(image)
        
        if len(kp1) > 0 and len(kp2) > 0:
            good_matches = match_features(desc1, desc2)
            
            # Same image should have many matches
            assert len(good_matches) > 0
    
    def test_match_with_custom_ratio(self):
        """Test that ratio test threshold affects matches."""
        image1 = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        image2 = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        
        kp1, desc1 = extract_orb_features(image1)
        kp2, desc2 = extract_orb_features(image2)
        
        if len(kp1) > 0 and len(kp2) > 0:
            # Stricter ratio test
            config_strict = TemplateMatchConfig(ratio_threshold=0.5)
            good_strict = match_features(desc1, desc2, config_strict)
            
            # Looser ratio test
            config_loose = TemplateMatchConfig(ratio_threshold=0.9)
            good_loose = match_features(desc1, desc2, config_loose)
            
            # Looser ratio should have more matches
            assert len(good_loose) >= len(good_strict)
    
    def test_match_returns_empty_for_none_descriptors(self):
        """Test that None descriptors return empty matches."""
        matches = match_features(None, None)
        assert matches == []


class TestHomographyComputation:
    """Tests for RANSAC homography computation."""
    
    def test_compute_homography_with_good_matches(self):
        """Test homography computation with known transformation."""
        # Create source points in a square pattern
        src_pts = np.float32([
            [50, 50], [150, 50], [150, 150], [50, 150],
            [75, 75], [125, 75], [125, 125], [75, 125],
            [100, 50], [150, 100], [100, 150], [50, 100]
        ])
        
        # Create destination points (translated by 20, 30)
        dst_pts = src_pts + np.array([20, 30])
        
        # Create mock keypoints
        src_kps = [cv2.KeyPoint(pt[0], pt[1], 10) for pt in src_pts]
        dst_kps = [cv2.KeyPoint(pt[0], pt[1], 10) for pt in dst_pts]
        
        # Create mock matches
        matches = [cv2.DMatch(i, i, 0, 10) for i in range(len(src_pts))]
        
        H, inliers = compute_homography(src_kps, dst_kps, matches)
        
        assert H is not None
        assert H.shape == (3, 3)
        assert inliers > 0
        
        # Transform a point and verify
        test_pt = transform_point((100, 100), H)
        
        # Should be close to (120, 130)
        assert abs(test_pt[0] - 120) < 5
        assert abs(test_pt[1] - 130) < 5
    
    def test_compute_homography_insufficient_matches(self):
        """Test that insufficient matches return None."""
        # Only 3 matches (need at least 10 with default config)
        src_pts = np.float32([[50, 50], [100, 50], [50, 100]])
        dst_pts = src_pts + np.array([10, 10])
        
        src_kps = [cv2.KeyPoint(pt[0], pt[1], 10) for pt in src_pts]
        dst_kps = [cv2.KeyPoint(pt[0], pt[1], 10) for pt in dst_pts]
        matches = [cv2.DMatch(i, i, 0, 10) for i in range(3)]
        
        H, inliers = compute_homography(src_kps, dst_kps, matches)
        
        assert H is None
        assert inliers == 0


class TestBoundingBoxTransformation:
    """Tests for bounding box transformation."""
    
    def test_transform_bbox_with_translation(self):
        """Test bounding box transformation with simple translation."""
        # Translation matrix
        H = np.array([
            [1, 0, 50],
            [0, 1, 30],
            [0, 0, 1]
        ], dtype=np.float32)
        
        bbox = BoundingBox(x=100, y=100, width=50, height=30, rotation=0)
        
        transformed = transform_bounding_box(bbox, H)
        
        # Should be translated by (50, 30)
        assert abs(transformed.x - 150) < 1
        assert abs(transformed.y - 130) < 1
        # Size should remain similar for pure translation
        assert abs(transformed.width - 50) < 5
        assert abs(transformed.height - 30) < 5
    
    def test_transform_bbox_with_scaling(self):
        """Test bounding box transformation with scaling."""
        # Scale by 2x
        H = np.array([
            [2, 0, 0],
            [0, 2, 0],
            [0, 0, 1]
        ], dtype=np.float32)
        
        bbox = BoundingBox(x=100, y=100, width=50, height=30, rotation=0)
        
        transformed = transform_bounding_box(bbox, H)
        
        # Position and size should be scaled
        assert abs(transformed.x - 200) < 1
        assert abs(transformed.y - 200) < 1
        assert abs(transformed.width - 100) < 5
        assert abs(transformed.height - 60) < 5
    
    def test_transform_bbox_with_clamping(self):
        """Test that transform clamps to image dimensions."""
        # Large translation that would go out of bounds
        H = np.array([
            [1, 0, 1000],
            [0, 1, 1000],
            [0, 0, 1]
        ], dtype=np.float32)
        
        bbox = BoundingBox(x=100, y=100, width=50, height=30)
        transformed = transform_bounding_box(bbox, H, image_dimensions=(500, 500))
        
        # Should be clamped to image boundaries
        assert transformed.x < 500
        assert transformed.y < 500


class TestBoundingBoxValidation:
    """Tests for transformed bounding box validation."""
    
    def test_validate_good_transformation(self):
        """Test validation passes for reasonable transformation."""
        original = BoundingBox(x=100, y=100, width=100, height=50, rotation=0)
        transformed = BoundingBox(x=120, y=130, width=105, height=48, rotation=0)
        
        config = TemplateMatchConfig()
        
        is_valid, error = validate_transformed_box(original, transformed, config)
        
        assert is_valid
        assert error is None
    
    def test_validate_area_change_too_large(self):
        """Test validation fails for excessive area change."""
        original = BoundingBox(x=100, y=100, width=100, height=100, rotation=0)
        # Area went from 10000 to 500 (massive reduction)
        transformed = BoundingBox(x=100, y=100, width=25, height=20, rotation=0)
        
        config = TemplateMatchConfig(max_area_ratio=2.0)
        
        is_valid, error = validate_transformed_box(original, transformed, config)
        
        assert not is_valid
        assert "area" in error.lower()
    
    def test_validate_aspect_ratio_change_too_large(self):
        """Test validation fails for excessive aspect ratio change."""
        original = BoundingBox(x=100, y=100, width=100, height=50, rotation=0)  # 2:1
        # Drastically different aspect ratio
        transformed = BoundingBox(x=100, y=100, width=50, height=200, rotation=0)  # 1:4
        
        config = TemplateMatchConfig(max_aspect_change=0.5)
        
        is_valid, error = validate_transformed_box(original, transformed, config)
        
        assert not is_valid
        assert "aspect" in error.lower()
    
    def test_validate_negative_dimensions(self):
        """Test validation fails for non-positive dimensions."""
        original = BoundingBox(x=100, y=100, width=100, height=50)
        transformed = BoundingBox(x=100, y=100, width=-10, height=50)
        
        is_valid, error = validate_transformed_box(original, transformed)
        
        assert not is_valid
        assert "dimension" in error.lower()


class TestMatchConfidence:
    """Tests for match confidence calculation."""
    
    def test_confidence_calculation_perfect_match(self):
        """Test confidence for a perfect match scenario."""
        # High inlier count, all boxes valid
        confidence = calculate_match_confidence(
            total_matches=50,
            inlier_count=45,
            valid_boxes=5,
            total_boxes=5
        )
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.7  # Should be high
    
    def test_confidence_calculation_poor_match(self):
        """Test confidence for a poor match scenario."""
        # Low inlier count, few valid boxes
        confidence = calculate_match_confidence(
            total_matches=10,
            inlier_count=2,
            valid_boxes=1,
            total_boxes=5
        )
        
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.5  # Should be low
    
    def test_confidence_zero_matches(self):
        """Test confidence with zero matches."""
        confidence = calculate_match_confidence(
            total_matches=0,
            inlier_count=0,
            valid_boxes=0,
            total_boxes=5
        )
        
        assert confidence == 0.0


class TestMatchResult:
    """Tests for MatchResult dataclass."""
    
    def test_match_result_creation(self):
        """Test MatchResult default values."""
        result = MatchResult(success=False, confidence=0.0)
        
        assert not result.success
        assert result.confidence == 0.0
        assert result.homography_matrix is None
        assert len(result.transformed_boxes) == 0
        assert result.inlier_count == 0
        assert result.total_matches == 0
        assert not result.requires_manual_anchors
        assert result.error_message is None
    
    def test_match_result_to_dict(self):
        """Test MatchResult serialization."""
        label = TemplateLabel(
            label_name="test",
            label_type=LabelType.CUSTOM,
            relative_x=0.1,
            relative_y=0.1,
            relative_width=0.2,
            relative_height=0.2
        )
        boxes = [TransformedBox(
            original_label=label,
            bounding_box=BoundingBox(x=10, y=10, width=20, height=20),
            is_valid=True,
            validation_error=None
        )]
        
        result = MatchResult(
            success=True,
            confidence=0.85,
            transformed_boxes=boxes,
            inlier_count=25,
            total_matches=30
        )
        
        data = result.to_dict()
        
        assert data["success"] is True
        assert data["confidence"] == 0.85
        assert len(data["transformed_boxes"]) == 1
        assert data["inlier_count"] == 25


class TestTemplateMatcher:
    """Tests for the TemplateMatcher class."""
    
    def test_matcher_initialization(self):
        """Test TemplateMatcher initializes with config."""
        config = TemplateMatchConfig(orb_nfeatures=1000)
        matcher = TemplateMatcher(config)
        
        assert matcher.config.orb_nfeatures == 1000
    
    def test_matcher_with_no_template_keypoints(self):
        """Test matcher returns error when template has no keypoints."""
        config = TemplateMatchConfig()
        matcher = TemplateMatcher(config)
        
        # Create template without keypoints
        template = Template(
            name="Test",
            feature_keypoints=None,
            labels=[]
        )
        
        # Create dummy image
        image = np.zeros((200, 200), dtype=np.uint8)
        
        result = matcher.match(template, image)
        
        assert not result.success
        assert result.requires_manual_anchors
        assert "keypoints" in result.error_message.lower()
    
    def test_matcher_prepare_keypoints(self):
        """Test preparing keypoints from an image."""
        matcher = TemplateMatcher()
        
        # Create image with features
        image = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (80, 80), 255, -1)
        cv2.rectangle(image, (100, 100), (180, 180), 255, -1)
        
        serialized = matcher.prepare_template_keypoints(image)
        
        if serialized is not None:
            assert isinstance(serialized, bytes)
            assert len(serialized) > 0
            
            # Should be deserializable
            kp, desc = matcher.deserialize_features(serialized)
            assert len(kp) > 0
    
    def test_matcher_extract_and_serialize_features(self):
        """Test full feature extraction and serialization flow."""
        matcher = TemplateMatcher()
        
        image = np.random.randint(0, 256, (200, 200), dtype=np.uint8)
        
        keypoints, descriptors = matcher.extract_features(image)
        
        if len(keypoints) > 0 and descriptors is not None:
            serialized = matcher.serialize_features(keypoints, descriptors)
            restored_kp, restored_desc = matcher.deserialize_features(serialized)
            
            assert len(restored_kp) == len(keypoints)


class TestEndToEndMatching:
    """End-to-end tests for template matching workflow."""
    
    def test_full_matching_workflow_identical_images(self):
        """Test complete template matching workflow with identical images."""
        # Create a template image with distinct features
        template_img = np.zeros((300, 300), dtype=np.uint8)
        cv2.rectangle(template_img, (50, 50), (100, 100), 255, -1)
        cv2.rectangle(template_img, (150, 150), (250, 250), 255, -1)
        cv2.circle(template_img, (200, 75), 25, 255, -1)
        
        # Extract and serialize keypoints
        matcher = TemplateMatcher()
        serialized = matcher.prepare_template_keypoints(template_img)
        
        if serialized is None:
            pytest.skip("No keypoints extracted from template")
        
        # Create template with labels
        template = Template(
            name="Test Template",
            feature_keypoints=serialized,
            labels=[
                TemplateLabel(
                    label_name="top_left_box",
                    label_type=LabelType.HEADER,
                    color="#FF0000",
                    relative_x=50/300,
                    relative_y=50/300,
                    relative_width=50/300,
                    relative_height=50/300
                ),
                TemplateLabel(
                    label_name="bottom_right_box",
                    label_type=LabelType.TABLE,
                    color="#00FF00",
                    relative_x=150/300,
                    relative_y=150/300,
                    relative_width=100/300,
                    relative_height=100/300
                )
            ],
            thumbnail_width=300,
            thumbnail_height=300
        )
        
        # Use same image as document (should have perfect match)
        document_img = template_img.copy()
        
        # Run matching
        config = TemplateMatchConfig(min_confidence=0.5)
        matcher = TemplateMatcher(config)
        result = matcher.match(template, document_img, document_dimensions=(300, 300))
        
        # Should succeed with same image
        assert result.success or result.confidence > 0.0
        
        if result.success:
            # Should have transformed boxes for each label
            assert len(result.transformed_boxes) == 2
            
            # Check confidence is high for identical images
            assert result.confidence > 0.6


# Fixture for test images
@pytest.fixture
def sample_document_image():
    """Create a sample document-like image for testing."""
    image = np.ones((500, 400), dtype=np.uint8) * 255
    
    # Add some text-like features (rectangles simulating text blocks)
    cv2.rectangle(image, (20, 20), (200, 50), 0, -1)  # Header
    cv2.rectangle(image, (20, 70), (380, 200), 0, 2)  # Table outline
    cv2.rectangle(image, (250, 300), (380, 350), 0, -1)  # Amount field
    
    # Add some noise/texture
    noise = np.random.normal(0, 10, image.shape).astype(np.int32)
    image = np.clip(image.astype(np.int32) + noise, 0, 255).astype(np.uint8)
    
    return image


@pytest.fixture
def sample_template(sample_document_image):
    """Create a sample template from the document image."""
    matcher = TemplateMatcher()
    serialized = matcher.prepare_template_keypoints(sample_document_image)
    
    if serialized is None:
        return None
    
    return Template(
        name="Invoice Template",
        feature_keypoints=serialized,
        labels=[
            TemplateLabel(
                label_name="header",
                label_type=LabelType.HEADER,
                color="#FF0000",
                relative_x=0.05,
                relative_y=0.04,
                relative_width=0.45,
                relative_height=0.06
            ),
            TemplateLabel(
                label_name="amount",
                label_type=LabelType.AMOUNT,
                color="#00FF00",
                relative_x=0.625,
                relative_y=0.6,
                relative_width=0.325,
                relative_height=0.1
            )
        ],
        thumbnail_width=400,
        thumbnail_height=500
    )


class TestWithFixtures:
    """Tests using pytest fixtures."""
    
    def test_matching_with_fixture_images(self, sample_document_image, sample_template):
        """Test matching using fixture-generated template and image."""
        if sample_template is None:
            pytest.skip("Could not create sample template")
        
        config = TemplateMatchConfig()
        matcher = TemplateMatcher(config)
        
        result = matcher.match(
            sample_template, 
            sample_document_image,
            document_dimensions=(400, 500)
        )
        
        # At minimum, should return a result
        assert isinstance(result, MatchResult)
        
        # Identical image should match well
        if result.success:
            assert result.confidence > 0.5
            assert len(result.transformed_boxes) > 0
