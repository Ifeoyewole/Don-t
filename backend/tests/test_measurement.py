"""Automated Unit and Integration Tests for Computer Vision Measurement Backend."""

import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.preprocessor import validate_photo_quality
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.core.cv.tolerance import classify_gap, evaluate_overall_status
from backend.app.main import app
from backend.app.schemas.domain import ExposureStatus, JointType, ToleranceStatus
from backend.app.schemas.measurement import ToleranceSpec
from backend.app.utils.image_io import encode_image_to_base64


# ==============================================================================
# Test Fixtures & Synthetic Image Generators
# ==============================================================================

@pytest.fixture
def synthetic_circular_image() -> np.ndarray:
    """Generate a clean synthetic 400x400 BGR pipe opening image with known concentric circles."""
    img = np.full((400, 400, 3), 40, dtype=np.uint8)  # Dark background
    center = (200, 200)

    # Outer collar: radius 120, brightness 180
    cv2.circle(img, center, 120, (180, 180, 180), -1)

    # Annular gap: radius 100 to 120 (gap width 20px) -> dark ring
    cv2.circle(img, center, 100, (30, 30, 30), -1)

    # Inner pipe wall: radius 80, brightness 160
    cv2.circle(img, center, 80, (160, 160, 160), -1)

    # Hollow pipe interior: radius 70, dark interior
    cv2.circle(img, center, 70, (20, 20, 20), -1)

    # Add slight gaussian blur for realistic anti-aliasing
    return cv2.GaussianBlur(img, (3, 3), 0.8)


@pytest.fixture
def synthetic_vertical_seam_image() -> np.ndarray:
    """Generate a synthetic vertical seam gap image (two plates separated by 18px gap)."""
    img = np.full((400, 400, 3), 160, dtype=np.uint8)  # Bright steel plate

    # Vertical gap in center: X from 191 to 209 (gap width 18px)
    img[:, 191:209] = (25, 25, 25)

    return cv2.GaussianBlur(img, (3, 3), 0.8)


@pytest.fixture
def synthetic_horizontal_seam_image() -> np.ndarray:
    """Generate a synthetic horizontal seam gap image (two plates separated by 20px gap)."""
    img = np.full((400, 400, 3), 170, dtype=np.uint8)

    # Horizontal gap in center: Y from 190 to 210 (gap width 20px)
    img[190:210, :] = (20, 20, 20)

    return cv2.GaussianBlur(img, (3, 3), 0.8)


@pytest.fixture
def blurry_image() -> np.ndarray:
    """Generate a heavily blurred image that fails sharpness threshold."""
    img = np.full((200, 200, 3), 128, dtype=np.uint8)
    cv2.circle(img, (100, 100), 50, (200, 200, 200), -1)
    return cv2.GaussianBlur(img, (35, 35), 15.0)


@pytest.fixture
def underexposed_image() -> np.ndarray:
    """Generate an underexposed dark image."""
    return np.full((200, 200, 3), 20, dtype=np.uint8)


@pytest.fixture
def overexposed_glare_image() -> np.ndarray:
    """Generate an overexposed image with saturated specular glare."""
    img = np.full((200, 200, 3), 225, dtype=np.uint8)
    # Add large specular glare hotspot
    img[50:150, 50:150] = 255
    return img


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client instance."""
    return TestClient(app)


# ==============================================================================
# Unit Tests: Tolerance Classification
# ==============================================================================

def test_standard_pipe_tolerance_table():
    """Verify standard pipe tolerance classifications."""
    assert classify_gap(2.0, pipe_diameter_mm=100.0) == ToleranceStatus.REVIEW
    assert classify_gap(3.0, pipe_diameter_mm=100.0) == ToleranceStatus.PASS
    assert classify_gap(10.0, pipe_diameter_mm=100.0) == ToleranceStatus.PASS
    assert classify_gap(15.0, pipe_diameter_mm=100.0) == ToleranceStatus.PASS
    assert classify_gap(18.0, pipe_diameter_mm=100.0) == ToleranceStatus.REVIEW
    assert classify_gap(25.0, pipe_diameter_mm=100.0) == ToleranceStatus.REVIEW
    assert classify_gap(28.0, pipe_diameter_mm=100.0) == ToleranceStatus.FAIL


def test_custom_tolerance_spec():
    """Verify custom ToleranceSpec bound evaluations."""
    spec = ToleranceSpec(nominal_gap_mm=8.0, min_gap_mm=4.0, max_gap_mm=12.0, warning_margin_mm=2.0)
    assert classify_gap(2.5, tolerance_spec=spec) == ToleranceStatus.REVIEW
    assert classify_gap(7.5, tolerance_spec=spec) == ToleranceStatus.PASS
    assert classify_gap(13.0, tolerance_spec=spec) == ToleranceStatus.WARNING
    assert classify_gap(15.5, tolerance_spec=spec) == ToleranceStatus.FAIL


def test_overall_status_aggregation():
    """Verify multi-point sample status aggregation priority."""
    assert evaluate_overall_status([ToleranceStatus.PASS, ToleranceStatus.PASS]) == ToleranceStatus.PASS
    assert evaluate_overall_status([ToleranceStatus.PASS, ToleranceStatus.REVIEW]) == ToleranceStatus.REVIEW
    assert evaluate_overall_status([ToleranceStatus.PASS, ToleranceStatus.WARNING]) == ToleranceStatus.WARNING
    assert evaluate_overall_status([ToleranceStatus.PASS, ToleranceStatus.FAIL, ToleranceStatus.WARNING]) == ToleranceStatus.FAIL


# ==============================================================================
# Unit Tests: Preprocessor & Image Quality Validation
# ==============================================================================

def test_validate_photo_quality_sharp(synthetic_circular_image):
    """Verify quality validation passes on clear in-focus image."""
    result = validate_photo_quality(synthetic_circular_image, blur_threshold=50.0)
    assert not result.is_blurry
    assert result.exposure_status == ExposureStatus.OK
    assert result.is_acceptable


def test_validate_photo_quality_blurry(blurry_image):
    """Verify quality validation flags blurred image."""
    result = validate_photo_quality(blurry_image, blur_threshold=100.0)
    assert result.is_blurry
    assert not result.is_acceptable
    assert any("focus" in rec.lower() or "blurry" in rec.lower() for rec in result.recommendations)


def test_validate_photo_quality_underexposed(underexposed_image):
    """Verify quality validation flags underexposed scene."""
    result = validate_photo_quality(underexposed_image)
    assert result.exposure_status == ExposureStatus.UNDEREXPOSED
    assert not result.is_acceptable
    assert any("underexposed" in rec.lower() for rec in result.recommendations)


def test_validate_photo_quality_glare(overexposed_glare_image):
    """Verify quality validation flags specular glare and high brightness."""
    result = validate_photo_quality(overexposed_glare_image)
    assert result.glare_detected or result.exposure_status == ExposureStatus.OVEREXPOSED
    assert not result.is_acceptable


# ==============================================================================
# Unit Tests: Circular & Seam CV Detectors
# ==============================================================================

def test_measure_circular_gap(synthetic_circular_image):
    """Test circular gap measurement algorithm on synthetic pipe image."""
    response = measure_circular_gap(
        synthetic_circular_image,
        pipe_diameter_mm=100.0,
        num_rays=36,
        return_debug_image=True,
    )

    assert response.joint_type == JointType.CIRCULAR_OPENING
    assert response.pipe_diameter_mm == 100.0
    assert response.pixels_per_mm > 0.0
    assert response.mean_gap_mm > 0.0
    assert len(response.overlay_hints.ray_samples) == 36
    assert response.debug_info is not None
    assert response.debug_info.debug_image_base64 is not None
    assert response.debug_info.debug_image_base64.startswith("data:image/jpeg;base64,")


def test_measure_vertical_seam_gap(synthetic_vertical_seam_image):
    """Test vertical seam gap measurement algorithm."""
    response = measure_seam_gap(
        synthetic_vertical_seam_image,
        joint_type=JointType.VERTICAL_SEAM,
        pipe_diameter_mm=100.0,
        num_scanlines=20,
        return_debug_image=True,
    )

    assert response.joint_type == JointType.VERTICAL_SEAM
    assert response.mean_gap_mm > 0.0
    assert len(response.overlay_hints.gap_lines) == 20
    assert response.overlay_hints.seam_left_edge is not None
    assert response.overlay_hints.seam_right_edge is not None


def test_measure_horizontal_seam_gap(synthetic_horizontal_seam_image):
    """Test horizontal seam gap measurement algorithm."""
    response = measure_seam_gap(
        synthetic_horizontal_seam_image,
        joint_type=JointType.HORIZONTAL_SEAM,
        pipe_diameter_mm=100.0,
        num_scanlines=20,
        return_debug_image=True,
    )

    assert response.joint_type == JointType.HORIZONTAL_SEAM
    assert response.mean_gap_mm > 0.0
    assert len(response.overlay_hints.gap_lines) == 20


# ==============================================================================
# Integration Tests: FastAPI Endpoints
# ==============================================================================

def test_api_health(client):
    """Test /health and /cv/health endpoints."""
    res = client.get("/cv/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "opencv_version" in data


def test_api_validate_photo(client, synthetic_circular_image):
    """Test POST /cv/validate-photo with multipart file upload."""
    _, buffer = cv2.imencode(".jpg", synthetic_circular_image)
    files = {"file": ("test.jpg", io.BytesIO(buffer.tobytes()), "image/jpeg")}

    res = client.post("/cv/validate-photo", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "blur_score" in data
    assert "exposure_status" in data
    assert "is_acceptable" in data


def test_api_measure_circular(client, synthetic_circular_image):
    """Test POST /cv/measure for circular pipe opening."""
    _, buffer = cv2.imencode(".jpg", synthetic_circular_image)
    files = {"file": ("pipe.jpg", io.BytesIO(buffer.tobytes()), "image/jpeg")}
    data = {
        "joint_type": "CIRCULAR_OPENING",
        "pipe_diameter_mm": "100.0",
        "return_debug_image": "true",
        "num_samples": "36",
    }

    res = client.post("/cv/measure", files=files, data=data)
    assert res.status_code == 200
    result = res.json()
    assert result["joint_type"] == "CIRCULAR_OPENING"
    assert result["mean_gap_mm"] > 0
    assert len(result["overlay_hints"]["ray_samples"]) == 36


def test_api_measure_vertical_seam(client, synthetic_vertical_seam_image):
    """Test POST /cv/measure for vertical seam."""
    _, buffer = cv2.imencode(".jpg", synthetic_vertical_seam_image)
    files = {"file": ("seam.jpg", io.BytesIO(buffer.tobytes()), "image/jpeg")}
    data = {
        "joint_type": "VERTICAL_SEAM",
        "pipe_diameter_mm": "100.0",
        "return_debug_image": "true",
        "num_samples": "20",
    }

    res = client.post("/cv/measure", files=files, data=data)
    assert res.status_code == 200
    result = res.json()
    assert result["joint_type"] == "VERTICAL_SEAM"
    assert result["mean_gap_mm"] > 0


def test_api_measure_invalid_image(client):
    """Test POST /cv/measure with corrupt non-image bytes."""
    files = {"file": ("corrupt.jpg", io.BytesIO(b"not an image"), "image/jpeg")}
    res = client.post("/cv/measure", files=files)
    assert res.status_code == 400
