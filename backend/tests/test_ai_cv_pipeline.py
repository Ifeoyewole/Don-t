"""Unit and Integration Tests for AI/CV Pipe Joint Measurement System.

Tests:
1. Image Quality Gate (sharpness, exposure, contrast, glare)
2. Zero Artificial Guessing Rejection on ambiguous/featureless images
3. Camera Calibration & Lens Rectification
4. Calibrated Confidence Fusion & Gating
5. Multi-Frame Temporal Tracking with MAD Outlier Rejection
6. Tolerance-Primary OPEN_JOINT Authority
7. Physical Ground-Truth Accuracy Evaluation
"""

import cv2
import numpy as np
import pytest

from backend.app.core.cv.ai.image_quality import validate_image_quality
from backend.app.core.cv.ai.joint_classifier import JointClassifier
from backend.app.core.cv.ai.joint_segmenter import JointSegmenter
from backend.app.core.cv.calibration import camera_calibrator
from backend.app.core.cv.circular_detector import measure_circular_gap
from backend.app.core.cv.confidence import confidence_engine
from backend.app.core.cv.fusion import MultiFrameFusion
from backend.app.schemas.domain import (
    JointConditionClass,
    MeasurementResultStatus,
    ToleranceStatus,
)
from backend.app.schemas.measurement import ToleranceSpec
from training.evaluate_measurement import evaluate_physical_measurements


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def synthetic_pipe_joint_image() -> np.ndarray:
    """Generate a clean synthetic 400x400 BGR pipe opening image with known concentric circles."""
    img = np.full((400, 400, 3), 40, dtype=np.uint8)
    center = (200, 200)

    # Outer collar: radius 120, brightness 180
    cv2.circle(img, center, 120, (180, 180, 180), -1)

    # Annular gap: radius 100 to 120 (gap width 20px) -> dark ring
    cv2.circle(img, center, 100, (30, 30, 30), -1)

    # Inner pipe wall: radius 80, brightness 160
    cv2.circle(img, center, 80, (160, 160, 160), -1)

    # Hollow pipe interior: radius 70, dark interior
    cv2.circle(img, center, 70, (20, 20, 20), -1)

    return cv2.GaussianBlur(img, (3, 3), 0.8)


# ==============================================================================
# Tests
# ==============================================================================

def test_image_quality_gate(synthetic_pipe_joint_image):
    """Verify that clear images pass and blurred/corrupted images are rejected."""
    # 1. Clear image should be usable
    res_clear = validate_image_quality(synthetic_pipe_joint_image)
    assert res_clear.usable is True
    assert res_clear.quality_score > 0.50
    assert res_clear.blur_score > 0.20

    # 2. Heavily blurred image must be rejected
    blurred_img = cv2.GaussianBlur(synthetic_pipe_joint_image, (35, 35), 15.0)
    res_blurred = validate_image_quality(blurred_img)
    assert res_blurred.usable is False
    assert "blurry" in res_blurred.rejection_reason.lower()

    # 3. Solid black image must be rejected
    blank_img = np.zeros((400, 400, 3), dtype=np.uint8)
    res_blank = validate_image_quality(blank_img)
    assert res_blank.usable is False


def test_zero_artificial_guessing_rejection():
    """Verify that images without reliable concentric geometry fail safely with NO guessing."""
    # Plain pipe wall with a linear seam/feature (no concentric circular joint)
    wall_img = np.full((400, 400, 3), 140, dtype=np.uint8)
    cv2.line(wall_img, (0, 0), (400, 400), (30, 30, 30), 4)

    # Must raise ValueError with 'joint_geometry_not_reliable' rather than fabricating a fake circle from center
    with pytest.raises(ValueError) as excinfo:
        measure_circular_gap(wall_img, pipe_diameter_mm=100.0)

    assert "joint_geometry_not_reliable" in str(excinfo.value)


def test_camera_calibration_engine(synthetic_pipe_joint_image):
    """Verify lens distortion rectification and calibrated scale calculations."""
    # Test undistort
    undistorted = camera_calibrator.undistort_image(
        synthetic_pipe_joint_image,
        camera_id_or_profile="CCTV-STANDARD-01",
    )
    assert undistorted.shape == synthetic_pipe_joint_image.shape

    # Test scale with tilt compensation
    px_per_mm_flat, mm_per_px_flat = camera_calibrator.compute_calibrated_scale(
        outer_radius_px=100.0,
        pipe_diameter_mm=200.0,
        tilt_angle_deg=0.0,
    )
    assert px_per_mm_flat == 1.0
    assert mm_per_px_flat == 1.0

    # Off-axis 30 degree tilt
    px_per_mm_tilted, _ = camera_calibrator.compute_calibrated_scale(
        outer_radius_px=100.0,
        pipe_diameter_mm=200.0,
        tilt_angle_deg=30.0,
    )
    assert px_per_mm_tilted > px_per_mm_flat


def test_confidence_engine_fusion():
    """Verify multi-component confidence fusion and calibrated production gating."""
    # High confidence across all components -> ACCEPTED_MEASUREMENT
    high_bd = confidence_engine.fuse_confidence(
        quality_score=0.95,
        segmentation_score=0.92,
        condition_score=0.90,
        geometry_score=0.94,
    )
    assert high_bd.overall_confidence >= 0.90
    assert high_bd.decision == MeasurementResultStatus.ACCEPTED_MEASUREMENT

    # Medium confidence -> REVIEW_REQUIRED
    med_bd = confidence_engine.fuse_confidence(
        quality_score=0.75,
        segmentation_score=0.70,
        condition_score=0.75,
        geometry_score=0.72,
    )
    assert 0.70 <= med_bd.overall_confidence < 0.90
    assert med_bd.decision == MeasurementResultStatus.REVIEW_REQUIRED

    # Low confidence -> REJECTED_UNRELIABLE
    low_bd = confidence_engine.fuse_confidence(
        quality_score=0.40,
        segmentation_score=0.30,
        condition_score=0.50,
        geometry_score=0.35,
    )
    assert low_bd.overall_confidence < 0.70
    assert low_bd.decision == MeasurementResultStatus.REJECTED_UNRELIABLE


def test_multiframe_mad_outlier_rejection():
    """Verify that temporal fusion filters out transient outlier spikes."""
    # Burst with one transient outlier at index 3 (e.g. water splash/glare spike of 18.9mm)
    frame_sequence = [10.9, 11.0, 10.8, 18.9, 10.9]

    fusion = MultiFrameFusion.fuse_frame_measurements(frame_sequence)

    assert fusion.num_input_frames == 5
    assert fusion.num_accepted_frames == 4
    assert 3 in fusion.outlier_frame_indices  # Outlier 18.9 was rejected
    assert abs(fusion.fused_mean_gap_mm - 10.9) < 0.15  # Robust median is ~10.9mm
    assert fusion.mad_mm < 0.20
    assert fusion.temporal_consistency_score > 0.70


def test_tolerance_primary_open_joint():
    """Verify that physical gap exceeding tolerance overrides AI appearance to OPEN_JOINT."""
    classifier = JointClassifier()

    # Case A: Measured gap 18.5mm exceeds max allowable 12.0mm -> must be OPEN_JOINT
    res_open = classifier.classify_joint(
        image_bgr=None,
        measured_gap_mm=18.5,
        max_allowable_gap_mm=12.0,
    )
    assert res_open.condition == JointConditionClass.OPEN_JOINT
    assert res_open.is_tolerance_overridden is True

    # Case B: Measured gap 8.0mm within allowable 12.0mm -> remains unoverridden
    # Without visual evidence or weights, zero-guessing requires CLASSIFICATION_UNAVAILABLE
    res_normal = classifier.classify_joint(
        image_bgr=None,
        measured_gap_mm=8.0,
        max_allowable_gap_mm=12.0,
    )
    assert res_normal.condition == JointConditionClass.CLASSIFICATION_UNAVAILABLE
    assert res_normal.is_tolerance_overridden is False


def test_physical_accuracy_evaluation():
    """Verify evaluation metric calculations against known physical ground truth."""
    ground_truth = [5.0, 10.0, 15.0, 20.0, 25.0]
    measured = [5.1, 9.9, 15.2, 19.8, 25.1]
    confs = [0.95, 0.94, 0.92, 0.91, 0.90]

    report = evaluate_physical_measurements(
        ground_truth_mm=ground_truth,
        measured_mm=measured,
        confidence_scores=confs,
    )

    assert report.total_samples == 5
    assert report.mae_mm < 0.20  # Very tight error
    assert report.within_1mm_ratio == 1.0
    assert ">=0.90" in report.calibrated_risk_curve
    assert report.calibrated_risk_curve[">=0.90"] == 0.0  # Zero bad measurements


def test_api_calibration_endpoints():
    """Verify GET and POST /cv/calibration/profiles endpoints."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    res = client.get("/cv/calibration/profiles")
    assert res.status_code == 200
    profiles = res.json()
    assert len(profiles) >= 2
    camera_ids = [p["camera_id"] for p in profiles]
    assert "CCTV-STANDARD-01" in camera_ids
    assert "GOPRO-MAX-REFRAMED" in camera_ids


def test_api_multiframe_endpoint(synthetic_pipe_joint_image):
    """Verify POST /cv/measure/multi-frame burst endpoint."""
    import io
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    _, buffer = cv2.imencode(".jpg", synthetic_pipe_joint_image)
    frame_bytes = buffer.tobytes()

    files = [
        ("files", ("f1.jpg", io.BytesIO(frame_bytes), "image/jpeg")),
        ("files", ("f2.jpg", io.BytesIO(frame_bytes), "image/jpeg")),
    ]
    data = {
        "pipe_diameter_mm": "100.0",
        "max_gap_mm": "15.0",
    }

    res = client.post("/cv/measure/multi-frame", files=files, data=data)
    assert res.status_code == 200
    body = res.json()
    assert body["num_frames_received"] == 2
    assert body["num_frames_accepted"] == 2
    assert body["median_gap_mm"] > 0
    assert body["result_status"] == MeasurementResultStatus.ACCEPTED_MEASUREMENT

