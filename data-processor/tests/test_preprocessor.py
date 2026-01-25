"""
Unit tests for image preprocessing functions.

Tests noise reduction, binarization, deskew correction, and full preprocessing pipeline.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image as PILImage

# Import test subjects - these will fail gracefully if OpenCV not available
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

# Import our modules
from services.preprocessor import (
    PreprocessingConfig,
    PreprocessingResult,
    load_image_from_bytes,
    image_to_bytes,
    resize_image,
    reduce_noise,
    binarize_image,
    estimate_skew_angle,
    deskew_image,
    convert_to_grayscale,
    enhance_contrast,
    preprocess_image,
    preprocess_for_ocr,
)

# Skip all tests if OpenCV not available
pytestmark = pytest.mark.skipif(not CV2_AVAILABLE, reason="OpenCV not available")


class TestPreprocessingConfig:
    """Tests for PreprocessingConfig dataclass."""

    def test_default_values(self):
        """Test that default configuration values are set correctly."""
        config = PreprocessingConfig()

        assert config.noise_reduction is True
        assert config.gaussian_sigma == 1.0
        assert config.gaussian_kernel_size == 5
        assert config.bilateral_d == 9
        assert config.deskew_enabled is True
        assert config.deskew_max_angle == 15.0
        assert config.binarize is True
        assert config.max_width == 1024
        assert config.max_height == 1024

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PreprocessingConfig(
            noise_reduction=False,
            gaussian_sigma=2.0,
            max_width=800,
            max_height=600
        )

        assert config.noise_reduction is False
        assert config.gaussian_sigma == 2.0
        assert config.max_width == 800
        assert config.max_height == 600

    @patch('services.preprocessor.settings')
    def test_from_settings(self, mock_settings):
        """Test creating config from Django settings."""
        mock_settings.PREPROCESSING_NOISE_REDUCTION = False
        mock_settings.PREPROCESSING_GAUSSIAN_SIGMA = 2.5
        mock_settings.MAX_IMAGE_WIDTH = 800
        mock_settings.MAX_IMAGE_HEIGHT = 600

        config = PreprocessingConfig.from_settings()

        assert config.noise_reduction is False
        assert config.gaussian_sigma == 2.5
        assert config.max_width == 800
        assert config.max_height == 600

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "noise_reduction": False,
            "gaussian_sigma": 2.5,
            "max_width": 800,
            "unknown_field": "ignored"
        }
        config = PreprocessingConfig.from_dict(data)

        assert config.noise_reduction is False
        assert config.gaussian_sigma == 2.5
        assert config.max_width == 800


class TestImageLoading:
    """Tests for image loading and conversion functions."""

    def test_load_image_from_bytes_valid_png(self):
        """Test loading a valid PNG image from bytes."""
        # Create a simple test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)
        test_image[25:75, 25:75] = [255, 0, 0]  # Red square

        # Convert to PNG bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()

        # Load back
        loaded = load_image_from_bytes(image_bytes)

        assert loaded is not None
        assert loaded.shape[0] == 100
        assert loaded.shape[1] == 100
        assert loaded.shape[2] == 3

    def test_load_image_from_bytes_invalid_data(self):
        """Test loading invalid image data raises ValueError."""
        with pytest.raises(ValueError, match="Failed to decode image"):
            load_image_from_bytes(b"not an image")

    def test_image_to_bytes_png(self):
        """Test converting image to PNG bytes."""
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        test_image[:, :] = [0, 255, 0]  # Green image

        result_bytes = image_to_bytes(test_image, "PNG")

        assert isinstance(result_bytes, bytes)
        assert len(result_bytes) > 0

        # Verify we can load it back
        loaded = load_image_from_bytes(result_bytes)
        assert loaded.shape[0] == 50
        assert loaded.shape[1] == 50

    def test_image_to_bytes_jpeg(self):
        """Test converting image to JPEG bytes."""
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        test_image[:, :] = [255, 255, 255]  # White image

        result_bytes = image_to_bytes(test_image, "JPEG")

        assert isinstance(result_bytes, bytes)
        assert len(result_bytes) > 0

    def test_image_to_bytes_unsupported_format(self):
        """Test unsupported format raises ValueError."""
        test_image = np.zeros((10, 10, 3), dtype=np.uint8)

        with pytest.raises(ValueError, match="Unsupported format"):
            image_to_bytes(test_image, "BMP")


class TestImageResizing:
    """Tests for image resizing functionality."""

    def test_resize_image_no_resize_needed(self):
        """Test that small images are not resized."""
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)

        resized, original_size, new_size = resize_image(test_image, 200, 200)

        assert np.array_equal(resized, test_image)
        assert original_size == (100, 100)
        assert new_size == (100, 100)

    def test_resize_image_width_limited(self):
        """Test resizing when width exceeds max."""
        test_image = np.zeros((100, 300, 3), dtype=np.uint8)  # 300x100

        resized, original_size, new_size = resize_image(test_image, 200, 200)

        assert original_size == (300, 100)
        assert new_size[0] == 200  # Width limited to 200
        assert new_size[1] == 67   # Height scaled proportionally
        assert resized.shape[1] == 200
        assert resized.shape[0] == 67

    def test_resize_image_height_limited(self):
        """Test resizing when height exceeds max."""
        test_image = np.zeros((300, 100, 3), dtype=np.uint8)  # 100x300

        resized, original_size, new_size = resize_image(test_image, 200, 200)

        assert original_size == (100, 300)
        assert new_size[0] == 67   # Width scaled proportionally
        assert new_size[1] == 200  # Height limited to 200
        assert resized.shape[0] == 200
        assert resized.shape[1] == 67


class TestNoiseReduction:
    """Tests for noise reduction functionality."""

    def test_reduce_noise_grayscale(self):
        """Test noise reduction on grayscale image."""
        # Create test image with some noise
        test_image = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

        config = PreprocessingConfig()
        result = reduce_noise(test_image, config)

        assert result.shape == test_image.shape
        assert result.dtype == test_image.dtype
        # Should be smoother than original
        assert not np.array_equal(result, test_image)

    def test_reduce_noise_color(self):
        """Test noise reduction on color image."""
        test_image = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)

        config = PreprocessingConfig()
        result = reduce_noise(test_image, config)

        assert result.shape == test_image.shape
        assert result.dtype == test_image.dtype

    def test_reduce_noise_custom_config(self):
        """Test noise reduction with custom configuration."""
        test_image = np.random.randint(0, 256, (50, 50), dtype=np.uint8)

        config = PreprocessingConfig(
            gaussian_sigma=2.0,
            bilateral_d=15,
            bilateral_sigma_color=100
        )
        result = reduce_noise(test_image, config)

        assert result.shape == test_image.shape


class TestImageBinarization:
    """Tests for image binarization functionality."""

    def test_binarize_image_grayscale(self):
        """Test binarization on grayscale image."""
        # Create test image with gradient
        test_image = np.zeros((50, 50), dtype=np.uint8)
        test_image[:, :25] = 255  # Left half white, right half black

        config = PreprocessingConfig()
        result = binarize_image(test_image, config)

        assert result.shape == test_image.shape
        # Should be binary (0 or 255 values)
        unique_values = np.unique(result)
        assert all(val in [0, 255] for val in unique_values)

    def test_binarize_image_color(self):
        """Test binarization on color image."""
        test_image = np.random.randint(0, 256, (30, 30, 3), dtype=np.uint8)

        config = PreprocessingConfig()
        result = binarize_image(test_image, config)

        assert result.shape[:2] == test_image.shape[:2]
        assert len(result.shape) == 2  # Should be grayscale
        # Should be binary
        unique_values = np.unique(result)
        assert all(val in [0, 255] for val in unique_values)

    @patch('cv2.adaptiveThreshold')
    def test_binarize_image_adaptive_fallback(self, mock_adaptive):
        """Test fallback to Otsu's method when adaptive threshold fails."""
        mock_adaptive.side_effect = Exception("Adaptive threshold failed")

        test_image = np.random.randint(0, 256, (30, 30), dtype=np.uint8)

        config = PreprocessingConfig()
        result = binarize_image(test_image, config)

        # Should still produce binary result
        unique_values = np.unique(result)
        assert all(val in [0, 255] for val in unique_values)


class TestSkewEstimation:
    """Tests for skew angle estimation."""

    def test_estimate_skew_angle_no_lines(self):
        """Test skew estimation on blank image."""
        test_image = np.zeros((100, 100), dtype=np.uint8)

        angle = estimate_skew_angle(test_image)

        assert angle == 0.0

    def test_estimate_skew_angle_horizontal_lines(self):
        """Test skew estimation with horizontal lines."""
        test_image = np.zeros((100, 100), dtype=np.uint8)
        # Draw horizontal lines
        cv2.line(test_image, (10, 20), (90, 20), 255, 2)
        cv2.line(test_image, (10, 40), (90, 40), 255, 2)
        cv2.line(test_image, (10, 60), (90, 60), 255, 2)

        angle = estimate_skew_angle(test_image)

        # Should be close to 0 for horizontal lines
        assert abs(angle) < 1.0

    def test_estimate_skew_angle_slanted_lines(self):
        """Test skew estimation with slanted lines."""
        test_image = np.zeros((100, 100), dtype=np.uint8)
        # Draw slanted lines (about 10 degrees)
        cv2.line(test_image, (10, 10), (90, 25), 255, 2)
        cv2.line(test_image, (10, 30), (90, 45), 255, 2)

        angle = estimate_skew_angle(test_image)

        # Should detect some angle
        assert angle != 0.0

    def test_estimate_skew_angle_color_image(self):
        """Test skew estimation on color image."""
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        cv2.line(test_image, (10, 10), (40, 25), (255, 255, 255), 2)

        angle = estimate_skew_angle(test_image)

        assert isinstance(angle, float)


class TestImageDeskewing:
    """Tests for image deskewing functionality."""

    def test_deskew_image_no_skew(self):
        """Test deskewing with negligible angle."""
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        test_image[:, :] = [255, 255, 255]

        result, angle = deskew_image(test_image, angle=0.1)

        assert np.array_equal(result, test_image)
        assert angle == 0.0

    def test_deskew_image_with_angle(self):
        """Test deskewing with specified angle."""
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)
        test_image[20:30, 20:30] = [255, 0, 0]  # Red square

        result, angle = deskew_image(test_image, angle=5.0)

        assert result.shape != test_image.shape  # Should be larger due to rotation
        assert angle == 5.0

    def test_deskew_image_angle_clamping(self):
        """Test that large angles are clamped."""
        test_image = np.zeros((30, 30, 3), dtype=np.uint8)

        result, angle = deskew_image(test_image, angle=20.0, max_angle=15.0)

        assert abs(angle) <= 15.0

    def test_deskew_image_auto_estimation(self):
        """Test deskewing with automatic angle estimation."""
        test_image = np.zeros((50, 50), dtype=np.uint8)
        cv2.line(test_image, (10, 10), (40, 20), 255, 2)

        result, angle = deskew_image(test_image)

        assert isinstance(angle, float)
        assert result.shape[0] >= test_image.shape[0]  # May be larger


class TestImageConversion:
    """Tests for image conversion utilities."""

    def test_convert_to_grayscale_already_gray(self):
        """Test converting already grayscale image."""
        test_image = np.zeros((30, 30), dtype=np.uint8)

        result = convert_to_grayscale(test_image)

        assert np.array_equal(result, test_image)
        assert len(result.shape) == 2

    def test_convert_to_grayscale_color(self):
        """Test converting color image to grayscale."""
        test_image = np.zeros((30, 30, 3), dtype=np.uint8)
        test_image[:, :, 0] = 255  # Red channel

        result = convert_to_grayscale(test_image)

        assert result.shape == (30, 30)
        assert len(result.shape) == 2

    def test_enhance_contrast_grayscale(self):
        """Test contrast enhancement on grayscale image."""
        # Create low contrast image
        test_image = np.full((30, 30), 128, dtype=np.uint8)

        result = enhance_contrast(test_image)

        assert result.shape == test_image.shape
        assert result.dtype == test_image.dtype

    def test_enhance_contrast_color(self):
        """Test contrast enhancement on color image."""
        test_image = np.full((20, 20, 3), 128, dtype=np.uint8)

        result = enhance_contrast(test_image)

        assert result.shape == (20, 20)
        assert len(result.shape) == 2  # Should be grayscale


class TestPreprocessingResult:
    """Tests for PreprocessingResult dataclass."""

    def test_preprocessing_result_creation(self):
        """Test PreprocessingResult initialization."""
        image = np.zeros((100, 100), dtype=np.uint8)

        result = PreprocessingResult(
            image=image,
            original_size=(200, 200),
            processed_size=(100, 100),
            deskew_angle=2.5,
            steps_applied=["resize", "deskew"]
        )

        assert result.deskew_angle == 2.5
        assert result.steps_applied == ["resize", "deskew"]

    def test_preprocessing_result_default_steps(self):
        """Test that steps_applied defaults to empty list."""
        image = np.zeros((50, 50), dtype=np.uint8)

        result = PreprocessingResult(
            image=image,
            original_size=(50, 50),
            processed_size=(50, 50)
        )

        assert result.steps_applied == []
        assert result.deskew_angle is None


class TestFullPreprocessing:
    """Tests for the complete preprocessing pipeline."""

    def test_preprocess_image_basic(self):
        """Test basic preprocessing pipeline."""
        # Create test image
        test_image = np.zeros((200, 200, 3), dtype=np.uint8)
        test_image[50:150, 50:150] = [255, 255, 255]  # White square

        # Convert to bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()

        config = PreprocessingConfig()
        result = preprocess_image(image_bytes, config)

        assert isinstance(result, PreprocessingResult)
        assert result.original_size == (200, 200)
        assert len(result.steps_applied) > 0
        assert "resize" in result.steps_applied or result.processed_size == (200, 200)

    def test_preprocess_image_no_processing(self):
        """Test preprocessing with all steps disabled."""
        # Create small test image
        test_image = np.zeros((50, 50, 3), dtype=np.uint8)

        # Convert to bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()

        config = PreprocessingConfig(
            noise_reduction=False,
            deskew_enabled=False,
            binarize=False
        )
        result = preprocess_image(image_bytes, config)

        assert isinstance(result, PreprocessingResult)
        assert result.steps_applied == ["resize"]  # Only resize should be applied

    def test_preprocess_for_ocr(self):
        """Test the OCR preprocessing convenience function."""
        # Create test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Convert to bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()

        processed_image, metadata = preprocess_for_ocr(image_bytes)

        assert isinstance(processed_image, np.ndarray)
        assert isinstance(metadata, dict)
        assert "original_size" in metadata
        assert "processed_size" in metadata
        assert "steps_applied" in metadata

    def test_preprocess_for_ocr_with_options(self):
        """Test OCR preprocessing with custom options."""
        # Create test image
        test_image = np.zeros((100, 100, 3), dtype=np.uint8)

        # Convert to bytes
        success, encoded = cv2.imencode('.png', test_image)
        assert success
        image_bytes = encoded.tobytes()

        options = {
            "noise_reduction": False,
            "binarize": False
        }

        processed_image, metadata = preprocess_for_ocr(image_bytes, options)

        assert isinstance(processed_image, np.ndarray)
        assert metadata["steps_applied"] == ["resize"]  # Only resize


# Test fixtures
@pytest.fixture
def sample_image_bytes():
    """Create sample image bytes for testing."""
    test_image = np.zeros((100, 100, 3), dtype=np.uint8)
    test_image[25:75, 25:75] = [255, 0, 0]  # Red square

    success, encoded = cv2.imencode('.png', test_image)
    assert success
    return encoded.tobytes()


@pytest.fixture
def sample_config():
    """Create sample preprocessing config."""
    return PreprocessingConfig(
        noise_reduction=True,
        deskew_enabled=True,
        binarize=True,
        max_width=200,
        max_height=200
    )